"""教师 Graph 共享状态。"""
from typing import TypedDict

from ..contracts import (
    ActorContext,
    AnalysisArtifact,
    IntentDecision,
    ReviewResult,
    SpecialistResponse,
)


class TeacherAgentState(TypedDict, total=False):
    """教师图状态。

    注意：LangGraph 会静默丢弃 schema 之外的输入键与节点更新键，
    编排层传入或节点返回的每个键都必须在此声明。
    """
    run_id: str
    actor: ActorContext
    user_message: str
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
    # 受支持写请求产出的待审批草案（ActionDraft）与落库后的审批 ID
    action_draft: object
    approval_id: str
