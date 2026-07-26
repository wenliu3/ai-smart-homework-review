/**
 * 助手新版 API 客户端（/assistant/runs/*）。
 *
 * 提供：
 * - JSON SSE 流式客户端 `streamAssistantRun`，正确处理跨网络分块、多行 data、CRLF。
 * - 安全阶段映射 `mapEventToPhase`，输出用户可读中文，不暴露内部 Agent 标识符、
 *   工具参数、数据库 ID 或 Prompt 内容。
 * - AbortController 双重取消：本地 abort + 调用 cancel API。
 *
 * 后端事件契约见 backend_python/app/agent/orchestration/events.py：
 *   run.started / route.selected / agent.started / agent.completed
 *   content.delta / run.completed / run.failed
 */
import request from "@/utils/request";

// ===================== 类型定义 =====================

/** 后端发出的 JSON SSE 事件。 */
export interface AssistantEvent {
  type: string;
  data: Record<string, any>;
}

/** 安全的运行阶段描述。 */
export interface RunPhase {
  /** 阶段键，用于去重和切换检测。 */
  key: string;
  /** 用户可读的中文标签。 */
  label: string;
}

/** streamAssistantRun 回调。 */
export interface AssistantStreamCallbacks {
  /** 收到一个 JSON 事件。 */
  onEvent?: (event: AssistantEvent) => void;
  /** 收到回答增量；第二个参数是截至当前的完整回答。 */
  onDelta?: (delta: string, accumulated: string) => void;
  /** 阶段切换（基于事件映射的安全名称）。 */
  onPhase?: (phase: RunPhase) => void;
  /** 流正常结束（run.completed 或 [DONE]）。 */
  onDone?: (finalAnswer?: string) => void;
  /** 出错（HTTP 错误、网络异常、run.failed 事件）。 */
  onError?: (error: { code: string; message: string }) => void;
}

/** 取消运行返回值。 */
export interface CancelRunResult {
  runId: string;
  status: string;
  message?: string;
}

// ===================== 安全阶段映射 =====================

/**
 * 将后端事件映射到安全的中文阶段名称。
 *
 * 安全要求（规格 19）：
 * - 阶段名称必须是用户可读的中文。
 * - 不得直接显示 teaching_data / final_reviewer 等内部标识符。
 * - 不得包含 tool_args / db_session / prompt 等字段。
 */
export function mapEventToPhase(event: AssistantEvent): RunPhase | null {
  switch (event.type) {
    case "run.started":
      return { key: "run.started", label: "正在启动" };

    case "route.selected": {
      const intent = event.data?.intent;
      if (intent === "teaching_data") {
        return { key: "route.teaching_data", label: "正在查询教学数据" };
      }
      if (intent === "teaching_strategy") {
        return { key: "route.teaching_strategy", label: "正在制定教学策略" };
      }
      if (intent === "revision") {
        return { key: "route.revision", label: "正在修订回答" };
      }
      if (intent === "learning_coach") {
        return { key: "route.learning_coach", label: "正在进行学习辅导" };
      }
      if (intent === "feedback_explanation") {
        return { key: "route.feedback_explanation", label: "正在解释学习反馈" };
      }
      if (intent === "learning_plan") {
        return { key: "route.learning_plan", label: "正在制定学习规划" };
      }
      if (intent === "prohibited_answer") {
        return { key: "route.prohibited_answer", label: "正在检查学习规范" };
      }
      if (intent === "operations_analysis") {
        return { key: "route.operations_analysis", label: "正在分析运营情况" };
      }
      if (intent === "audit_analysis") {
        return { key: "route.audit_analysis", label: "正在进行脱敏审计" };
      }
      if (intent === "model_governance") {
        return { key: "route.model_governance", label: "正在检查模型治理配置" };
      }
      return { key: "route.selected", label: "正在分析请求" };
    }

    case "agent.started": {
      const agent = event.data?.agent;
      if (agent === "teaching_data") {
        return { key: "agent.teaching_data", label: "正在查询教学数据" };
      }
      if (agent === "teaching_strategy") {
        return { key: "agent.teaching_strategy", label: "正在生成教学策略" };
      }
      if (agent === "final_reviewer") {
        return { key: "agent.final_reviewer", label: "正在复核回答" };
      }
      if (agent === "learning_coach" || agent === "learning_coach_agent") {
        return { key: "agent.learning_coach", label: "正在进行学习辅导" };
      }
      if (agent === "feedback_explainer" || agent === "feedback_explainer_agent") {
        return { key: "agent.feedback_explainer", label: "正在解释学习反馈" };
      }
      if (agent === "learning_planner" || agent === "learning_planner_agent") {
        return { key: "agent.learning_planner", label: "正在制定学习规划" };
      }
      if (agent === "student_final_reviewer") {
        return { key: "agent.student_final_reviewer", label: "正在复核学习建议" };
      }
      if (agent === "operations_analysis" || agent === "operations_analysis_agent") {
        return { key: "agent.operations_analysis", label: "正在分析运营情况" };
      }
      if (agent === "audit_analysis" || agent === "audit_analysis_agent") {
        return { key: "agent.audit_analysis", label: "正在进行脱敏审计" };
      }
      if (agent === "model_governance" || agent === "model_governance_agent") {
        return { key: "agent.model_governance", label: "正在检查模型治理配置" };
      }
      if (agent === "admin_final_reviewer") {
        return { key: "agent.admin_final_reviewer", label: "正在复核管理建议" };
      }
      return { key: "agent.started", label: "正在处理" };
    }

    case "agent.completed":
      // 不在完成时切换阶段标签，避免抖动；返回 null 让调用方忽略
      return null;

    case "content.delta":
      return { key: "content.delta", label: "正在生成回答" };

    case "approval.required":
      // 只给出阶段名，不回显 approvalId 等标识符
      return { key: "approval.required", label: "等待人工审批" };

    case "run.completed":
      return { key: "run.completed", label: "已完成" };

    case "run.failed":
      return { key: "run.failed", label: "处理失败" };

    case "run.cancelled":
      return { key: "run.cancelled", label: "已取消" };

    default:
      return null;
  }
}

// ===================== SSE 文本解析 =====================

/**
 * 将完整 SSE 文本解析为事件列表。
 *
 * 处理：
 * - \n\n 或 \r\n\r\n 分隔事件。
 * - 多行 data 字段以 \n 拼接。
 * - 跳过注释行（: 开头）和 event/id/retry 字段（阶段 1 不使用）。
 * - 忽略 [DONE] 标记。
 * - 忽略非法 JSON 行（不抛错，保证流式健壮性）。
 * - 末尾无 \n\n 的残留 buffer 中已完整解析的事件会被返回。
 */
export function parseSSEEvents(rawText: string): AssistantEvent[] {
  const events: AssistantEvent[] = [];

  // 统一处理 CRLF：将 \r\n 替换为 \n，再按 \n\n 切分
  const normalized = rawText.replace(/\r\n/g, "\n");
  const blocks = normalized.split("\n\n");

  for (const block of blocks) {
    if (!block.trim()) continue;

    const dataLines: string[] = [];
    for (const line of block.split("\n")) {
      const trimmed = line.trim();
      if (!trimmed) continue;
      if (trimmed.startsWith(":")) continue; // 注释行
      if (trimmed.startsWith("data:")) {
        // data: 后的内容可能带前导空格，按 SSE 规范应去掉一个空格
        const payload = trimmed.slice(5);
        const value = payload.startsWith(" ") ? payload.slice(1) : payload;
        dataLines.push(value);
      }
      // 忽略 event: / id: / retry: 字段（阶段 1 不使用）
    }

    if (dataLines.length === 0) continue;

    const dataStr = dataLines.join("\n");
    if (dataStr === "[DONE]") continue;

    try {
      const parsed = JSON.parse(dataStr);
      if (parsed && typeof parsed === "object" && typeof parsed.type === "string") {
        events.push({
          type: parsed.type,
          data: parsed.data ?? {},
        });
      }
    } catch {
      // 非法 JSON：忽略，保证流式健壮性
    }
  }

  return events;
}

// ===================== JSON SSE 流式客户端 =====================

const HEARTBEAT_TIMEOUT_MS = 60_000;

/**
 * 启动一次教师助手运行，以 JSON SSE 流式接收事件。
 *
 * 实现：
 * - 使用 fetch + ReadableStream 手动解析 SSE（EventSource 不支持 POST）。
 * - 跨网络分块通过 buffer 累积 + 按 \n\n 切分处理。
 * - 多行 data 字段通过 parseSSEEvents 拼接。
 * - AbortController 本地取消；取消后不触发 onError（用户主动行为）。
 * - run.failed 事件触发 onError 且不暴露内部细节。
 * - 收到 [DONE] 或 run.completed 触发 onDone。
 * - 60 秒无数据视为连接中断，自动 abort。
 *
 * @returns AbortController — 调用 .abort() 取消流。
 */
/** streamAssistantRun 可选项。 */
export interface AssistantStreamOptions {
  /** 用户当前所在页面路径（规划 5.6）：仅作为提示上下文，非权限依据。 */
  pageContext?: string;
}

export function streamAssistantRun(
  message: string,
  sessionId: string,
  callbacks: AssistantStreamCallbacks,
  options?: AssistantStreamOptions,
): AbortController {
  const controller = new AbortController();
  const baseURL = import.meta.env.VITE_API_BASE_URL || "/api";

  let heartbeatTimer: ReturnType<typeof setTimeout> | null = null;
  let completed = false;
  // 心跳超时标志：区分“心跳超时触发的 abort”与“用户主动取消的 abort”。
  let timedOut = false;
  // 401 重试标志：token 过期时借道 axios 刷新后仅重试一次，避免无限循环。
  let authRetried = false;
  // 阶段跟踪和最终答案在 streamAssistantRun 作用域中，
  // 以便 processEventBlock（在 .then 外声明）能访问。
  let lastPhaseKey: string | null = null;
  let finalAnswer: string | undefined;

  const resetHeartbeat = () => {
    if (heartbeatTimer) clearTimeout(heartbeatTimer);
    heartbeatTimer = setTimeout(() => {
      // 60 秒无数据视为连接中断：先记超时标志再 abort，
      // 让 catch 能把这次 abort 上报为 STREAM_TIMEOUT，而不是当作用户取消静默吞掉。
      timedOut = true;
      controller.abort();
    }, HEARTBEAT_TIMEOUT_MS);
  };

  const clearHeartbeat = () => {
    if (heartbeatTimer) {
      clearTimeout(heartbeatTimer);
      heartbeatTimer = null;
    }
  };

  const safeError = (code: string, message: string) => {
    if (completed) return;
    completed = true;
    clearHeartbeat();
    callbacks.onError?.({ code, message });
  };

  const safeDone = (finalAnswer?: string) => {
    if (completed) return;
    completed = true;
    clearHeartbeat();
    callbacks.onDone?.(finalAnswer);
  };

  const startFetch = () => {
    const token = localStorage.getItem("token");
    fetch(`${baseURL}/assistant/runs/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({
        message,
        session_id: sessionId,
        // 后端 CreateRunRequest 以 pageContext 别名接收
        ...(options?.pageContext ? { pageContext: options.pageContext } : {}),
      }),
      signal: controller.signal,
    })
      .then(async (response) => {
        // 401：token 可能已过期。fetch 不经过 axios 拦截器无法自动刷新，
        // 这里借道一次轻量 axios 请求（listSessions）触发 request.ts 的
        // 401 → refresh → 重试链路，刷新成功后重读 token 重试一次流式请求。
        if (response.status === 401 && !authRetried) {
          authRetried = true;
          try {
            await listSessions();
          } catch {
            // 刷新链路失败：认证确实过期，交给拦截器的登录引导，这里报错收口
            safeError("AUTH_EXPIRED", "登录状态已过期，请重新登录");
            return;
          }
          if (completed || controller.signal.aborted) return;
          resetHeartbeat();
          startFetch();
          return;
        }

        if (!response.ok) {
          // HTTP 错误：尝试读取 message，但不暴露内部细节
          let message = `HTTP ${response.status}`;
          try {
            const body = await response.json();
            if (body?.message && typeof body.message === "string") {
              message = body.message;
            }
          } catch {
            // 非 JSON 响应，保留默认 message
          }
          safeError("HTTP_ERROR", message);
          return;
        }

        const reader = response.body?.getReader();
        if (!reader) {
          safeError("STREAM_ERROR", "浏览器不支持流式读取");
          return;
        }

        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          resetHeartbeat();
          buffer += decoder.decode(value, { stream: true });

          // 按事件分隔符切分；保留最后一段未完整的 buffer
          let separator: RegExpExecArray | null;
          while ((separator = /\r?\n\r?\n/.exec(buffer)) !== null) {
            const rawEvent = buffer.slice(0, separator.index);
            buffer = buffer.slice(separator.index + separator[0].length);
            processEventBlock(rawEvent);
          }
        }

        // 处理残留 buffer（无结尾 \n\n 的情况）
        if (buffer.trim()) {
          processEventBlock(buffer);
        }

        // 只有显式终态事件才能宣告成功；自然 EOF 说明流在完成前中断。
        if (!completed) {
          safeError(
            "STREAM_INCOMPLETE",
            "助手连接在完成前中断，请重试",
          );
        }
      })
      .catch((err) => {
        clearHeartbeat();
        if (err?.name === "AbortError") {
          // 心跳超时触发的 abort 需要上报错误；用户主动取消保持静默
          if (timedOut) {
            safeError("STREAM_TIMEOUT", "连接超时，请重试");
          }
          return;
        }
        safeError("NETWORK_ERROR", err?.message || "请求失败");
      });
  };

  resetHeartbeat();
  startFetch();

  return controller;

  /** 处理单个 SSE 事件块。 */
  function processEventBlock(raw: string): void {
    const events = parseSSEEvents(raw);
    for (const event of events) {
      callbacks.onEvent?.(event);

      // 阶段切换
      const phase = mapEventToPhase(event);
      if (phase && phase.key !== lastPhaseKey) {
        lastPhaseKey = phase.key;
        callbacks.onPhase?.(phase);
      }

      // run.completed 提前触发 onDone
      if (event.type === "run.completed") {
        // 后端 final_answer_length 不直接传回答内容，调用方需从 messages 接口拉取
        safeDone(finalAnswer);
      }

      if (event.type === "content.delta") {
        const delta = event.data?.content ?? event.data?.text;
        if (typeof delta === "string" && delta.length > 0) {
          finalAnswer = `${finalAnswer ?? ""}${delta}`;
          callbacks.onDelta?.(delta, finalAnswer);
        }
      }

      if (event.type === "run.cancelled") {
        safeDone(finalAnswer);
      }

      // run.failed 触发 onError
      if (event.type === "run.failed") {
        const code = event.data?.error_code || "AGENT_CHAT_ERROR";
        const message = event.data?.message || "助手运行失败，请稍后重试";
        safeError(code, message);
      }
    }
  }
}

// ===================== 运行查询 / 取消 =====================

/**
 * 查询运行状态。
 */
export async function getRun(runId: string): Promise<{
  runId: string;
  status: string;
  finalOutput: string | null;
  errorCode: string | null;
  intent: string | null;
  startedAt: string | null;
  finishedAt: string | null;
}> {
  return request({
    url: `/assistant/runs/${runId}`,
    method: "get",
  });
}

/** 运行产物（分维度批改草案等）。 */
export interface RunArtifact {
  artifactType: string;
  schemaVersion: string;
  payload: Record<string, any> | null;
  createdAt: string | null;
}

/**
 * 列出运行产物。run 归属人可读；批改 run 的任课教师经跨库校验后可读。
 */
export async function getRunArtifacts(
  runId: string,
): Promise<{ runId: string; items: RunArtifact[] }> {
  return request({
    url: `/assistant/runs/${runId}/artifacts`,
    method: "get",
  });
}

/**
 * 取消运行。双重取消机制：本地 abort + 服务端 cancel API。
 *
 * 已完成的运行返回当前状态而不报错。
 */
export async function cancelRun(runId: string): Promise<CancelRunResult> {
  const data = await request({
    url: `/assistant/runs/${runId}/cancel`,
    method: "post",
  });
  return {
    runId: data.runId,
    status: data.status,
    message: data.message,
  };
}

// ===================== 会话接口 =====================

/** 助手会话。 */
export interface AssistantSession {
  sessionId: string;
  title: string | null;
  status: string;
  createdAt: string | null;
  updatedAt: string | null;
}

/** 助手消息。 */
export interface AssistantMessage {
  role: "user" | "assistant";
  content: string;
  runId: string | null;
  createdAt: string | null;
}

/**
 * 列出当前教师的会话。
 */
export async function listSessions(): Promise<{ sessions: AssistantSession[] }> {
  return request({
    url: "/assistant/sessions",
    method: "get",
  });
}

/**
 * 创建新会话。session_id 服务端生成。
 */
export async function createSession(
  title?: string,
): Promise<{ sessionId: string; title: string | null }> {
  return request({
    url: "/assistant/sessions",
    method: "post",
    data: title ? { title } : {},
  });
}

/**
 * 归档会话（软删除）。系统会话（批改/查重）不可删。
 */
export async function deleteSession(
  sessionId: string,
): Promise<{ sessionId: string; status: string }> {
  return request({
    url: `/assistant/sessions/${sessionId}`,
    method: "delete",
  });
}

/**
 * 重命名会话。
 */
export async function renameSession(
  sessionId: string,
  title: string,
): Promise<{ sessionId: string; title: string }> {
  return request({
    url: `/assistant/sessions/${sessionId}`,
    method: "patch",
    data: { title },
  });
}

/**
 * 对一次助手运行提交 👍(1)/👎(-1)；同 run 重复评分覆盖。
 */
export async function submitRunFeedback(
  runId: string,
  rating: 1 | -1,
  comment?: string,
): Promise<{ runId: string; rating: number }> {
  return request({
    url: `/assistant/runs/${runId}/feedback`,
    method: "post",
    data: comment ? { rating, comment } : { rating },
  });
}

/**
 * 获取会话全部消息。
 */
export async function getSessionMessages(
  sessionId: string,
): Promise<{ sessionId: string; messages: AssistantMessage[] }> {
  return request({
    url: `/assistant/sessions/${sessionId}/messages`,
    method: "get",
  });
}

// ===================== 写操作审批 =====================

export type ApprovalStatus =
  | "pending"
  | "approved"
  | "executed"
  | "rejected"
  | "expired"
  | "failed";

export type ApprovalActionType =
  | "create_assignment_draft"
  | "create_ai_rule"
  | "submit_teacher_score"
  | "update_model_config"
  | "publish_assignment"
  | "update_assignment"
  | "delete_assignment";

// approval.required 的负载解析与动作中文名是纯展示逻辑，放在
// components/assistant/approval.ts，避免组件单测 mock 本模块时被一并替换。

export interface AssistantApproval {
  approvalId: string;
  runId: string | null;
  actionType: ApprovalActionType;
  targetType: string;
  targetId: string | null;
  parameters: Record<string, unknown>;
  summary: string;
  riskLevel: "low" | "medium" | "high";
  status: ApprovalStatus;
  expiresAt: string;
  result: Record<string, unknown> | null;
}

export interface ApprovalListResult {
  items: AssistantApproval[];
}

export interface ApprovalExecutionResult {
  approvalId: string;
  status: "executed";
  result: Record<string, unknown> | null;
}

export async function listApprovals(
  status?: ApprovalStatus,
): Promise<ApprovalListResult> {
  return request({
    url: "/assistant/approvals",
    method: "get",
    params: status ? { status } : undefined,
  });
}

export async function approveAction(
  approvalId: string,
  payload: Record<string, unknown>,
): Promise<ApprovalExecutionResult> {
  return request({
    url: `/assistant/approvals/${approvalId}/approve`,
    method: "post",
    data: { payload },
  });
}

export async function rejectAction(
  approvalId: string,
  reason: string,
): Promise<AssistantApproval> {
  const normalizedReason = reason.trim();
  if (!normalizedReason) {
    throw new Error("拒绝原因不能为空");
  }
  return request({
    url: `/assistant/approvals/${approvalId}/reject`,
    method: "post",
    data: { reason: normalizedReason },
  });
}
