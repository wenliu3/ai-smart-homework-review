"""统一模型网关（规格 11.1/11.2）。

职责：从 AiModel 读取激活配置；按能力档位创建并缓存 LangChain ChatModel；
应用温度/超时/输出上限；密钥脱敏。缓存键：
(agent_profile, model_id, model_updated_at, prompt_version)
——管理员修改默认模型配置后 updated_at 变化，缓存立即失效，无需 TTL。
"""
import logging
import threading

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from sqlalchemy.orm import Session

from ..core.exceptions import BizException
from ..models import AiModel
from .contracts import ModelProfile

logger = logging.getLogger(__name__)

MODEL_NOT_CONFIGURED_CODE = 10016

# 能力档位参数（规格 11.2）：初期共用默认物理模型，参数按档位隔离
PROFILE_SETTINGS: dict[ModelProfile, dict] = {
    ModelProfile.ROUTER: {"temperature": 0.1, "max_tokens": 500, "timeout": 15},
    ModelProfile.GENERAL: {"temperature": 0.3, "max_tokens": 2000, "timeout": 40},
    ModelProfile.VISION_GRADER: {"temperature": 0.2, "max_tokens": 4000, "timeout": 120},
    ModelProfile.REVIEWER: {"temperature": 0.1, "max_tokens": 2000, "timeout": 40},
}


def mask_secret(value: str | None) -> str:
    """密钥脱敏：保留首尾各 4 位；长度 <= 8 全掩码；空值返回空串。"""
    if not value:
        return ""
    if len(value) <= 8:
        return "****"
    return f"{value[:4]}****{value[-4:]}"


class ModelGateway:
    """创建并缓存 ChatModel。线程安全（LangGraph 会在后台线程执行工具）。"""

    def __init__(self) -> None:
        self._cache: dict[tuple, BaseChatModel] = {}
        self._lock = threading.Lock()

    def get_default_config(self, db: Session) -> AiModel:
        """默认模型优先；无默认回退到任一 active 模型；无可用模型或无 Key 抛业务异常。"""
        config = db.query(AiModel).filter(
            AiModel.is_default == True,
            AiModel.status == "active",
        ).first()
        if not config:
            config = db.query(AiModel).filter(AiModel.status == "active").first()
        if not config:
            raise BizException(MODEL_NOT_CONFIGURED_CODE, "数据库中没有可用的 AI 模型，请先在系统中配置 AI 模型")
        if not (config.api_key or "").strip():
            raise BizException(MODEL_NOT_CONFIGURED_CODE, f"AI 模型「{config.name}」未配置 API Key")
        return config

    def build_cache_key(self, db: Session, profile: ModelProfile, prompt_version: str) -> tuple:
        """多维缓存键：(agent_profile, model_id, model_updated_at, prompt_version)。"""
        config = self.get_default_config(db)
        return (profile.value, config.id, config.updated_at, prompt_version)

    def get_chat_model(self, db: Session, profile: ModelProfile, prompt_version: str = "v1") -> BaseChatModel:
        config = self.get_default_config(db)
        key = (profile.value, config.id, config.updated_at, prompt_version)
        with self._lock:
            cached = self._cache.get(key)
            if cached is not None:
                return cached
            llm = init_chat_model(
                model=f"openai:{config.model_name}",
                api_key=config.api_key,
                base_url=config.base_url,
                **PROFILE_SETTINGS[profile],
            )
            # 淘汰同 profile 下配置过期的条目；不同 profile 允许共存
            stale = [k for k in self._cache if k[0] == profile.value and k != key]
            for k in stale:
                del self._cache[k]
            self._cache[key] = llm
            logger.info(
                "ChatModel 已创建: profile=%s model=%s",
                profile.value,
                config.model_name,
            )
            return llm

    def clear_cache(self) -> None:
        with self._lock:
            self._cache.clear()


# 全局单例：进程内共享缓存
model_gateway = ModelGateway()
