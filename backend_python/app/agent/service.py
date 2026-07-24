"""教师助手对话编排服务：读历史 → Agent 流式执行 → 落库 → 发事件。

路由层只做参数校验与 SSE 封装（薄路由约定）。本服务是双库边界的唯一交汇点：
- 会话历史与消息读写 → PostgreSQL 会话库（AssistantSessionLocal，委托 crud.agent_chat）
- 模型配置查询与 Agent 构建 → MySQL 业务库（SessionLocal，经 agent._get_agent → ModelGateway）
"""
import logging
from collections.abc import Iterator
from dataclasses import dataclass

from ..assistant_database import AssistantSessionLocal
from ..core.exceptions import BizException
from ..crud import agent_chat as agent_chat_crud
from ..database import SessionLocal
from .agent import _get_agent, chat_with_agent
from .contracts import SAFE_CHAT_ERROR_MESSAGE

logger = logging.getLogger(__name__)


@dataclass
class ChatStreamEvent:
    """SSE 事件。event=None 表示默认 message 事件（不带 event 字段，保持旧前端格式兼容）。"""
    event: str | None
    data: str


def stream_chat_events(teacher_id: int, message: str, session_id: str) -> Iterator[ChatStreamEvent]:
    full_answer = ""
    saved = False
    try:
        # 短事务读历史（PG 会话库）+构建 agent（MySQL 业务库查模型配置）：
        # LLM 客户端是独立 httpx 连接，不依赖 db session；
        # SSE 流式生成可能耗时 30s+，不能让请求在此其间持有连接池连接。
        with AssistantSessionLocal() as sdb:
            chat_history = agent_chat_crud.get_recent_messages(sdb, teacher_id, session_id)
        with SessionLocal() as db:
            agent = _get_agent(db)

        for content in chat_with_agent(agent, teacher_id, message, chat_history):
            full_answer += content
            yield ChatStreamEvent(event=None, data=content)

        # 流正常结束：先落库再发 done，保证前端收到 done 时数据已入库
        if full_answer:
            with AssistantSessionLocal() as sdb:
                agent_chat_crud.save_exchange(sdb, teacher_id, session_id, message, full_answer)
            saved = True
        yield ChatStreamEvent(event="done", data="[DONE]")
    except BizException as e:
        # 业务异常的 message 本身面向用户（如"未配置 AI 模型"），可直接透传
        logger.warning("Assistant biz error: code=%s message=%s", e.code, e.message)
        yield ChatStreamEvent(event="error", data=e.message)
    except Exception:
        # 兜底异常绝不外泄类型与细节（可能含内部实现与敏感信息，规格 3.2/15）
        logger.error("Agent chat error", exc_info=True)
        yield ChatStreamEvent(event="error", data=SAFE_CHAT_ERROR_MESSAGE)
    finally:
        # 异常中断时用独立 session 兜底存储（正常流程已存过则跳过）
        if full_answer and not saved:
            try:
                with AssistantSessionLocal() as sdb:
                    agent_chat_crud.save_exchange(sdb, teacher_id, session_id, message, full_answer)
            except Exception:
                logger.error("助手消息兜底存储失败", exc_info=True)
