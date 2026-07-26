"""批改与查重评测（录制回放，规划 5.7）。

回放录制的批改模型结构化输出，驱动真实的 invoke_with_repair
（校验 → 修复重试 → 降级转人工）与多模态消息构造；查重录制
直接跑真实文本查重管线并核对人工标注。
"""
import base64

from app.agent.contracts import GradingRubric, SubmissionImageRef
from app.agent.graphs.grading import GRADING_AGENT_NODE
from app.agent.subagents.grading import invoke_with_repair
from app.agent.tools.content import (
    MAX_IMAGE_BYTES,
    build_grading_message_content,
    normalize_submission_content,
)
from app.plagiarism import run_plagiarism_check
from tests.evals.replay import ASSETS_DIR, ReplayAgent, load_recording

# 人工评分校准门槛：AI 总分与人工总分之差不得超过满分的 10%
_HUMAN_GAP_RATIO = 0.10


def _build_state(case: dict, tmp_path=None) -> dict:
    rubric = GradingRubric.model_validate(case["rubric"])
    normalized = normalize_submission_content(case["submission_text"], None)
    for name in case.get("image_assets", []):
        normalized.image_refs.append(SubmissionImageRef(
            file_name=name,
            file_path=str(ASSETS_DIR / name),
            evidence_ref=f"submission:image:{len(normalized.image_refs) + 1}",
        ))
    if case.get("oversized_image") and tmp_path is not None:
        big = tmp_path / "oversized.png"
        with big.open("wb") as handle:
            # 稀疏写一个字节即可让 st_size 超限，不必真占磁盘
            handle.seek(MAX_IMAGE_BYTES)
            handle.write(b"\0")
        normalized.image_refs.append(SubmissionImageRef(
            file_name="oversized.png",
            file_path=str(big),
            evidence_ref="submission:image:99",
        ))
    return {
        "rubric": rubric,
        "normalized_content": normalized,
        "assignment_description": case.get("assignment_description", ""),
        "reference_materials": "",
    }


def test_grading_replay_matches_human_rating_within_10_percent(tmp_path):
    cases = load_recording("grading")
    assert len(cases) == 20
    for case in cases:
        state = _build_state(case, tmp_path)
        agent = ReplayAgent(case["model_responses"])
        result = invoke_with_repair(
            agent, state, reviewer=False, stage=GRADING_AGENT_NODE,
        )
        human = case["human_rating"]
        if human["requires_human_review"]:
            # 一致性：录制标注需人工复核 ⇔ 真实管线降级为 grading_failure
            failure = result.get("grading_failure")
            assert failure is not None, case["case_id"]
            assert failure["stage"] == GRADING_AGENT_NODE
            assert failure["error"]
            assert len(agent.prompts) == 2, case["case_id"]
        else:
            draft = result.get("grading_draft")
            assert draft is not None, (case["case_id"], result)
            full_marks = state["rubric"].total_score
            gap = abs(draft.total_score - human["total_score"])
            assert gap <= _HUMAN_GAP_RATIO * full_marks, (
                case["case_id"], draft.total_score, human["total_score"],
            )


def test_repair_retry_feeds_validation_error_back_to_model(tmp_path):
    cases = [
        case for case in load_recording("grading")
        if len(case["model_responses"]) == 2
        and not case["human_rating"]["requires_human_review"]
    ]
    assert cases
    for case in cases:
        state = _build_state(case, tmp_path)
        agent = ReplayAgent(case["model_responses"])
        result = invoke_with_repair(
            agent, state, reviewer=False, stage=GRADING_AGENT_NODE,
        )
        assert result.get("grading_draft") is not None, case["case_id"]
        assert len(agent.prompts) == 2
        retry_message = agent.prompts[1]["messages"][-1]
        assert "校验错误" in retry_message.content
        assert "上一次输出" in retry_message.content


def test_multimodal_recordings_flow_real_images_into_model_message(tmp_path):
    cases = [
        case for case in load_recording("grading")
        if case.get("image_assets")
    ]
    assert len(cases) >= 3
    saw_oversized = False
    for case in cases:
        state = _build_state(case, tmp_path)
        blocks = build_grading_message_content(state["normalized_content"])
        image_blocks = [
            block for block in blocks if block["type"] == "image_url"
        ]
        assert image_blocks, case["case_id"]
        for block in image_blocks:
            url = block["image_url"]["url"]
            assert url.startswith("data:image/png;base64,")
            decoded = base64.b64decode(url.split(",", 1)[1])
            assert decoded.startswith(b"\x89PNG"), case["case_id"]
        if case.get("oversized_image"):
            saw_oversized = True
            placeholders = [
                block for block in blocks
                if block["type"] == "text"
                and "图片过大未传入模型" in block["text"]
            ]
            assert placeholders, case["case_id"]
            # 超大图绝不能以 image_url 形式进入消息
            assert all(
                "oversized" not in block["image_url"]["url"]
                for block in image_blocks
            )
    assert saw_oversized


def test_plagiarism_recordings_replay_through_real_pipeline():
    cases = load_recording("plagiarism")
    assert len(cases) == 10
    for case in cases:
        result = run_plagiarism_check(
            case["submissions"],
            template_text=case.get("template_text"),
        )
        rows = {
            row["studentNumber"]: row
            for row in result.get("results", [])
        }
        flagged = sorted(
            number for number, row in rows.items()
            if "疑似" in row.get("status", "")
        )
        skipped = sorted(
            item["studentNumber"] for item in result.get("skipped", [])
        )
        expect = case["expect"]
        assert flagged == sorted(expect["flagged"]), (case["case_id"], flagged)
        assert skipped == sorted(expect["skipped"]), (case["case_id"], skipped)
        for number in expect["clean"]:
            if number in rows:
                assert "疑似" not in rows[number].get("status", ""), (
                    case["case_id"], number,
                )
