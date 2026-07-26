"""数据接地评测（录制回放，规划 5.7）。

回放录制的专业 Agent 结构化输出与工具结果，驱动真实的
parse_specialist_response / verify_specialist_evidence / 降级路径，
并度量回答中的数字事实是否全部来自工具结果。
"""
import json
import re

import pytest
from langchain_core.messages import ToolMessage

from app.agent.subagents.messages import (
    degraded_specialist_update,
    parse_specialist_response,
    verify_specialist_evidence,
)
from tests.evals.cases.catalog import ALL_CASES, RECORDING_GROUPS
from tests.evals import replay
from tests.evals.replay import load_recording


def _agent_result(case: dict) -> dict:
    messages = [
        ToolMessage(
            content=json.dumps(payload, ensure_ascii=False),
            tool_call_id=f"replay-{index}",
        )
        for index, payload in enumerate(case["tool_payloads"])
    ]
    return {
        "structured_response": case["structured_response"],
        "messages": messages,
    }


def _numeric_values(value, output: set[str]) -> None:
    if isinstance(value, dict):
        for nested in value.values():
            _numeric_values(nested, output)
    elif isinstance(value, list):
        for nested in value:
            _numeric_values(nested, output)
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        text = str(value)
        output.add(text[:-2] if text.endswith(".0") else text)


def test_catalog_and_recordings_total_110_cases():
    recorded = {
        name: len(load_recording(name)) for name in RECORDING_GROUPS
    }
    assert recorded == RECORDING_GROUPS
    assert len(ALL_CASES) + sum(recorded.values()) == 110


def test_recording_loader_rejects_incompatible_schema(tmp_path, monkeypatch):
    (tmp_path / "future.json").write_text(
        json.dumps({"schema_version": "2.0", "cases": []}),
        encoding="utf-8",
    )
    monkeypatch.setattr(replay, "RECORDINGS_DIR", tmp_path)
    with pytest.raises(ValueError, match="不兼容的录制格式版本"):
        replay.load_recording("future")


def test_recording_loader_accepts_minor_version_bump(tmp_path, monkeypatch):
    (tmp_path / "minor.json").write_text(
        json.dumps({"schema_version": "1.3", "cases": [{"case_id": "x"}]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(replay, "RECORDINGS_DIR", tmp_path)
    assert replay.load_recording("minor") == [{"case_id": "x"}]


def test_grounded_answers_replay_through_real_evidence_verification():
    cases = [
        case for case in load_recording("grounding")
        if case["expect"]["parsed"]
    ]
    assert cases
    grounded = 0
    for case in cases:
        result = _agent_result(case)
        response = parse_specialist_response(result)
        assert response is not None, case["case_id"]
        verified = verify_specialist_evidence(response, result)
        assert set(verified.evidence_refs) == set(
            case["expect"]["verified_evidence"],
        ), case["case_id"]
        stripped = any("已移除" in item for item in verified.limitations)
        assert stripped is case["expect"]["stripped"], case["case_id"]

        # 数字事实必须全部来自真实工具结果
        values: set[str] = set()
        _numeric_values(case["tool_payloads"], values)
        numbers = re.findall(r"\d+", case["structured_response"]["answer"])
        grounded += all(number in values for number in numbers)
    assert grounded / len(cases) >= 0.98


def test_malformed_specialist_output_degrades_safely():
    cases = [
        case for case in load_recording("grounding")
        if not case["expect"]["parsed"]
    ]
    assert cases
    for case in cases:
        result = _agent_result(case)
        assert parse_specialist_response(result) is None, case["case_id"]
    update = degraded_specialist_update()
    assert update["candidate_answer"] == ""
    assert update["limitations"]
