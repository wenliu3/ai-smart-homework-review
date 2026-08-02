"""直接调用 AI 批改方法（7 月 15 版）的单元测试。

覆盖：
- _run_ai_grading 正则提取总分（「总分：85分」「总分:90分」、缺失返回 None）
- 模型响应 content 为分块列表时的文本归一化
- _build_media_items 媒体消息构建（老师要求 / 参考附件 / 学生正文 / 图片）
- _grading_prompt_text 多维度提示与输出格式要求
"""
import pytest
from PIL import Image

from app.models import Assignment, Submission
from app.tasks.grading import (
    _build_media_items,
    _coerce_text_content,
    _grading_prompt_text,
    _run_ai_grading,
    _strip_html,
)


def _assignment(description="<p>请论述软件测试的意义</p>", attachments=None, **ai_rule_overrides):
    ai_rule = {"version": "rubric-v1", "maxScore": 100, "modelType": "deepseek"}
    ai_rule.update(ai_rule_overrides)
    return Assignment(
        title="测试作业",
        description=description,
        teacher_id=1,
        teacher_name="教师",
        classes=[],
        status="published",
        ai_rule=ai_rule,
        attachments=attachments or [],
    )


def _submission(content="学生答案", attachments=None):
    return Submission(
        assignment_id=1,
        student_id=2,
        class_id=3,
        content=content,
        attachments=attachments or [],
        status="submitted",
        submission_count=1,
    )


class _FakeLLM:
    """记录消息内容的假模型，返回预设 content。"""

    def __init__(self, content):
        self.content = content
        self.prompt = None

    def invoke(self, messages):
        self.prompt = messages[0].content
        class _Response:
            pass

        response = _Response()
        response.content = self.content
        return response


def _patch_llm(monkeypatch, fake):
    monkeypatch.setattr(
        "app.tasks.grading.model_gateway.get_chat_model_by_code",
        lambda *args, **kwargs: fake,
    )


def _texts_from_prompt(prompt):
    return "\n".join(
        block["text"] for block in prompt if block["type"] == "text"
    )


# ========== 正则提取总分 ==========

def test_run_ai_grading_extracts_fullwidth_score(monkeypatch):
    fake = _FakeLLM("**【总分：85分】**\n✅ 优点：内容完整")
    _patch_llm(monkeypatch, fake)

    result = _run_ai_grading(object(), _submission(), _assignment())

    assert result["score"] == 85
    assert result["content"].startswith("**【总分：85分】**")
    assert result["model_code"] == "deepseek"
    # 消息里包含格式要求与学生正文
    text = _texts_from_prompt(fake.prompt)
    assert "【总分：XX分】" in text
    assert "学生答案" in text


def test_run_ai_grading_extracts_halfwidth_score(monkeypatch):
    _patch_llm(monkeypatch, _FakeLLM("总分:90分"))

    result = _run_ai_grading(object(), _submission(), _assignment())

    assert result["score"] == 90


def test_run_ai_grading_missing_score_degrades(monkeypatch):
    _patch_llm(monkeypatch, _FakeLLM("内容完整，但回复里没有写总分"))

    result = _run_ai_grading(object(), _submission(), _assignment())

    assert result["score"] is None
    assert result["content"].startswith("⚠️ AI 评分解析失败，请教师人工复核。")
    assert "没有写总分" in result["content"]


def test_run_ai_grading_coerces_block_content(monkeypatch):
    """多模态模型 content 为分块列表时仍能解析出总分。"""
    _patch_llm(
        monkeypatch,
        _FakeLLM([{"type": "text", "text": "总分：75分\n不错"}]),
    )

    result = _run_ai_grading(object(), _submission(), _assignment())

    assert result["score"] == 75
    assert "不错" in result["content"]


def test_run_ai_grading_missing_model_type_fails_controlled(monkeypatch):
    """缺少 ai_rule.modelType：受控失败，不发起模型调用。"""
    from app.agent.contracts import AGENT_RULE_MODEL_NOT_CONFIGURED
    from app.tasks.grading import GradingRoutingError

    assignment = _assignment(**{"modelType": None})
    ai_rule = assignment.ai_rule
    del ai_rule["modelType"]
    assignment.ai_rule = ai_rule

    with pytest.raises(GradingRoutingError) as exc_info:
        _run_ai_grading(object(), _submission(), assignment)

    assert exc_info.value.code == AGENT_RULE_MODEL_NOT_CONFIGURED


# ========== 文本归一化 ==========

def test_coerce_text_content_handles_string_and_blocks():
    assert _coerce_text_content("纯文本") == "纯文本"
    assert _coerce_text_content([
        {"type": "text", "text": "第一段"},
        {"type": "image_url", "image_url": {"url": "data:..."}},
    ]) == "第一段"
    assert _coerce_text_content("") == ""


def test_strip_html_removes_tags():
    assert _strip_html("<p>你好<b>同学</b></p>") == "你好同学"
    assert _strip_html("  行首空格  ") == "行首空格"
    assert _strip_html("") == ""


# ========== 提示词构建 ==========

def test_grading_prompt_includes_dimensions_and_format():
    assignment = _assignment(criteria=[
        {"id": "a", "title": "内容", "maxScore": 60, "instructions": "要点齐全"},
        {"id": "b", "title": "表达", "maxScore": 40, "instructions": ""},
    ])

    text = _grading_prompt_text(assignment)

    assert "1. 内容（满分60）：要点齐全" in text
    assert "2. 表达（满分40）" in text
    assert "【输出格式要求】" in text
    assert "**1. 维度名：XX分**" in text
    assert "✅ 开头" in text


def test_grading_prompt_without_criteria_omits_dimension_list():
    text = _grading_prompt_text(_assignment(prompt="请按实验要求评分"))

    assert "请按实验要求评分" in text
    assert "评分维度（" not in text
    assert "【输出格式要求】" in text


# ========== 媒体消息构建 ==========

def test_build_media_items_includes_requirement_reference_and_body(tmp_path):
    (tmp_path / "ref.txt").write_text("参考答案要点", encoding="utf-8")
    assignment = _assignment(
        description="<p>请完成实验报告</p>",
        attachments=[{
            "fileName": "ref.txt",
            "fileUrl": "/uploads/ref.txt",
            "fileType": "text/plain",
        }],
    )
    submission = _submission(content="<p>学生实验内容</p>")

    items = _build_media_items(submission, assignment, str(tmp_path))
    texts = "\n".join(item["text"] for item in items if item["type"] == "text")

    assert "请完成实验报告" in texts
    assert "参考答案要点" in texts
    assert "学生实验内容" in texts


def test_build_media_items_includes_image_url_block(tmp_path):
    chart = tmp_path / "chart.png"
    Image.new("RGB", (4, 4), color="red").save(chart)
    assignment = _assignment(attachments=[])
    submission = _submission(content="", attachments=[{
        "fileName": "chart.png",
        "fileUrl": "/uploads/chart.png",
        "fileType": "image/png",
    }])

    items = _build_media_items(submission, assignment, str(tmp_path))
    image_blocks = [item for item in items if item["type"] == "image_url"]

    assert image_blocks
    assert image_blocks[0]["image_url"]["url"].startswith("data:image/")


def test_build_media_items_truncates_long_text(tmp_path):
    long_body = "长" * 10000
    submission = _submission(content=long_body)

    items = _build_media_items(submission, _assignment(), str(tmp_path))
    body_text = next(
        item["text"]
        for item in items
        if item["type"] == "text" and "学生作业正文" in item["text"]
    )

    # 单块截断到 8000 字符
    assert len(body_text) < 8200
    assert "长" * 8000 in body_text
