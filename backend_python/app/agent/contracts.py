"""多智能体平台的结构化契约（规格文档第 10 节）。

跨 Agent / 工具 / 网关传递的关键状态必须使用这里的类型，
禁止靠自然语言拼接传递。所有跨阶段产物须带 schema_version（后续阶段补充）。
"""
from enum import Enum
from typing import Literal

from pydantic import BaseModel

ActorRole = Literal["teacher", "student", "superadmin"]


class ModelProfile(str, Enum):
    """模型能力档位（规格 11.2）。初期允许映射到同一物理模型，代码与数据保持档位隔离。"""
    ROUTER = "router"
    GENERAL = "general"
    VISION_GRADER = "vision_grader"
    REVIEWER = "reviewer"


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

# 兜底安全消息：绝不携带异常类型与内部细节
SAFE_CHAT_ERROR_MESSAGE = "AI 服务暂时不可用，请稍后重试"
