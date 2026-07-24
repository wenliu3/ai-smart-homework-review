"""LangChain 1.0 教师助手 Agent — 模型创建与 Prompt 统一走 ModelGateway / PromptRegistry"""
import threading

from sqlalchemy.orm import Session
from langchain_core.messages import AIMessageChunk
from langchain.agents import create_agent

from .contracts import ModelProfile
from .prompts import get_prompt
from .services.model_gateway import model_gateway
from .tools import ALL_TOOLS, TeacherContext   # TeacherContext 从 tools.py 里定义的地方导入

# agent 进程级缓存：key = (profile, model_id, model_updated_at, prompt_version)
# 管理员修改默认模型配置或 Prompt 发版后 key 变化，旧 agent 自动淘汰（取代旧的 60s TTL）
_agent_cache: dict = {}
_agent_cache_lock = threading.Lock()


def _build_messages(message: str, chat_history: list = None) -> list:
    """构建消息列表"""
    messages = []
    if chat_history:
        for msg in chat_history[-10:]:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            messages.append({"role": "user" if role == "user" else "assistant", "content": content})
    messages.append({"role": "user", "content": message})
    return messages


def _get_agent(db: Session):
    """获取教师助手 agent（进程级缓存，线程安全）。

    ChatModel 由 ModelGateway 创建（统一温度/超时/输出上限/缓存），
    系统 Prompt 由 PromptRegistry 提供（当前版本 teacher_assistant:v1）。
    double-checked locking：命中无锁返回，miss 持锁构建（与 ModelGateway 一致）。
    """
    prompt = get_prompt("teacher_assistant")
    cache_key = model_gateway.build_cache_key(db, ModelProfile.GENERAL, prompt.version)
    agent = _agent_cache.get(cache_key)
    if agent is not None:
        return agent
    with _agent_cache_lock:
        agent = _agent_cache.get(cache_key)
        if agent is not None:
            return agent
        llm = model_gateway.get_chat_model(db, ModelProfile.GENERAL, prompt_version=prompt.version)
        _agent_cache.clear()   # 同一时刻只有一个 (默认模型, prompt版本) 组合生效
        agent = create_agent(
            model=llm,
            tools=ALL_TOOLS,
            system_prompt=prompt.content,
            context_schema=TeacherContext,
        )
        _agent_cache[cache_key] = agent
        return agent


def chat_with_assistant(db: Session, teacher_id: int, message: str, chat_history: list = None):
    """流式输出 — 只 yield 大模型最终生成的纯文本，过滤掉工具调用分片和工具原始返回结果"""
    agent = _get_agent(db)
    yield from chat_with_agent(agent, teacher_id, message, chat_history)


def chat_with_agent(agent, teacher_id: int, message: str, chat_history: list = None):
    """流式输出 — 使用预构建的 agent，不持有 db session。

    适用于 SSE 长连接场景：调用方先用短事务构建 agent，
    再用本函数流式输出，避免长时间占用连接池连接。
    """
    messages = _build_messages(message, chat_history)

    for token, metadata in agent.stream(
        {"messages": messages},
        context=TeacherContext(teacher_id=teacher_id),   # ← 权限边界从这里传入，LLM 看不到
        stream_mode="messages",
    ):
        # 只处理 AIMessageChunk：ToolMessage 与工具调用分片不会泄露到前端
        if isinstance(token, AIMessageChunk) and token.text:
            yield token.text


def chat_with_assistant_sync(db: Session, teacher_id: int, message: str, chat_history: list = None) -> str:
    """同步版本 — 一次性返回完整回复"""
    agent = _get_agent(db)
    messages = _build_messages(message, chat_history)

    result = agent.invoke(
        {"messages": messages},
        context=TeacherContext(teacher_id=teacher_id),
    )
    ai_messages = [m for m in result["messages"] if m.type == "ai"]
    return ai_messages[-1].content if ai_messages else "抱歉，我无法处理您的请求。"
