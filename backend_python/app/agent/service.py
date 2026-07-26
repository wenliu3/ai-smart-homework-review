"""教师助手对话编排服务：读历史 → Agent 流式执行 → 落库 → 发事件。

路由层只做参数校验与 SSE 封装（薄路由约定）。本服务是双库边界的唯一交汇点：
- 会话历史与消息读写 → PostgreSQL 会话库（AssistantSessionLocal，委托 crud.agent_chat）
- 模型配置查询与 Agent 构建 → MySQL 业务库（SessionLocal，经 agent._get_agent → ModelGateway）
"""
import json
import logging
import queue
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from pydantic import BaseModel
from langchain_core.messages import AIMessageChunk
from sqlalchemy.orm import Session

from ..assistant_database import AssistantSessionLocal
from ..config import settings
from ..core.exceptions import BizException
from ..crud import agent_chat as agent_chat_crud
from ..crud import agent_run as agent_run_crud
from ..crud import agent_session as agent_session_crud
from ..database import SessionLocal
from .contracts import (
    AGENT_BUDGET_EXCEEDED,
    AGENT_CHAT_ERROR,
    AGENT_MODEL_TIMEOUT,
    AGENT_RUN_CANCELLED,
    SAFE_CHAT_ERROR_MESSAGE,
    ActorContext,
)
from .graphs.teacher import build_teacher_graph
from .registry import get_teacher_assistant_agent
from .runtime import (
    BudgetExceeded,
    RunBudget,
    RunCancelled,
    default_run_budget,
    is_model_timeout,
)
from .tools.common import TeacherContext

logger = logging.getLogger(__name__)
# 并发上限必须低于会话库连接池容量（assistant_database.py: pool_size + max_overflow = 15），
# 否则满载时多出的 worker 会阻塞等待连接直至池超时。默认值见 config.py。
_STREAM_WORKER_SLOTS = threading.BoundedSemaphore(
    value=max(1, settings.AGENT_STREAM_MAX_CONCURRENCY),
)
_CAPACITY_ERROR_CODE = "AGENT_CAPACITY_EXCEEDED"
_CAPACITY_ERROR_MESSAGE = "助手当前请求较多，请稍后重试"

# 会话归属/权限类校验消息：本身面向用户，可安全透传到 SSE 事件；
# 其余 ValueError（含 pydantic ValidationError 等内部细节）一律脱敏。
_SAFE_OWNERSHIP_ERROR_MESSAGES = frozenset({
    "会话不存在或不属于当前用户",
    "学生会话不存在或不属于当前用户",
    "管理员会话不存在或不属于当前用户",
})


def _public_value_error_message(exc: ValueError) -> str:
    """只透传已知安全的会话归属校验消息；其余 ValueError 走兜底安全消息。"""
    message = str(exc)
    if message in _SAFE_OWNERSHIP_ERROR_MESSAGES:
        return message
    return SAFE_CHAT_ERROR_MESSAGE


def _capacity_exhausted_events() -> Iterator["ChatStreamEvent"]:
    yield ChatStreamEvent(
        event=None,
        data=json.dumps({
            "type": "run.failed",
            "data": {
                "error_code": _CAPACITY_ERROR_CODE,
                "message": _CAPACITY_ERROR_MESSAGE,
            },
        }, ensure_ascii=False),
    )
    yield ChatStreamEvent(event="done", data="[DONE]")


def _build_messages(message: str, chat_history: list | None = None) -> list:
    """构建受控的教师助手消息列表。"""
    messages = []
    for item in (chat_history or [])[-10:]:
        role = "user" if item.get("role", "user") == "user" else "assistant"
        messages.append({"role": role, "content": item.get("content", "")})
    messages.append({"role": "user", "content": message})
    return messages


def _get_agent(db: Session):
    """兼容旧聊天 API 的 Agent 获取入口。"""
    return get_teacher_assistant_agent(db)


def chat_with_agent(
    agent,
    teacher_id: int,
    message: str,
    chat_history: list | None = None,
):
    """流式输出最终 AI 文本，过滤工具结果与工具调用分片。"""
    for token, _metadata in agent.stream(
        {"messages": _build_messages(message, chat_history)},
        context=TeacherContext(teacher_id=teacher_id),
        stream_mode="messages",
    ):
        if isinstance(token, AIMessageChunk) and token.text:
            yield token.text


def chat_with_assistant(
    db: Session,
    teacher_id: int,
    message: str,
    chat_history: list | None = None,
):
    """兼容旧聊天 API 的流式入口。"""
    yield from chat_with_agent(
        _get_agent(db),
        teacher_id,
        message,
        chat_history,
    )


def chat_with_assistant_sync(
    db: Session,
    teacher_id: int,
    message: str,
    chat_history: list | None = None,
) -> str:
    """兼容旧聊天 API 的同步入口。"""
    result = _get_agent(db).invoke(
        {"messages": _build_messages(message, chat_history)},
        context=TeacherContext(teacher_id=teacher_id),
    )
    ai_messages = [item for item in result["messages"] if item.type == "ai"]
    return ai_messages[-1].content if ai_messages else "抱歉，我无法处理您的请求。"


@dataclass
class ChatStreamEvent:
    """SSE 事件。event=None 表示默认 message 事件（不带 event 字段，保持旧前端格式兼容）。"""
    event: str | None
    data: str


@dataclass
class OrchestrationResult:
    """编排服务返回值：供新版 SSE 路由消费。"""
    run_id: str
    final_answer: str
    events: list[dict] = field(default_factory=list)
    status: str = "completed"  # completed | failed | cancelled
    error_code: str | None = None


def _json_safe(value: Any) -> Any:
    """将 LangGraph 节点更新压缩为可写入 JSON 列的纯数据。"""
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {
            str(key): _json_safe(item)
            for key, item in value.items()
            # action_draft 含旧值快照与哈希，审批表已完整保存一份，
            # 不再冗余写进 agent_run_steps.output；usage 走独立列
            if key not in {
                "actor", "runtime_budget", "events",
                "recent_messages", "action_draft", "usage",
            }
        }
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _record_model_usage(usage: dict | None, calls: int) -> None:
    """把运行用量累加到默认模型的全局计数（规划 4.1）。

    统计尽力而为：模型配置缺失或库抖动都不影响运行结果。
    """
    if not usage and calls <= 0:
        return
    try:
        from ..crud import ai_model as ai_model_crud
        from .gateway import model_gateway

        with SessionLocal() as db:
            config = model_gateway.get_default_config(db)
            ai_model_crud.increment_usage(
                db,
                model_id=config.id,
                calls=calls,
                tokens=int((usage or {}).get("total_tokens", 0)),
            )
    except Exception:
        logger.warning("模型用量统计写入失败", exc_info=True)


def _merge_usage(left: dict | None, right: dict | None) -> dict:
    left = left or {}
    right = right or {}
    return {
        key: left.get(key, 0) + right.get(key, 0)
        for key in {*left, *right}
    }


class _StreamRunContext:
    """一次图流式消费的可变追踪状态；异常时由调用方收口 running Step。"""

    def __init__(self) -> None:
        self.running_step_ids: dict[str, int] = {}
        self.node_started_at: dict[str, float] = {}
        self.active_node: str | None = None
        self.last_boundary = time.monotonic()
        self.run_usage: dict = {}
        self.usage_calls = 0

    def close_running(
        self, sdb: Session, user_id: int, *, status: str, error_code: str,
    ) -> None:
        for step_id in self.running_step_ids.values():
            agent_run_crud.finish_step(
                sdb, step_id, user_id, status=status, error_code=error_code,
            )
        self.running_step_ids.clear()


def _consume_graph_stream(
    graph,
    initial_state: dict,
    *,
    sdb: Session,
    run_id: str,
    user_id: int,
    emit,
    supervisor_node: str,
    ctx: "_StreamRunContext",
) -> dict:
    """消费 stream(updates+custom)：节点事件透传、Step 生命周期、usage 聚合。

    学生/管理员真流式路径共用（规划 5.4，对齐教师路径语义）；
    异常向上抛，由调用方分类并用 ctx.close_running 收口。
    """
    final_state = dict(initial_state)
    for part in graph.stream(
        initial_state,
        stream_mode=["updates", "custom"],
        version="v2",
    ):
        if part["type"] == "custom":
            event = part["data"]
            if event.get("type") == "agent.started":
                agent_name = event.get("data", {}).get("agent")
                if agent_name:
                    ctx.node_started_at[agent_name] = time.monotonic()
                    ctx.active_node = agent_name
                    ctx.running_step_ids[agent_name] = agent_run_crud.start_step(
                        sdb,
                        run_id=run_id,
                        user_id=user_id,
                        node_name=agent_name,
                    ).id
            emit(event)
            continue
        if part["type"] != "updates":
            continue
        for node_name, update in part["data"].items():
            final_state.update(update)
            now_ts = time.monotonic()
            started = ctx.node_started_at.pop(node_name, ctx.last_boundary)
            step_usage = update.get("usage") or {}
            if step_usage:
                ctx.run_usage = _merge_usage(ctx.run_usage, step_usage)
                ctx.usage_calls += 1
            evidence = update.get(
                "evidence_refs", final_state.get("evidence_refs", []),
            )
            duration = max(1, int((now_ts - started) * 1000))
            running_id = ctx.running_step_ids.pop(node_name, None)
            if running_id is not None:
                agent_run_crud.finish_step(
                    sdb, running_id, user_id,
                    status="completed",
                    output=_json_safe(update),
                    evidence_refs=_json_safe(evidence),
                    usage=step_usage or None,
                    duration_ms=duration,
                )
            else:
                agent_run_crud.append_step(
                    sdb,
                    run_id=run_id,
                    user_id=user_id,
                    node_name=node_name,
                    status="completed",
                    output=_json_safe(update),
                    evidence_refs=_json_safe(evidence),
                    usage=step_usage or None,
                    duration_ms=duration,
                )
            if node_name == ctx.active_node:
                ctx.active_node = None
            ctx.last_boundary = now_ts
            if node_name == supervisor_node:
                decision = update.get("intent")
                if decision is not None:
                    agent_run_crud.update_run_route(
                        sdb,
                        run_id=run_id,
                        user_id=user_id,
                        intent=decision.intent.value,
                        risk_level=decision.risk_level.value,
                    )
    return final_state


# 单个内容分片的长度上限（段落过长时兜底切块）
_DELTA_CHUNK_CHARS = 400


def _emit_content_deltas(emit, final_answer: str) -> None:
    """审核通过后按段落逐段放行（决策 D5）。

    严禁在审核/finalize 之前调用——「先流出、审核否决后撤回」被明确禁止。
    分隔符保留在片段内，客户端顺序拼接可精确还原全文。
    """
    if not final_answer:
        return
    paragraphs = final_answer.split("\n\n")
    for index, paragraph in enumerate(paragraphs):
        piece = paragraph + (
            "\n\n" if index < len(paragraphs) - 1 else ""
        )
        while piece:
            chunk, piece = piece[:_DELTA_CHUNK_CHARS], piece[_DELTA_CHUNK_CHARS:]
            if chunk:
                emit({"type": "content.delta", "data": {"content": chunk}})


def _build_session_summary(user_message: str, final_answer: str) -> str:
    """确定性会话摘要：截断拼接，不调用 LLM（规格阶段 1.5 明令）。"""
    question = (user_message or "").strip().replace("\n", " ")[:120]
    answer = (final_answer or "").strip().replace("\n", " ")[:240]
    if not question and not answer:
        return ""
    return f"问：{question}｜答：{answer}"


def _write_session_summary(
    sdb: Session,
    *,
    session_id: str,
    user_id: int,
    user_message: str,
    final_answer: str,
) -> None:
    """finalize 后写回摘要；失败只告警，绝不影响本轮回答（规划 4.4）。"""
    summary = _build_session_summary(user_message, final_answer)
    if not summary:
        return
    try:
        agent_session_crud.update_summary(
            sdb, session_id, user_id=user_id, summary=summary,
        )
    except Exception:
        logger.warning("会话摘要写回失败: session_id=%s", session_id, exc_info=True)


def _build_artifacts(final_state: dict) -> list[dict]:
    artifacts: list[dict] = []
    specialist_response = final_state.get("specialist_response")
    if specialist_response is not None:
        artifacts.append({
            "artifact_type": "specialist_response",
            "schema_version": "v1",
            "payload": _json_safe(specialist_response),
        })
    review = final_state.get("review")
    if review is not None:
        artifacts.append({
            "artifact_type": "review_result",
            "schema_version": "v1",
            "payload": _json_safe(review),
        })
    return artifacts


def _finalize_run_or_detect_cancel_race(
    sdb: Session,
    *,
    run_id: str,
    user_id: int,
    final_answer: str,
    artifacts: list[dict],
    usage: dict | None = None,
) -> bool:
    """原子 finalize 运行；命中「最后节点完成后、finalize 前被取消」的竞态时返回 True。

    finalize_run 只接受活动状态：运行在此窗口被取消会抛
    ValueError("只有活动状态可完成…")。这里吸收该竞态并交由调用方发
    run.cancelled 事件，避免把内部 CRUD 消息当作 run.failed 透传给客户端；
    其余 ValueError 原样抛出。
    """
    try:
        agent_run_crud.finalize_run(
            sdb,
            run_id=run_id,
            user_id=user_id,
            final_output=final_answer,
            assistant_message=final_answer,
            artifacts=artifacts,
            usage=usage,
        )
        return False
    except ValueError:
        sdb.expire_all()
        current = agent_run_crud.get_run(sdb, run_id, user_id=user_id)
        if current is not None and current.status == "cancelled":
            return True
        raise


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


# ========== 新版编排：教师多智能体 + PostgreSQL 运行持久化 ==========

def orchestrate_teacher_run(
    teacher_id: int,
    message: str,
    session_id: str,
    request_id: str,
    specialists: Any,
    assistant_db: Session | None = None,
    budget: RunBudget | None = None,
    event_callback=None,
    page_context: str | None = None,
) -> OrchestrationResult:
    """运行教师图并将 Run/Step/Message 持久化到 PostgreSQL。

    流程：
    1. 创建/加载 PG 会话与 Run（status=running）
    2. 追加用户消息
    3. 构造 ActorContext（服务端身份，不进入 LLM 工具参数）
    4. 构建教师图并同步调用
    5. 从 visited_nodes 持久化每个 Step
    6. 原子 finalize Run（最终助手消息 + run.completed）
    7. 失败时 fail_run + 稳定错误码（不泄露内部细节）

    specialists 由调用方注入：生产环境用 SpecialistContainer，测试用替身。
    assistant_db 可选注入：测试用，生产环境内部创建独立 PG 会话。
    """
    own_db = assistant_db is None
    sdb = assistant_db or AssistantSessionLocal()
    try:
        return _orchestrate_inner(
            sdb, teacher_id, message, session_id, request_id, specialists, budget,
            event_callback, page_context,
        )
    finally:
        if own_db:
            sdb.close()


def _orchestrate_inner(
    sdb: Session,
    teacher_id: int,
    message: str,
    session_id: str,
    request_id: str,
    specialists: Any,
    budget: RunBudget | None,
    event_callback,
    page_context: str | None = None,
) -> OrchestrationResult:
    from ..models import AgentMessage, AgentSession

    # 1. 会话归属校验（跨用户直接拒绝，不创建 Run）
    owned = (
        sdb.query(AgentSession)
        .filter(
            AgentSession.id == session_id,
            AgentSession.user_id == teacher_id,
            AgentSession.actor_role == "teacher",
            AgentSession.status == "active",
        )
        .first()
    )
    if not owned:
        raise ValueError("会话不存在或不属于当前用户")

    recent_rows = (
        sdb.query(AgentMessage)
        .filter(AgentMessage.session_id == session_id)
        .order_by(AgentMessage.created_at.desc(), AgentMessage.id.desc())
        .limit(10)
        .all()
    )
    recent_messages = [
        {"role": row.role, "content": row.content}
        for row in reversed(recent_rows)
        if row.role in ("user", "assistant")
    ]

    # 2. 创建 Run（status=running）— 先建 Run，即使后续失败也能记录
    run = agent_run_crud.create_run(
        sdb, session_id=session_id, user_id=teacher_id, intent="pending",
    )

    # 3. 追加用户消息
    agent_session_crud.append_message(
        sdb, session_id=session_id, user_id=teacher_id,
        role="user", content=message, run_id=run.id,
    )

    # 4. 构造 ActorContext（服务端身份，不进入 LLM 工具参数）
    actor = ActorContext(
        user_id=teacher_id,
        role="teacher",
        request_id=request_id,
        session_id=session_id,
    )

    # 5. 构建图并调用
    budget = budget or default_run_budget()

    def _is_cancelled() -> bool:
        sdb.expire_all()
        current = agent_run_crud.get_run(sdb, run.id, user_id=teacher_id)
        return current is None or current.status == "cancelled"

    # 聊天路径不再写 checkpoint（决策 D3）：全仓无 interrupt/恢复消费方，
    # 审批持久化走 PG 业务表；checkpointer.py 基础设施保留备用
    graph = build_teacher_graph(
        specialists,
        budget=budget,
        is_cancelled=_is_cancelled,
    )
    initial_state = {
        "run_id": run.id,
        "actor": actor,
        "user_message": message,
        "page_context": page_context or "",
        "conversation_summary": owned.summary or "",
        "recent_messages": recent_messages,
        "runtime_budget": budget,
        "visited_nodes": [],
        "events": [],
    }
    emitted_events: list[dict] = []

    def emit(event: dict) -> None:
        event = {
            "type": event["type"],
            "data": {"run_id": run.id, **event.get("data", {})},
        }
        emitted_events.append(event)
        if event_callback is not None:
            event_callback(event)

    emit({"type": "run.started", "data": {}})

    node_started_at: dict[str, float] = {}
    persisted_nodes: set[str] = set()
    # 节点开始即落 running Step，结束时原地收口（规划 4.4 生命周期）
    running_step_ids: dict[str, int] = {}
    active_node: str | None = None
    last_node_boundary = time.monotonic()
    run_usage: dict = {}
    usage_calls = 0

    try:
        final_state = dict(initial_state)
        for part in graph.stream(
            initial_state,
            stream_mode=["updates", "custom"],
            version="v2",
        ):
            if part["type"] == "custom":
                custom_event = part["data"]
                if custom_event.get("type") == "agent.started":
                    active_node = custom_event.get("data", {}).get("agent")
                    if active_node:
                        node_started_at[active_node] = time.monotonic()
                        running_step_ids[active_node] = agent_run_crud.start_step(
                            sdb,
                            run_id=run.id,
                            user_id=teacher_id,
                            node_name=active_node,
                        ).id
                emit(custom_event)
                continue
            if part["type"] != "updates":
                continue
            for node_name, update in part["data"].items():
                final_state.update(update)
                now = time.monotonic()
                started = node_started_at.pop(node_name, last_node_boundary)
                evidence_refs = update.get(
                    "evidence_refs", final_state.get("evidence_refs", []),
                )
                step_usage = update.get("usage") or {}
                if step_usage:
                    run_usage = _merge_usage(run_usage, step_usage)
                    usage_calls += 1
                running_id = running_step_ids.pop(node_name, None)
                if running_id is not None:
                    agent_run_crud.finish_step(
                        sdb,
                        running_id,
                        teacher_id,
                        status="completed",
                        output=_json_safe(update),
                        evidence_refs=_json_safe(evidence_refs),
                        usage=step_usage or None,
                        duration_ms=max(1, int((now - started) * 1000)),
                    )
                else:
                    agent_run_crud.append_step(
                        sdb,
                        run_id=run.id,
                        user_id=teacher_id,
                        node_name=node_name,
                        status="completed",
                        output=_json_safe(update),
                        evidence_refs=_json_safe(evidence_refs),
                        usage=step_usage or None,
                        duration_ms=max(1, int((now - started) * 1000)),
                    )
                persisted_nodes.add(node_name)
                if node_name == active_node:
                    active_node = None
                last_node_boundary = now
                if node_name == "teacher_supervisor":
                    decision = update.get("intent")
                    if decision is not None:
                        agent_run_crud.update_run_route(
                            sdb,
                            run_id=run.id,
                            user_id=teacher_id,
                            intent=decision.intent.value,
                            risk_level=decision.risk_level.value,
                        )
    except RunCancelled:
        for cancelled_id in running_step_ids.values():
            agent_run_crud.finish_step(
                sdb,
                cancelled_id,
                teacher_id,
                status="cancelled",
                error_code=AGENT_RUN_CANCELLED,
            )
        cancelled_event = {
            "type": "run.cancelled",
            "data": {"error_code": AGENT_RUN_CANCELLED},
        }
        emit(cancelled_event)
        return OrchestrationResult(
            run_id=run.id,
            final_answer="",
            events=emitted_events,
            status="cancelled",
            error_code=AGENT_RUN_CANCELLED,
        )
    except BudgetExceeded as e:
        logger.warning("Teacher run budget exceeded: run_id=%s code=%s", run.id, e.code)
        if active_node and active_node not in persisted_nodes:
            failed_duration = max(
                1, int((time.monotonic() - node_started_at.get(
                    active_node, last_node_boundary,
                )) * 1000),
            )
            running_id = running_step_ids.pop(active_node, None)
            if running_id is not None:
                agent_run_crud.finish_step(
                    sdb, running_id, teacher_id,
                    status="failed",
                    error_code=AGENT_BUDGET_EXCEEDED,
                    duration_ms=failed_duration,
                )
            else:
                agent_run_crud.append_step(
                    sdb, run_id=run.id, user_id=teacher_id,
                    node_name=active_node, status="failed",
                    error_code=AGENT_BUDGET_EXCEEDED,
                    duration_ms=failed_duration,
                )
        agent_run_crud.fail_run(sdb, run.id, user_id=teacher_id, error_code=AGENT_BUDGET_EXCEEDED)
        emit({"type": "run.failed", "data": {
            "error_code": AGENT_BUDGET_EXCEEDED,
        }})
        return OrchestrationResult(
            run_id=run.id,
            final_answer="",
            events=emitted_events,
            status="failed",
            error_code=AGENT_BUDGET_EXCEEDED,
        )
    except Exception as exc:
        logger.exception("Teacher run crashed: run_id=%s", run.id)
        # 模型超时映射为独立稳定码，便于与普通失败区分（规划 4.2）
        error_code = (
            AGENT_MODEL_TIMEOUT if is_model_timeout(exc) else AGENT_CHAT_ERROR
        )
        if active_node and active_node not in persisted_nodes:
            failed_duration = max(
                1, int((time.monotonic() - node_started_at.get(
                    active_node, last_node_boundary,
                )) * 1000),
            )
            running_id = running_step_ids.pop(active_node, None)
            if running_id is not None:
                agent_run_crud.finish_step(
                    sdb, running_id, teacher_id,
                    status="failed",
                    error_code=error_code,
                    duration_ms=failed_duration,
                )
            else:
                agent_run_crud.append_step(
                    sdb, run_id=run.id, user_id=teacher_id,
                    node_name=active_node, status="failed",
                    error_code=error_code,
                    duration_ms=failed_duration,
                )
        agent_run_crud.fail_run(sdb, run.id, user_id=teacher_id, error_code=error_code)
        emit({"type": "run.failed", "data": {
            "error_code": error_code,
            "message": SAFE_CHAT_ERROR_MESSAGE,
        }})
        return OrchestrationResult(
            run_id=run.id,
            final_answer=SAFE_CHAT_ERROR_MESSAGE,
            events=emitted_events,
            status="failed",
            error_code=error_code,
        )

    # 6. 原子 finalize：最终消息 + 结构化产物 + run.completed
    final_answer = final_state.get("final_answer", "")
    if _finalize_run_or_detect_cancel_race(
        sdb, run_id=run.id, user_id=teacher_id,
        final_answer=final_answer,
        artifacts=_build_artifacts(final_state),
        usage=run_usage or None,
    ):
        # 取消竞态：最后节点完成后、finalize 前用户取消了运行
        emit({
            "type": "run.cancelled",
            "data": {"error_code": AGENT_RUN_CANCELLED},
        })
        return OrchestrationResult(
            run_id=run.id,
            final_answer="",
            events=emitted_events,
            status="cancelled",
            error_code=AGENT_RUN_CANCELLED,
        )
    _emit_content_deltas(emit, final_answer)
    emit({"type": "run.completed", "data": {
        "final_answer_length": len(final_answer),
    }})
    _record_model_usage(run_usage, usage_calls)
    _write_session_summary(
        sdb, session_id=session_id, user_id=teacher_id,
        user_message=message, final_answer=final_answer,
    )

    return OrchestrationResult(
        run_id=run.id,
        final_answer=final_answer,
        events=emitted_events,
        status="completed",
        error_code=None,
    )


# ========== 新版 SSE 流：JSON 事件序列 ==========

def stream_assistant_events(
    teacher_id: int,
    message: str,
    session_id: str,
    request_id: str,
    page_context: str | None = None,
) -> Iterator[ChatStreamEvent]:
    """新版 SSE 流：将教师图运行结果以 JSON 事件序列输出。

    事件格式：每个 data 行是一个 JSON 对象 {"type": "...", "data": {...}}。
    最终发送 event: done / data: [DONE] 作为结束标记。

    异常绝不外泄类型与细节（规格 3.2/15）。
    """
    event_queue: queue.Queue = queue.Queue()
    finished = object()
    emitted_count = 0
    current_run_id: str | None = None
    completed_normally = False

    if not _STREAM_WORKER_SLOTS.acquire(blocking=False):
        yield from _capacity_exhausted_events()
        return

    def enqueue(event: dict) -> None:
        nonlocal emitted_count
        emitted_count += 1
        event_queue.put(event)

    def worker() -> None:
        try:
            # 模型配置 Session 只在工作线程内使用；业务工具仍创建独立 Session。
            with SessionLocal() as db:
                from .subagents import SubagentContainer
                specialists = SubagentContainer(db)
                result = orchestrate_teacher_run(
                    teacher_id=teacher_id,
                    message=message,
                    session_id=session_id,
                    request_id=request_id,
                    specialists=specialists,
                    event_callback=enqueue,
                    page_context=page_context,
                )
            # 测试替身或兼容实现可能不调用 callback，使用结果事件兜底。
            if emitted_count == 0:
                for event in result.events:
                    data = {"run_id": result.run_id, **event.get("data", {})}
                    enqueue({"type": event["type"], "data": data})
        except ValueError as exc:
            logger.warning("Assistant stream validation error: %s", exc)
            # 只透传会话归属类安全消息；ValidationError 等内部细节脱敏
            enqueue({
                "type": "run.failed",
                "data": {
                    "error_code": AGENT_CHAT_ERROR,
                    "message": _public_value_error_message(exc),
                },
            })
        except Exception:
            logger.exception("Assistant stream error")
            enqueue({
                "type": "run.failed",
                "data": {
                    "error_code": AGENT_CHAT_ERROR,
                    "message": SAFE_CHAT_ERROR_MESSAGE,
                },
            })
        finally:
            _STREAM_WORKER_SLOTS.release()
            event_queue.put(finished)

    thread = threading.Thread(
        target=worker,
        name=f"assistant-run-{request_id[:8]}",
        daemon=True,
    )
    try:
        thread.start()
    except Exception:
        _STREAM_WORKER_SLOTS.release()
        raise

    try:
        while True:
            try:
                item = event_queue.get(timeout=15)
            except queue.Empty:
                yield ChatStreamEvent(
                    event=None,
                    data=json.dumps({
                        "type": "heartbeat",
                        "data": {"run_id": current_run_id},
                    }, ensure_ascii=False),
                )
                continue
            if item is finished:
                completed_normally = True
                break
            if item.get("type") == "run.started":
                current_run_id = item.get("data", {}).get("run_id")
            yield ChatStreamEvent(
                event=None,
                data=json.dumps(item, ensure_ascii=False),
            )
        yield ChatStreamEvent(event="done", data="[DONE]")
    finally:
        # 客户端断开时尽力取消已知运行；条件取消不会影响已结束 Run。
        if not completed_normally and current_run_id:
            try:
                with AssistantSessionLocal() as sdb:
                    agent_run_crud.cancel_run(
                        sdb, current_run_id, user_id=teacher_id,
                    )
            except Exception:
                logger.warning(
                    "客户端断开后的运行取消失败: run_id=%s",
                    current_run_id,
                    exc_info=True,
                )


# ========== 学生角色编排 ==========

def orchestrate_student_run(
    student_id: int,
    message: str,
    session_id: str,
    request_id: str,
    subagents: Any,
    assistant_db: Session | None = None,
    budget: RunBudget | None = None,
    event_callback: Callable[[dict], None] | None = None,
    page_context: str | None = None,
) -> OrchestrationResult:
    """执行学生主管 Graph，并按角色隔离会话、步骤和 Artifact。"""

    from ..models import AgentMessage, AgentSession
    from .graphs.student import build_student_graph

    owns_db = assistant_db is None
    sdb = assistant_db or AssistantSessionLocal()
    try:
        session = sdb.query(AgentSession).filter(
            AgentSession.id == session_id,
            AgentSession.user_id == student_id,
            AgentSession.actor_role == "student",
            AgentSession.status == "active",
        ).first()
        if session is None:
            raise ValueError("学生会话不存在或不属于当前用户")
        recent_rows = (
            sdb.query(AgentMessage)
            .filter(AgentMessage.session_id == session_id)
            .order_by(AgentMessage.created_at.desc(), AgentMessage.id.desc())
            .limit(10)
            .all()
        )
        recent_messages = [
            {"role": row.role, "content": row.content}
            for row in reversed(recent_rows)
            if row.role in ("user", "assistant")
        ]
        run = agent_run_crud.create_run(
            sdb,
            session_id=session_id,
            user_id=student_id,
            intent="pending",
            graph_version="student-v1",
        )
        agent_session_crud.append_message(
            sdb,
            session_id=session_id,
            user_id=student_id,
            role="user",
            content=message,
            run_id=run.id,
        )
        emitted_events: list[dict] = []

        def emit(event: dict) -> None:
            normalized = {
                "type": event["type"],
                "data": {"run_id": run.id, **event.get("data", {})},
            }
            emitted_events.append(normalized)
            if event_callback is not None:
                event_callback(normalized)

        emit({"type": "run.started", "data": {}})
        actor = ActorContext(
            user_id=student_id,
            role="student",
            request_id=request_id,
            session_id=session_id,
        )

        def _is_cancelled() -> bool:
            sdb.expire_all()
            current = agent_run_crud.get_run(
                sdb,
                run.id,
                user_id=student_id,
            )
            return current is None or current.status == "cancelled"

        graph = build_student_graph(
            subagents,
            is_cancelled=_is_cancelled,
        )
        stream_ctx = _StreamRunContext()
        try:
            # 真流式（规划 5.4）：对齐教师路径的节点事件与 Step 生命周期
            final_state = _consume_graph_stream(
                graph,
                {
                    "run_id": run.id,
                    "actor": actor,
                    "user_message": message,
                    "page_context": page_context or "",
                    "conversation_summary": session.summary or "",
                    "recent_messages": recent_messages,
                    "runtime_budget": budget or default_run_budget(),
                    "visited_nodes": [],
                },
                sdb=sdb,
                run_id=run.id,
                user_id=student_id,
                emit=emit,
                supervisor_node="student_supervisor",
                ctx=stream_ctx,
            )
            final_answer = final_state.get("final_answer", "")
            run_usage = stream_ctx.run_usage or final_state.get("usage") or {}
            if _finalize_run_or_detect_cancel_race(
                sdb, run_id=run.id, user_id=student_id,
                final_answer=final_answer,
                artifacts=_build_artifacts(final_state),
                usage=run_usage or None,
            ):
                # 取消竞态：最后节点完成后、finalize 前用户取消了运行
                emit({
                    "type": "run.cancelled",
                    "data": {"error_code": AGENT_RUN_CANCELLED},
                })
                return OrchestrationResult(
                    run_id=run.id,
                    final_answer="",
                    events=emitted_events,
                    status="cancelled",
                    error_code=AGENT_RUN_CANCELLED,
                )
            _emit_content_deltas(emit, final_answer)
            emit({"type": "run.completed", "data": {}})
            _record_model_usage(run_usage, stream_ctx.usage_calls)
            _write_session_summary(
                sdb, session_id=session_id, user_id=student_id,
                user_message=message, final_answer=final_answer,
            )
            return OrchestrationResult(
                run_id=run.id,
                final_answer=final_answer,
                events=emitted_events,
            )
        except RunCancelled:
            stream_ctx.close_running(
                sdb, student_id,
                status="cancelled", error_code=AGENT_RUN_CANCELLED,
            )
            emit({
                "type": "run.cancelled",
                "data": {"error_code": AGENT_RUN_CANCELLED},
            })
            return OrchestrationResult(
                run_id=run.id,
                final_answer="",
                events=emitted_events,
                status="cancelled",
                error_code=AGENT_RUN_CANCELLED,
            )
        except BudgetExceeded as e:
            # 与教师路径一致：预算超限落稳定错误码，不误记为通用错误
            logger.warning(
                "Student run budget exceeded: run_id=%s code=%s", run.id, e.code,
            )
            stream_ctx.close_running(
                sdb, student_id,
                status="failed", error_code=AGENT_BUDGET_EXCEEDED,
            )
            agent_run_crud.fail_run(
                sdb,
                run.id,
                user_id=student_id,
                error_code=AGENT_BUDGET_EXCEEDED,
            )
            emit({"type": "run.failed", "data": {
                "error_code": AGENT_BUDGET_EXCEEDED,
            }})
            return OrchestrationResult(
                run_id=run.id,
                final_answer="",
                events=emitted_events,
                status="failed",
                error_code=AGENT_BUDGET_EXCEEDED,
            )
        except Exception as exc:
            logger.exception("Student run crashed: run_id=%s", run.id)
            error_code = (
                AGENT_MODEL_TIMEOUT
                if is_model_timeout(exc)
                else AGENT_CHAT_ERROR
            )
            stream_ctx.close_running(
                sdb, student_id, status="failed", error_code=error_code,
            )
            agent_run_crud.fail_run(
                sdb,
                run.id,
                user_id=student_id,
                error_code=error_code,
            )
            failed_event = {
                "type": "run.failed",
                "data": {
                    "error_code": error_code,
                    "message": SAFE_CHAT_ERROR_MESSAGE,
                },
            }
            emit(failed_event)
            return OrchestrationResult(
                run_id=run.id,
                final_answer=SAFE_CHAT_ERROR_MESSAGE,
                events=emitted_events,
                status="failed",
                error_code=error_code,
            )
    finally:
        if owns_db:
            sdb.close()


def _stream_role_events(
    *,
    actor_id: int,
    request_id: str,
    orchestrate: Callable[..., OrchestrationResult],
    orchestrate_kwargs: dict[str, Any],
    container_factory: Callable[[Session], Any],
) -> Iterator[ChatStreamEvent]:
    """Run a role graph in a worker and expose events/heartbeats immediately."""

    event_queue: queue.Queue = queue.Queue()
    finished = object()
    emitted_count = 0
    current_run_id: str | None = None
    completed_normally = False

    if not _STREAM_WORKER_SLOTS.acquire(blocking=False):
        yield from _capacity_exhausted_events()
        return

    def enqueue(event: dict) -> None:
        nonlocal emitted_count
        emitted_count += 1
        event_queue.put(event)

    def worker() -> None:
        try:
            with SessionLocal() as db:
                result = orchestrate(
                    **orchestrate_kwargs,
                    subagents=container_factory(db),
                    event_callback=enqueue,
                )
            if emitted_count == 0:
                for event in result.events:
                    enqueue(event)
        except ValueError as exc:
            logger.warning("Role assistant stream validation error: %s", exc)
            # 只透传会话归属类安全消息；ValidationError 等内部细节脱敏
            enqueue({
                "type": "run.failed",
                "data": {
                    "error_code": AGENT_CHAT_ERROR,
                    "message": _public_value_error_message(exc),
                },
            })
        except Exception:
            logger.exception("Role assistant stream error")
            enqueue({
                "type": "run.failed",
                "data": {
                    "error_code": AGENT_CHAT_ERROR,
                    "message": SAFE_CHAT_ERROR_MESSAGE,
                },
            })
        finally:
            _STREAM_WORKER_SLOTS.release()
            event_queue.put(finished)

    thread = threading.Thread(
        target=worker,
        name=f"assistant-role-run-{request_id[:8]}",
        daemon=True,
    )
    try:
        thread.start()
    except Exception:
        _STREAM_WORKER_SLOTS.release()
        raise

    try:
        while True:
            try:
                item = event_queue.get(timeout=15)
            except queue.Empty:
                yield ChatStreamEvent(
                    event=None,
                    data=json.dumps({
                        "type": "heartbeat",
                        "data": {"run_id": current_run_id},
                    }, ensure_ascii=False),
                )
                continue
            if item is finished:
                completed_normally = True
                break
            if item.get("type") == "run.started":
                current_run_id = item.get("data", {}).get("run_id")
            yield ChatStreamEvent(
                event=None,
                data=json.dumps(item, ensure_ascii=False),
            )
        yield ChatStreamEvent(event="done", data="[DONE]")
    finally:
        if not completed_normally and current_run_id:
            try:
                with AssistantSessionLocal() as sdb:
                    agent_run_crud.cancel_run(
                        sdb,
                        current_run_id,
                        user_id=actor_id,
                    )
            except Exception:
                logger.warning(
                    "Failed to cancel disconnected role run: run_id=%s",
                    current_run_id,
                    exc_info=True,
                )


def stream_student_events(
    student_id: int,
    message: str,
    session_id: str,
    request_id: str,
    page_context: str | None = None,
) -> Iterator[ChatStreamEvent]:
    """学生 Graph 的 JSON SSE 入口。"""

    from .subagents import StudentSubagentContainer

    yield from _stream_role_events(
        actor_id=student_id,
        request_id=request_id,
        orchestrate=orchestrate_student_run,
        orchestrate_kwargs={
            "student_id": student_id,
            "message": message,
            "session_id": session_id,
            "request_id": request_id,
            "page_context": page_context,
        },
        container_factory=StudentSubagentContainer,
    )


def orchestrate_admin_run(
    admin_id: int,
    message: str,
    session_id: str,
    request_id: str,
    subagents: Any,
    assistant_db: Session | None = None,
    budget: RunBudget | None = None,
    event_callback: Callable[[dict], None] | None = None,
    page_context: str | None = None,
) -> OrchestrationResult:
    """执行管理员主管 Graph，并按角色隔离持久化运行记录。"""
    from ..models import AgentMessage, AgentSession
    from .graphs.admin import build_admin_graph

    owns_db = assistant_db is None
    sdb = assistant_db or AssistantSessionLocal()
    try:
        session = sdb.query(AgentSession).filter(
            AgentSession.id == session_id,
            AgentSession.user_id == admin_id,
            AgentSession.actor_role == "superadmin",
            AgentSession.status == "active",
        ).first()
        if session is None:
            raise ValueError("管理员会话不存在或不属于当前用户")
        recent_rows = (
            sdb.query(AgentMessage)
            .filter(AgentMessage.session_id == session_id)
            .order_by(AgentMessage.created_at.desc(), AgentMessage.id.desc())
            .limit(10)
            .all()
        )
        recent_messages = [
            {"role": row.role, "content": row.content}
            for row in reversed(recent_rows)
            if row.role in ("user", "assistant")
        ]
        run = agent_run_crud.create_run(
            sdb,
            session_id=session_id,
            user_id=admin_id,
            intent="pending",
            graph_version="admin-v1",
        )
        agent_session_crud.append_message(
            sdb,
            session_id=session_id,
            user_id=admin_id,
            role="user",
            content=message,
            run_id=run.id,
        )
        emitted_events: list[dict] = []

        def emit(event: dict) -> None:
            normalized = {
                "type": event["type"],
                "data": {"run_id": run.id, **event.get("data", {})},
            }
            emitted_events.append(normalized)
            if event_callback is not None:
                event_callback(normalized)

        emit({"type": "run.started", "data": {}})
        def _is_cancelled() -> bool:
            sdb.expire_all()
            current = agent_run_crud.get_run(
                sdb,
                run.id,
                user_id=admin_id,
            )
            return current is None or current.status == "cancelled"

        graph = build_admin_graph(
            subagents,
            is_cancelled=_is_cancelled,
        )
        actor = ActorContext(
            user_id=admin_id,
            role="superadmin",
            request_id=request_id,
            session_id=session_id,
        )
        stream_ctx = _StreamRunContext()
        try:
            # 真流式（规划 5.4）：对齐教师路径的节点事件与 Step 生命周期
            final_state = _consume_graph_stream(
                graph,
                {
                    "run_id": run.id,
                    "actor": actor,
                    "user_message": message,
                    "page_context": page_context or "",
                    "conversation_summary": session.summary or "",
                    "recent_messages": recent_messages,
                    "runtime_budget": budget or default_run_budget(),
                    "visited_nodes": [],
                },
                sdb=sdb,
                run_id=run.id,
                user_id=admin_id,
                emit=emit,
                supervisor_node="admin_supervisor",
                ctx=stream_ctx,
            )
            final_answer = final_state.get("final_answer", "")
            run_usage = stream_ctx.run_usage or final_state.get("usage") or {}
            if _finalize_run_or_detect_cancel_race(
                sdb, run_id=run.id, user_id=admin_id,
                final_answer=final_answer,
                artifacts=_build_artifacts(final_state),
                usage=run_usage or None,
            ):
                # 取消竞态：最后节点完成后、finalize 前用户取消了运行
                emit({
                    "type": "run.cancelled",
                    "data": {"error_code": AGENT_RUN_CANCELLED},
                })
                return OrchestrationResult(
                    run_id=run.id,
                    final_answer="",
                    events=emitted_events,
                    status="cancelled",
                    error_code=AGENT_RUN_CANCELLED,
                )
            _emit_content_deltas(emit, final_answer)
            emit({"type": "run.completed", "data": {}})
            _record_model_usage(run_usage, stream_ctx.usage_calls)
            _write_session_summary(
                sdb, session_id=session_id, user_id=admin_id,
                user_message=message, final_answer=final_answer,
            )
            return OrchestrationResult(
                run_id=run.id,
                final_answer=final_answer,
                events=emitted_events,
            )
        except RunCancelled:
            stream_ctx.close_running(
                sdb, admin_id,
                status="cancelled", error_code=AGENT_RUN_CANCELLED,
            )
            emit({
                "type": "run.cancelled",
                "data": {"error_code": AGENT_RUN_CANCELLED},
            })
            return OrchestrationResult(
                run_id=run.id,
                final_answer="",
                events=emitted_events,
                status="cancelled",
                error_code=AGENT_RUN_CANCELLED,
            )
        except BudgetExceeded as e:
            # 与教师路径一致：预算超限落稳定错误码，不误记为通用错误
            logger.warning(
                "Admin run budget exceeded: run_id=%s code=%s", run.id, e.code,
            )
            stream_ctx.close_running(
                sdb, admin_id,
                status="failed", error_code=AGENT_BUDGET_EXCEEDED,
            )
            agent_run_crud.fail_run(
                sdb,
                run.id,
                user_id=admin_id,
                error_code=AGENT_BUDGET_EXCEEDED,
            )
            emit({"type": "run.failed", "data": {
                "error_code": AGENT_BUDGET_EXCEEDED,
            }})
            return OrchestrationResult(
                run_id=run.id,
                final_answer="",
                events=emitted_events,
                status="failed",
                error_code=AGENT_BUDGET_EXCEEDED,
            )
        except Exception as exc:
            logger.exception("Admin run crashed: run_id=%s", run.id)
            error_code = (
                AGENT_MODEL_TIMEOUT
                if is_model_timeout(exc)
                else AGENT_CHAT_ERROR
            )
            stream_ctx.close_running(
                sdb, admin_id, status="failed", error_code=error_code,
            )
            agent_run_crud.fail_run(
                sdb,
                run.id,
                user_id=admin_id,
                error_code=error_code,
            )
            failed_event = {
                "type": "run.failed",
                "data": {
                    "error_code": error_code,
                    "message": SAFE_CHAT_ERROR_MESSAGE,
                },
            }
            emit(failed_event)
            return OrchestrationResult(
                run_id=run.id,
                final_answer=SAFE_CHAT_ERROR_MESSAGE,
                events=emitted_events,
                status="failed",
                error_code=error_code,
            )
    finally:
        if owns_db:
            sdb.close()


def stream_admin_events(
    admin_id: int,
    message: str,
    session_id: str,
    request_id: str,
    page_context: str | None = None,
) -> Iterator[ChatStreamEvent]:
    """管理员 Graph 的 JSON SSE 入口。"""
    from .subagents import AdminSubagentContainer

    yield from _stream_role_events(
        actor_id=admin_id,
        request_id=request_id,
        orchestrate=orchestrate_admin_run,
        orchestrate_kwargs={
            "admin_id": admin_id,
            "message": message,
            "session_id": session_id,
            "request_id": request_id,
            "page_context": page_context,
        },
        container_factory=AdminSubagentContainer,
    )
