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
