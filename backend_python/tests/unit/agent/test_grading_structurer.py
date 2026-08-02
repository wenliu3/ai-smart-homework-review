"""可选独立结构化模型链路：普通报告节点与结构化整理节点（任务 5）。

开启时：规则模型出两份普通文本报告（structured=False），独立结构化模型一次
整理为 GradingReportPair。验证：
- 普通报告提取：主/复核节点从最后一个 AIMessage 取非空文本，只调用一次；
  普通模式 Agent 由 get_grading_agent(..., structured=False) 获取。
- 结构化整理：传给结构化模型的消息只含两份报告与规则，绝不泄露 base64 图片、
  附件路径或学生原始正文；无 structured_response / extraction_errors 非空 /
  维度不匹配 / 分数越界均降级为有限 grading_failure（不抛异常）。
"""
from langchain_core.messages import AIMessage

from app.agent.contracts import (
    CriterionGrade,
    GradingDraft,
    GradingReportPair,
    GradingRubric,
    NormalizedSubmissionContent,
    RubricCriterion,
    SubmissionImageRef,
    SubmissionTextBlock,
)
from app.agent.graphs.grading import GRADING_AGENT_NODE, GRADING_STRUCTURER_NODE
from app.agent.subagents.grading import (
    create_node as create_grading_node,
    invoke_plain_grader,
)
from app.agent.subagents.grading_review import create_node as create_review_node
from app.agent.subagents.grading_structurer import (
    build_structurer_prompt,
    invoke_structurer,
)


def _rubric() -> GradingRubric:
    return GradingRubric(
        version="v1",
        criteria=[RubricCriterion(
            criterion_id="overall", title="综合质量", max_score=100,
        )],
    )


def _draft_payload(score: float) -> dict:
    return GradingDraft(
        rubric_version="v1",
        items=[CriterionGrade(
            criterion_id="overall",
            title="综合质量",
            score=score,
            max_score=100,
            feedback="内容完整",
            evidence_refs=["submission:text:1"],
        )],
        summary="总体不错",
    ).model_dump()


def _valid_pair_payload() -> dict:
    return {
        "primary": _draft_payload(86),
        "review": _draft_payload(82),
    }


class _FakeAgent:
    """替身 Agent：记录调用，返回预设结果。"""

    def __init__(self, result):
        self.result = result
        self.calls = []

    def invoke(self, payload, **kwargs):
        self.calls.append(payload)
        return self.result


class _RecordingRegistry:
    """记录 get_grading_agent / get_specialist 调用，返回同一个替身 Agent。"""

    def __init__(self, agent):
        self.agent = agent
        self.grading_calls = []
        self.specialist_calls = []

    def get_grading_agent(self, db, *, model_code, reviewer, structured):
        self.grading_calls.append({
            "model_code": model_code,
            "reviewer": reviewer,
            "structured": structured,
        })
        return self.agent

    def get_specialist(self, name, db):
        self.specialist_calls.append(name)
        return self.agent


def _plain_state(**overrides) -> dict:
    state = {
        "rubric": _rubric(),
        "normalized_content": NormalizedSubmissionContent(),
        "structurer_enabled": True,
        "rule_model_code": "mimo",
        "rule_prompt": "按实验要求评分",
    }
    state.update(overrides)
    return state


def _structurer_state(**overrides) -> dict:
    state = {
        "rubric": _rubric(),
        "rule_prompt": "按实验报告要求评分，满分 100。",
        "grading_report": "主批改报告：内容完整，依据充分，建议得 86 分。",
        "review_report": "独立复核报告：内容较完整，个别依据不足，建议得 82 分。",
        "structurer_model_code": "deepseek",
    }
    state.update(overrides)
    return state


# ========== 步骤 1：普通报告节点 ==========

def test_plain_grader_primary_extracts_report_once():
    agent = _FakeAgent({"messages": [AIMessage(
        content="主批改普通报告",
        usage_metadata={"input_tokens": 80, "output_tokens": 40, "total_tokens": 120},
    )]})
    registry = _RecordingRegistry(agent)
    node = create_grading_node(object(), registry)

    result = node(_plain_state())

    assert result["grading_report"] == "主批改普通报告"
    assert result["usage"]["total_tokens"] == 120
    assert len(agent.calls) == 1
    # 普通模式 Agent 走 get_grading_agent(structured=False)，不用 specialist
    assert registry.grading_calls == [{
        "model_code": "mimo", "reviewer": False, "structured": False,
    }]
    assert registry.specialist_calls == []


def test_plain_grader_review_extracts_report_once():
    agent = _FakeAgent({"messages": [AIMessage(
        content="独立复核普通报告",
        usage_metadata={"input_tokens": 70, "output_tokens": 40, "total_tokens": 110},
    )]})
    registry = _RecordingRegistry(agent)
    node = create_review_node(object(), registry)

    result = node(_plain_state())

    assert result["review_report"] == "独立复核普通报告"
    assert result["usage"]["total_tokens"] == 110
    assert len(agent.calls) == 1
    assert registry.grading_calls == [{
        "model_code": "mimo", "reviewer": True, "structured": False,
    }]
    assert registry.specialist_calls == []


def test_invoke_plain_grader_direct():
    agent = _FakeAgent({"messages": [AIMessage(content="直接调用报告")]})

    result = invoke_plain_grader(
        agent, _plain_state(), reviewer=False, stage=GRADING_AGENT_NODE,
    )

    assert result["grading_report"] == "直接调用报告"
    assert len(agent.calls) == 1


def test_plain_grader_takes_last_nonempty_aimessage():
    agent = _FakeAgent({"messages": [
        AIMessage(content="第一版"),
        AIMessage(content="最终批改报告"),
    ]})

    result = invoke_plain_grader(
        agent, _plain_state(), reviewer=False, stage=GRADING_AGENT_NODE,
    )

    assert result["grading_report"] == "最终批改报告"


def test_plain_grader_empty_report_degrades_to_failure():
    agent = _FakeAgent({"messages": [AIMessage(content="   \n  ")]})
    node = create_grading_node(object(), _RecordingRegistry(agent))

    result = node(_plain_state())

    assert "grading_report" not in result
    assert result["grading_failure"]["stage"] == "grading_agent"
    assert result["grading_failure"]["error"]
    assert len(agent.calls) == 1


# ========== 步骤 2：结构化整理节点 ==========

def test_structurer_success_returns_pair_and_usage():
    agent = _FakeAgent({
        "structured_response": _valid_pair_payload(),
        "messages": [AIMessage(
            content="",
            usage_metadata={"input_tokens": 200, "output_tokens": 100, "total_tokens": 300},
        )],
    })

    result = invoke_structurer(agent, _structurer_state())

    assert "grading_failure" not in result
    assert isinstance(result["report_pair"], GradingReportPair)
    assert result["report_pair"].primary.total_score == 86
    assert result["report_pair"].review.total_score == 82
    assert result["usage"]["total_tokens"] == 300
    assert len(agent.calls) == 1


def test_structurer_message_excludes_images_paths_and_raw_body():
    captured = {}

    class _CapturingAgent:
        def invoke(self, payload, **kwargs):
            captured["messages"] = payload["messages"]
            return {"structured_response": _valid_pair_payload()}

    state = _structurer_state(normalized_content=NormalizedSubmissionContent(
        text_blocks=[SubmissionTextBlock(
            source_type="rich_text",
            label="学生富文本正文",
            content="学生原始正文绝不能外泄，含伪 base64 标记",
            evidence_ref="submission:text:1",
        )],
        image_refs=[SubmissionImageRef(
            file_name="chart.png",
            file_path="D:/secret/uploads/chart.png",
            evidence_ref="submission:image:1",
        )],
    ))

    result = invoke_structurer(_CapturingAgent(), state)

    content = captured["messages"][0].content
    # 只含两份报告、评分量表与教师规则
    assert "按实验报告要求评分" in content
    assert "主批改报告：内容完整" in content
    assert "独立复核报告：内容较完整" in content
    # 绝不泄露 base64 图片、附件路径或学生原始正文
    assert "data:image" not in content
    assert "base64" not in content
    assert "D:/secret/uploads/chart.png" not in content
    assert "学生原始正文绝不能外泄" not in content
    assert "grading_failure" not in result


def test_structurer_prompt_includes_mandatory_rule():
    prompt = build_structurer_prompt(_structurer_state())
    assert "你只能整理两份已有批改报告" in prompt
    assert "禁止读取不存在的原始作业" in prompt
    assert "禁止重新评分" in prompt
    assert "禁止补造分数、证据或扣分理由" in prompt
    assert "报告信息不足时写入 extraction_errors" in prompt


def test_structurer_missing_structured_response_degrades():
    agent = _FakeAgent({"messages": []})

    result = invoke_structurer(agent, _structurer_state())

    assert "report_pair" not in result
    failure = result["grading_failure"]
    assert failure["stage"] == GRADING_STRUCTURER_NODE
    assert failure["error"]


def test_structurer_extraction_errors_degrades():
    payload = _valid_pair_payload()
    payload["extraction_errors"] = ["主批改报告未提供得分依据"]
    agent = _FakeAgent({"structured_response": payload})

    result = invoke_structurer(agent, _structurer_state())

    assert "report_pair" not in result
    failure = result["grading_failure"]
    assert failure["stage"] == GRADING_STRUCTURER_NODE
    assert "主批改报告未提供得分依据" in failure["error"]


def test_structurer_dimension_mismatch_degrades():
    payload = _valid_pair_payload()
    payload["primary"]["items"][0]["criterion_id"] = "wrong_id"
    agent = _FakeAgent({"structured_response": payload})

    result = invoke_structurer(agent, _structurer_state())

    assert "report_pair" not in result
    assert result["grading_failure"]["stage"] == GRADING_STRUCTURER_NODE
    assert result["grading_failure"]["error"]


def test_structurer_score_out_of_bounds_degrades():
    payload = _valid_pair_payload()
    payload["review"]["items"][0]["score"] = 150
    agent = _FakeAgent({"structured_response": payload})

    result = invoke_structurer(agent, _structurer_state())

    assert "report_pair" not in result
    assert result["grading_failure"]["stage"] == GRADING_STRUCTURER_NODE
    assert result["grading_failure"]["error"]
