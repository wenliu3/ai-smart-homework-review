"""教师 Graph 共享状态。"""
from typing import Annotated, TypedDict

from ..contracts import (
    ActorContext,
    AnalysisArtifact,
    IntentDecision,
    ReviewResult,
    SpecialistResponse,
)




def _accumulate_usage(left: dict, right: dict) -> dict:
    """usage 通道 reducer：多个节点各自回传用量，按键累加成运行总量。"""
    left = left or {}
    right = right or {}
    return {
        key: left.get(key, 0) + right.get(key, 0)
        for key in {*left, *right}
    }


class TeacherAgentState(TypedDict, total=False):
    """教师图状态。

    注意：LangGraph 会静默丢弃 schema 之外的输入键与节点更新键，
    编排层传入或节点返回的每个键都必须在此声明。
    """
    run_id: str
    actor: ActorContext
    user_message: str
    page_context: str
    conversation_summary: str
    recent_messages: list[dict]
    intent: IntentDecision
    artifact: AnalysisArtifact
    specialist_response: SpecialistResponse
    evidence_refs: list[str]
    limitations: list[str]
    runtime_budget: object
    candidate_answer: str
    review: ReviewResult
    revision_count: int
    last_specialist: str
    final_answer: str
    visited_nodes: list[str]
    events: list[dict]
    # 各节点回传的模型用量，按键累加为运行总量（规划 4.1）
    usage: Annotated[dict, _accumulate_usage]
    # 受支持写请求产出的待审批草案（ActionDraft）与落库后的审批 ID
    action_draft: object
    approval_id: str
