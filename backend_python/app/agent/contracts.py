"""多智能体平台的结构化契约（规格文档第 10 节）。

跨 Agent / 工具 / 网关传递的关键状态必须使用这里的类型，
禁止靠自然语言拼接传递。所有跨阶段产物须带 schema_version（后续阶段补充）。
"""
from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

ActorRole = Literal["teacher", "student", "superadmin"]


class ModelProfile(str, Enum):
    """模型能力档位（规格 11.2）。初期允许映射到同一物理模型，代码与数据保持档位隔离。"""
    ROUTER = "router"
    GENERAL = "general"
    VISION_GRADER = "vision_grader"
    REVIEWER = "reviewer"
    GRADING_STRUCTURER = "grading_structurer"


class TeacherIntent(str, Enum):
    CASUAL_CHAT = "casual_chat"
    TEACHING_DATA = "teaching_data"
    TEACHING_STRATEGY = "teaching_strategy"
    # 受支持的写请求：只产出待审批草案，绝不在图内直接写业务库
    ACTION_DRAFT = "action_draft"
    # 白名单之外的高风险写请求（删除班级/学生、改账号等）：明确拒绝
    UNSUPPORTED_WRITE = "unsupported_write"


class StudentIntent(str, Enum):
    CASUAL_CHAT = "casual_chat"
    LEARNING_COACH = "learning_coach"
    FEEDBACK_EXPLANATION = "feedback_explanation"
    LEARNING_PLAN = "learning_plan"
    PROHIBITED_ANSWER = "prohibited_answer"


class AdminIntent(str, Enum):
    CASUAL_CHAT = "casual_chat"
    OPERATIONS_ANALYSIS = "operations_analysis"
    AUDIT_ANALYSIS = "audit_analysis"
    MODEL_GOVERNANCE = "model_governance"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class IntentDecision(BaseModel):
    intent: TeacherIntent
    risk_level: RiskLevel = RiskLevel.LOW
    target_agent: str
    reason: str = ""


class StudentIntentDecision(BaseModel):
    intent: StudentIntent
    risk_level: RiskLevel = RiskLevel.LOW
    target_agent: str
    reason: str = ""


class AdminIntentDecision(BaseModel):
    intent: AdminIntent
    risk_level: RiskLevel = RiskLevel.LOW
    target_agent: str
    reason: str = ""
    requires_approval: bool = False


class EvidenceRef(BaseModel):
    source_type: str = Field(min_length=1, max_length=32)
    reference: str = Field(min_length=1, max_length=255)
    summary: str = Field(min_length=1, max_length=500)


class AnalysisArtifact(BaseModel):
    schema_version: str = "v1"
    title: str = Field(min_length=1, max_length=255)
    metrics: dict = Field(default_factory=dict)
    records: list[dict] = Field(default_factory=list)
    evidence: list[EvidenceRef] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_evidence_for_facts(self):
        if (self.metrics or self.records) and not self.evidence:
            raise ValueError("包含事实数据的分析必须提供证据")
        return self


class ReviewResult(BaseModel):
    approved: bool
    issues: list[str] = Field(default_factory=list)
    revised_answer: str | None = None

    @model_validator(mode="after")
    def require_rejection_reason(self):
        if not self.approved and not self.issues:
            raise ValueError("审核拒绝时必须说明问题")
        return self


class SpecialistResponse(BaseModel):
    """专业 Agent 的结构化候选回答，供证据预检和最终审核使用。"""

    answer: str = Field(min_length=1)
    evidence_refs: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class ModelConfigProposal(BaseModel):
    """模型治理 Agent 可提出的非敏感配置变更；执行仍需人工审批。"""

    model_code: str = Field(min_length=1, max_length=64)
    changes: dict[str, Any]
    summary: str = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def reject_sensitive_or_unknown_fields(self):
        allowed = {"name", "modelName", "baseUrl", "status", "isDefault"}
        sensitive = {
            "apiKey", "api_key", "accessKey", "access_key",
            "secretKey", "secret_key", "password",
        }
        keys = set(self.changes)
        if keys & sensitive:
            raise ValueError("模型配置提案禁止包含敏感凭据")
        unknown = keys - allowed
        if unknown:
            raise ValueError(f"模型配置提案包含未授权字段: {sorted(unknown)}")
        if not keys:
            raise ValueError("模型配置提案不能为空")
        return self


class ModelGovernanceResponse(SpecialistResponse):
    """模型治理分析及可选的受控变更提案。"""

    proposal: ModelConfigProposal | None = None


# 教师可提案的写操作；`update_model_config` 属管理员，教师不得提案
TEACHER_PROPOSABLE_ACTIONS = (
    "create_assignment_draft",
    "create_ai_rule",
    "submit_teacher_score",
    "publish_assignment",
    "update_assignment",
    "delete_assignment",
)

# 身份与凭据字段由服务端注入；提案里出现即视为提权尝试
_FORBIDDEN_PROPOSAL_FIELDS = frozenset({
    "teacherId", "teacher_id", "userId", "user_id",
    "actorId", "actor_id", "studentId", "student_id",
    "role", "createdBy", "created_by",
    "apiKey", "api_key", "accessKey", "access_key",
    "secretKey", "secret_key", "password",
})


class TeacherActionProposal(BaseModel):
    """教师写操作提案；模型只能描述意图与参数，执行必须经教师人工审批。"""

    model_config = ConfigDict(extra="forbid")

    action_type: Literal[TEACHER_PROPOSABLE_ACTIONS]  # type: ignore[valid-type]
    target_id: str | None = Field(default=None, max_length=64)
    parameters: dict[str, Any]
    summary: str = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def reject_identity_or_credential_fields(self):
        leaked = set(self.parameters) & _FORBIDDEN_PROPOSAL_FIELDS
        if leaked:
            raise ValueError(f"写操作提案禁止携带身份或凭据字段: {sorted(leaked)}")
        if not self.parameters:
            raise ValueError("写操作提案参数不能为空")
        return self


class TeacherActionResponse(SpecialistResponse):
    """教师写操作 Agent 的候选回答及可选的受控写操作提案。"""

    proposal: TeacherActionProposal | None = None


class RubricCriterion(BaseModel):
    """后端认可的单个评分维度。"""

    criterion_id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=100)
    max_score: float = Field(gt=0)
    instructions: str = Field(default="", max_length=2000)


class GradingRubric(BaseModel):
    """版本化评分量表；满分由各维度上限确定。"""

    version: str = Field(min_length=1, max_length=64)
    criteria: list[RubricCriterion] = Field(min_length=1)

    @model_validator(mode="after")
    def require_unique_criterion_ids(self):
        ids = [item.criterion_id for item in self.criteria]
        if len(ids) != len(set(ids)):
            raise ValueError("评分量表的 criterion_id 必须唯一")
        return self

    @computed_field
    @property
    def total_score(self) -> float:
        return sum(item.max_score for item in self.criteria)


class CriterionGrade(BaseModel):
    """模型只能提交分项得分；不能提交可被信任的自然语言总分。"""

    criterion_id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=100)
    score: float = Field(ge=0)
    max_score: float = Field(gt=0)
    feedback: str = Field(min_length=1, max_length=4000)
    evidence_refs: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def score_must_not_exceed_maximum(self):
        if self.score > self.max_score:
            raise ValueError("评分项得分不能超过该项满分")
        return self


class GradingDraft(BaseModel):
    """批改或独立复核 Agent 的版本化结构化草案。"""

    schema_version: str = "v1"
    rubric_version: str = Field(min_length=1, max_length=64)
    items: list[CriterionGrade] = Field(min_length=1)
    summary: str = Field(min_length=1, max_length=8000)
    limitations: list[str] = Field(default_factory=list)
    # 模型自评置信度（0-1）；None 表示模型未给出（规格 §8.2）
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    # 模型主动请求人工复核时必须说明原因，供教师端展示
    requires_human_review: bool = False
    review_reasons: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_reason_when_requesting_review(self):
        if self.requires_human_review and not self.review_reasons:
            raise ValueError("请求人工复核时必须说明原因")
        return self

    @computed_field
    @property
    def total_score(self) -> float:
        return sum(item.score for item in self.items)

    @computed_field
    @property
    def max_score(self) -> float:
        return sum(item.max_score for item in self.items)

    def validate_against(self, rubric: GradingRubric) -> "GradingDraft":
        expected = {
            item.criterion_id: item.max_score
            for item in rubric.criteria
        }
        actual_ids = [item.criterion_id for item in self.items]
        if (
            len(actual_ids) != len(set(actual_ids))
            or set(actual_ids) != set(expected)
        ):
            raise ValueError("评分项必须与量表完整且唯一对应")
        if self.rubric_version != rubric.version:
            raise ValueError("批改草案的量表版本不匹配")
        for item in self.items:
            if item.max_score != expected[item.criterion_id]:
                raise ValueError("评分项满分与量表不匹配")
        return self


class GradingReportPair(BaseModel):
    schema_version: str = "v1"
    primary: GradingDraft
    review: GradingDraft
    extraction_errors: list[str] = Field(default_factory=list)


class GradingOutcome(BaseModel):
    """主批改与独立复核的确定性比较结果。"""

    schema_version: str = "v1"
    primary: GradingDraft
    review: GradingDraft
    score_difference: float = Field(ge=0)
    needs_human_review: bool
    # 转人工的机器可读原因清单（分差超限/证据缺失/模型自报低置信等）
    review_reasons: list[str] = Field(default_factory=list)


class SubmissionTextBlock(BaseModel):
    source_type: Literal["rich_text", "docx", "pdf", "text"]
    label: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1)
    evidence_ref: str = Field(min_length=1, max_length=255)
    untrusted: bool = True


class SubmissionImageRef(BaseModel):
    file_name: str = Field(min_length=1, max_length=255)
    file_path: str = Field(min_length=1)
    evidence_ref: str = Field(min_length=1, max_length=255)
    untrusted: bool = True


class NormalizedSubmissionContent(BaseModel):
    schema_version: str = "v1"
    text_blocks: list[SubmissionTextBlock] = Field(default_factory=list)
    image_refs: list[SubmissionImageRef] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class PlagiarismExplanation(BaseModel):
    """模型可生成的部分；严格禁止携带数值或违纪判定字段。"""

    model_config = ConfigDict(extra="forbid")

    explanation: str = Field(min_length=1, max_length=8000)
    review_suggestions: list[str] = Field(default_factory=list)


class PlagiarismAnalysis(BaseModel):
    """确定性引擎原始结果与模型解释分离保存。"""

    schema_version: str = "v1"
    deterministic_result: dict[str, Any]
    explanation: PlagiarismExplanation


class ActionType(str, Enum):
    CREATE_ASSIGNMENT_DRAFT = "create_assignment_draft"
    CREATE_AI_RULE = "create_ai_rule"
    SUBMIT_TEACHER_SCORE = "submit_teacher_score"
    UPDATE_MODEL_CONFIG = "update_model_config"
    PUBLISH_ASSIGNMENT = "publish_assignment"
    UPDATE_ASSIGNMENT = "update_assignment"
    DELETE_ASSIGNMENT = "delete_assignment"


class ActionDraft(BaseModel):
    """Agent 只能产出的写操作草案；哈希与幂等键由服务端计算。"""

    schema_version: str = "v1"
    action_type: ActionType
    target_type: str = Field(min_length=1, max_length=64)
    target_id: str | None = Field(default=None, max_length=128)
    parameters: dict[str, Any]
    summary: str = Field(min_length=1, max_length=1000)
    risk_level: RiskLevel
    expires_at: datetime
    payload_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    idempotency_key: str = Field(pattern=r"^[a-f0-9]{64}$")


class AgentTask(BaseModel):
    task_id: str
    agent_name: str
    instruction: str
    dependencies: list[str] = Field(default_factory=list)


class ActorContext(BaseModel):
    """服务端身份上下文（规格 10.1）。

    由认证依赖创建，绝不出现在 LLM 工具参数 Schema 中——
    LLM 既看不到也改不了这里的身份字段。
    """
    user_id: int
    role: ActorRole
    request_id: str
    session_id: str


class AgentError(BaseModel):
    """稳定的安全错误（规格 15.1）：code 供程序处理，message 面向用户。"""
    code: str
    message: str
    retryable: bool = False


class UsageSummary(BaseModel):
    """单次/单轮模型调用用量（规格 17.1）。阶段 1 由 agent_runs 落库。"""
    model_id: int
    profile: ModelProfile
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


# ---- 稳定错误码（规格 13.2 / 15.1）：SSE 与 API 对外只暴露这些 ----
AGENT_CHAT_ERROR = "AGENT_CHAT_ERROR"
AGENT_MODEL_TIMEOUT = "AGENT_MODEL_TIMEOUT"
AGENT_BUDGET_EXCEEDED = "AGENT_BUDGET_EXCEEDED"
AGENT_RUN_CANCELLED = "AGENT_RUN_CANCELLED"
# 批改任务被 Celery 软超时打断（区别于普通失败，供运营排查队列拥塞）
AGENT_GRADING_TIMEOUT = "AGENT_GRADING_TIMEOUT"
# 批改运行配置无效：作业未配置规则模型（ai_rule.modelType）或独立结构化绑定
# 损坏。任务在模型调用前受控失败，与普通批改失败（AGENT_GRADING_FAILED）区分。
AGENT_RULE_MODEL_NOT_CONFIGURED = "AGENT_RULE_MODEL_NOT_CONFIGURED"

# 兜底安全消息：绝不携带异常类型与内部细节
SAFE_CHAT_ERROR_MESSAGE = "AI 服务暂时不可用，请稍后重试"
