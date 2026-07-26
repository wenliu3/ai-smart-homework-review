"""安全评测（录制回放，规划 5.7）。

学生侧：回放录制的候选回答与审核输出，驱动真实的
student_final_reviewer 节点（确定性拒绝路径不应触碰模型）。
管理员侧：录制的密钥必须经真实 mask_secret 后不可还原。
"""
from types import SimpleNamespace

from app.agent.contracts import StudentIntent
from app.agent.gateway import mask_secret
from app.agent.subagents.student_final_reviewer import create_node
from tests.evals.replay import ReplayAgent, ReplayRegistry, load_recording


def test_student_reviewer_replay_matches_recorded_verdicts():
    cases = load_recording("safety_student")
    assert len(cases) == 10
    for case in cases:
        recorded = case["recorded_review"]
        if recorded is None:
            responses = []
        elif isinstance(recorded, str):
            # 录制为字符串 = 模型未按契约返回结构化结果
            responses = [None]
        else:
            responses = [recorded]
        agent = ReplayAgent(responses)
        node = create_node(
            db=None,
            registry=ReplayRegistry({"student_final_reviewer": agent}),
        )
        state = {
            "candidate_answer": case["candidate_answer"],
            "intent": SimpleNamespace(
                intent=StudentIntent(case["intent"]),
            ),
            "evidence_refs": case["evidence_refs"],
        }
        update = node(state)
        review = update["review"]
        expect = case["expect"]
        assert review.approved is expect["approved"], case["case_id"]
        if expect["issue_keyword"]:
            assert any(
                expect["issue_keyword"] in issue for issue in review.issues
            ), (case["case_id"], review.issues)
        # 确定性拒绝路径必须零模型调用；模型路径必须恰好回放一次
        assert (len(agent.prompts) > 0) is expect["uses_model"], case["case_id"]


def test_admin_secret_masking_replay_never_leaks_secret():
    cases = load_recording("safety_admin")
    assert len(cases) == 5
    for case in cases:
        raw = case["raw_secret"]
        masked = mask_secret(raw or None)
        assert masked == case["expected_masked"], case["case_id"]
        if len(raw) > 8:
            assert raw[4:-4] not in masked, case["case_id"]
            assert raw not in masked
        elif raw:
            assert raw not in masked, case["case_id"]
