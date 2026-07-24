"""LangChain 1.0 教师助手 Agent — 基于 create_agent + ToolRuntime(官方context注入机制)"""
import time
from sqlalchemy.orm import Session
from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessageChunk
from langchain.agents import create_agent
from ..models import AiModel
from .tools import ALL_TOOLS, TeacherContext   # TeacherContext 从 tools.py 里定义的地方导入

SYSTEM_PROMPT = """你是教学助手AI，服务于教师用户，通过工具查询数据库中的教学数据。
能力：查班级/班级学生、作业/提交情况、按姓名或学号查学生成绩、教师看板统计、待批改列表。

规则：
- 工具返回结果里的ID只是给你自己串联查询用的（先按名称/标题查列表拿到ID，再用ID查详情），最终回答里绝不能出现"ID:5"这类内容，用名称代替
- 不编造数据；工具查不到就如实说，并提示老师换个关键词
- 涉及学生信息注意隐私，不暴露密码等敏感字段
- 超出工具能力范围的请求（发通知、改数据等），如实告知做不到，不要假装完成

格式：
- 展示在窄悬浮面板里，不用emoji装饰标题
- 多条记录、字段整齐时用markdown表格；单条简单结果一两句话说完，不用硬套格式
- 同一个数字不要又列表/表格说一遍、又用文字重复统计一遍
- 别习惯性用"需要我帮您...吗？"结尾，除非接下来的操作明显有用
- 标题#、列表-/*后面要带空格，否则前端渲染不出来
"""


# agent 进程级缓存：避免每次请求都查 AiModel + init_chat_model + create_agent
# 缓存 key 为默认模型 id（管理员切换默认模型时立即失效），TTL 60s 兜底配置变更
_agent_cache: dict = {"agent": None, "ts": 0.0, "model_id": None}
_AGENT_CACHE_TTL = 60  # 秒


def _build_messages(message: str, chat_history: list = None) -> list:
    """构建消息列表（和你原来完全一样，不用动）"""
    messages = []
    if chat_history:
        for msg in chat_history[-10:]:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            messages.append({"role": "user" if role == "user" else "assistant", "content": content})
    messages.append({"role": "user", "content": message})
    return messages


def _get_agent(db: Session):
    """获取 agent，带进程级缓存。

    缓存命中条件：agent 已构建 + 默认模型 id 未变 + 未过 TTL。
    - 管理员切换默认模型 → 立即重建（model_id 变化）
    - 管理员修改 api_key 等字段 → 最多 60s 后生效（TTL 兜底）

    缓存命中时只查一次 AiModel.id（轻量），未命中时查完整配置重建。
    LLM 客户端是独立 httpx 连接、不依赖 db session，缓存复用线程安全。
    """
    now = time.time()
    cached = _agent_cache

    # 轻量查询：只取 id，判断缓存是否失效
    current_model_id = db.query(AiModel.id).filter(AiModel.is_default == True).scalar()
    if not current_model_id:
        current_model_id = db.query(AiModel.id).filter(AiModel.status == "active").scalar()
    if not current_model_id:
        raise RuntimeError("数据库中没有可用的 AI 模型，请先在系统中配置 AI 模型")

    model_changed = cached["model_id"] != current_model_id
    ttl_expired = now - cached["ts"] >= _AGENT_CACHE_TTL

    if cached["agent"] is not None and not model_changed and not ttl_expired:
        return cached["agent"]

    # 缓存失效：查完整配置重建 agent
    model_config = db.query(AiModel).filter(AiModel.id == current_model_id).first()
    if not (model_config.api_key or "").strip():
        raise RuntimeError(f"AI 模型「{model_config.name}」未配置 API Key")

    llm = init_chat_model(
        model=f"openai:{model_config.model_name}",
        api_key=model_config.api_key,
        base_url=model_config.base_url,
        temperature=0.3,   # 查询/汇总类任务用低温度提高确定性，降低幻觉
        max_tokens=2000,
    )
    agent = create_agent(
        model=llm,
        tools=ALL_TOOLS,
        system_prompt=SYSTEM_PROMPT,
        context_schema=TeacherContext,
    )
    _agent_cache["agent"] = agent
    _agent_cache["ts"] = now
    _agent_cache["model_id"] = current_model_id
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
        # 只处理 AIMessageChunk：
        # - ToolMessage（工具函数原始返回的字符串）会被这个 isinstance 判断挡掉，不会泄露到前端
        # - 工具调用请求的分片 .text 通常是空的，也会被 and 后面这个条件挡掉
        if isinstance(token, AIMessageChunk) and token.text:
            yield token.text   # 用 .text 而不是 .content —— 部分模型的 content 可能是结构化内容块列表，不一定是纯字符串


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