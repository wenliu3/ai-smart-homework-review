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

# 批改主批改/复核每次底层请求的请求超时（秒）：按 code 显式路由时，
# 不再沿用 VISION_GRADER/REVIEWER 的 120/40 秒长超时。
GRADING_LLM_TIMEOUT = 35

# 能力档位参数（规格 11.2）：初期共用默认物理模型，参数按档位隔离
PROFILE_SETTINGS: dict[ModelProfile, dict] = {
    ModelProfile.ROUTER: {"temperature": 0.1, "max_tokens": 500, "timeout": 15},
    ModelProfile.GENERAL: {"temperature": 0.3, "max_tokens": 2000, "timeout": 40},
    ModelProfile.VISION_GRADER: {"temperature": 0.2, "max_tokens": 4000, "timeout": 120},
    ModelProfile.REVIEWER: {"temperature": 0.1, "max_tokens": 2000, "timeout": 40},
}

# DeepSeek V4 系列默认开启 thinking 模式，而 thinking 模式不支持 LangChain 的
# 强制 tool_choice（结构化输出必需），会返回 400 "Thinking mode does not support
# this tool_choice"。关闭 thinking 后即可正常做工具调用式结构化输出。
_DISABLE_THINKING_KWARGS = {"thinking": {"type": "disabled"}}


def _deepseek_thinking_kwargs(config: AiModel) -> dict | None:
    """DeepSeek V4 模型返回关闭 thinking 的 model_kwargs，其余模型返回 None。"""
    provider = (config.provider or "").lower()
    model_name = (config.model_name or "").lower()
    if "deepseek" in provider and "v4" in model_name:
        return _DISABLE_THINKING_KWARGS
    return None


def mask_secret(value: str | None) -> str:
    """密钥脱敏：保留首尾各 4 位；长度 <= 8 全掩码；空值返回空串。"""
    if not value:
        return ""
    if len(value) <= 8:
        return "****"
    return f"{value[:4]}****{value[-4:]}"


def get_config_by_code(db: Session, model_code: str, profile: ModelProfile) -> AiModel:
    """按 AI 规则模型 code 精确获取激活配置。

    只认 status=="active" 且 code 精确匹配的模型；不存在、未激活或
    未配置 API Key 均抛 BizException(10016)。**绝不回退默认模型**——
    独立结构化链路绑定了哪个模型就用哪个，绑定失效立即失败而不是悄悄换模型。
    """
    config = db.query(AiModel).filter(
        AiModel.status == "active",
        AiModel.code == model_code,
    ).first()
    if not config:
        raise BizException(
            MODEL_NOT_CONFIGURED_CODE,
            f"未找到启用状态下的 AI 规则模型「{model_code}」（档位 {profile.value}），请先在系统中配置并启用该模型",
        )
    if not (config.api_key or "").strip():
        raise BizException(
            MODEL_NOT_CONFIGURED_CODE,
            f"AI 规则模型「{config.name}」未配置 API Key",
        )
    return config


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

    def get_config_for_profile(
        self, db: Session, profile: ModelProfile,
    ) -> AiModel:
        """按档位选模型（规划 5.3）：绑定 > 能力标签 > 默认链。

        - profile_bindings 里显式绑定该档位的 active 模型优先；
        - VISION_GRADER 其次选带 "vision" 能力标签的 active 模型；
        - 都没有则回退 get_default_config（默认 → 任一 active）。
        """
        candidates = db.query(AiModel).filter(
            AiModel.status == "active",
        ).order_by(AiModel.id.asc()).all()
        for config in candidates:
            bindings = config.profile_bindings or {}
            if bindings.get(profile.value) and (config.api_key or "").strip():
                return config
        if profile == ModelProfile.VISION_GRADER:
            for config in candidates:
                capabilities = config.capabilities or []
                if "vision" in capabilities and (config.api_key or "").strip():
                    return config
        return self.get_default_config(db)

    def build_cache_key(self, db: Session, profile: ModelProfile, prompt_version: str) -> tuple:
        """多维缓存键：(agent_profile, model_id, model_updated_at, prompt_version)。"""
        config = self.get_config_for_profile(db, profile)
        return (profile.value, config.id, config.updated_at, prompt_version)

    def _build_llm(
        self, config: AiModel, profile: ModelProfile, *, timeout: int | None = None,
    ) -> BaseChatModel:
        """按配置创建 ChatModel 客户端（不联网）。timeout 覆盖档位默认超时。"""
        params = dict(PROFILE_SETTINGS[profile])
        if timeout is not None:
            params["timeout"] = timeout
        thinking_kwargs = _deepseek_thinking_kwargs(config)
        if thinking_kwargs:
            # 自定义 API 参数必须走 extra_body：model_kwargs 会被展开成请求参数，
            # 而 extra_body 才会作为请求体字段发给服务端（langchain-openai 约定）。
            params["extra_body"] = thinking_kwargs
        return init_chat_model(
            model=f"openai:{config.model_name}",
            api_key=config.api_key,
            base_url=config.base_url,
            # 瞬时错误（连接错误/429）同模型重试一次（规划 4.2）
            max_retries=1,
            **params,
        )

    def get_chat_model(self, db: Session, profile: ModelProfile, prompt_version: str = "v1") -> BaseChatModel:
        config = self.get_config_for_profile(db, profile)
        key = (profile.value, config.id, config.updated_at, prompt_version)
        with self._lock:
            cached = self._cache.get(key)
            if cached is not None:
                return cached
            llm = self._build_llm(config, profile)
            # 淘汰同 profile 下配置过期的条目；不同 profile 允许共存。
            # 只清理本方法产生的普通条目（键不含 "explicit" 哨兵），
            # 不误删 get_chat_model_by_code 的按 code 显式条目。
            stale = [k for k in self._cache if k[-1] != "explicit" and k[0] == profile.value and k != key]
            for k in stale:
                del self._cache[k]
            self._cache[key] = llm
            logger.info(
                "ChatModel 已创建: profile=%s model=%s",
                profile.value,
                config.model_name,
            )
            return llm

    def get_chat_model_by_code(
        self, db: Session, *, model_code: str, profile: ModelProfile, prompt_version: str = "v1",
    ) -> BaseChatModel:
        """按 AI 规则模型 code 显式路由创建并缓存 ChatModel。

        本方法专用于批改链路，对 VISION_GRADER/REVIEWER 应用 GRADING_LLM_TIMEOUT。
        与 get_chat_model 不同：这里严格按 code 取激活配置，不参与默认模型链，
        配置不存在/未激活/无 Key 时抛 10016 而**不回退默认模型**。
        缓存键在既有四元组后追加 "explicit" 哨兵，与 get_chat_model 的普通条目
        相互隔离；淘汰时也只清理同 profile 下的显式条目。
        """
        config = get_config_by_code(db, model_code, profile)
        key = (profile.value, config.id, config.updated_at, prompt_version, "explicit")
        with self._lock:
            cached = self._cache.get(key)
            if cached is not None:
                return cached
            llm = self._build_llm(
                config,
                profile,
                timeout=(
                    GRADING_LLM_TIMEOUT
                    if profile in (ModelProfile.VISION_GRADER, ModelProfile.REVIEWER)
                    else None
                ),
            )
            # 只淘汰同 profile 下的按 code 显式条目（键带 "explicit" 哨兵），
            # 保证不误删 get_chat_model 的普通条目；同档位不同 code 会互汰、不同档位可共存。
            stale = [k for k in self._cache if k[-1] == "explicit" and k[0] == profile.value and k != key]
            for k in stale:
                del self._cache[k]
            self._cache[key] = llm
            logger.info(
                "ChatModel 已创建(按 code): code=%s model=%s",
                model_code,
                config.model_name,
            )
            return llm

    def clear_cache(self) -> None:
        with self._lock:
            self._cache.clear()


# 全局单例：进程内共享缓存
model_gateway = ModelGateway()
