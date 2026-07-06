import request from "@/utils/request";

// ===================== 类型定义 =====================

/** 会话列表项 */
export interface ChatSession {
  sessionId: string;
  messageCount: number;
  lastTime: string;
  lastMessage: string;
}

/** 单条消息 */
export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  createdAt?: string;
}

// ===================== 普通接口（走 axios 封装） =====================

/**
 * 获取会话列表
 */
export function getSessions(): Promise<{ sessions: ChatSession[] }> {
  return request({
    url: "/teacher/assistant/sessions",
    method: "get",
  });
}

/**
 * 获取某个会话的全部消息
 */
export function getSessionMessages(
  sessionId: string
): Promise<{ sessionId: string; messages: ChatMessage[] }> {
  return request({
    url: `/teacher/assistant/sessions/${sessionId}/messages`,
    method: "get",
  });
}

/**
 * 删除指定会话
 */
export function deleteSession(sessionId: string): Promise<{ message: string }> {
  return request({
    url: `/teacher/assistant/sessions/${sessionId}`,
    method: "delete",
  });
}

/**
 * 清空全部会话
 */
export function deleteAllSessions(): Promise<{ message: string }> {
  return request({
    url: "/teacher/assistant/sessions/all",
    method: "delete",
  });
}

// ===================== SSE 流式对话（fetch + ReadableStream） =====================

/** SSE 回调接口 */
interface SSECallbacks {
  /** 收到一个内容片段 */
  onMessage: (chunk: string) => void;
  /** 流结束（正常完成） */
  onDone: () => void;
  /** 出错 */
  onError: (error: string) => void;
}

/**
 * 发起流式对话 — POST + SSE
 *
 * 因为浏览器原生 EventSource 只支持 GET，这里用 fetch + ReadableStream
 * 手动解析 SSE 协议（data: / event: 行）。
 *
 * @returns AbortController — 可用于中断请求
 */
export function chatStream(
  message: string,
  sessionId: string,
  callbacks: SSECallbacks
): AbortController {
  const controller = new AbortController();
  const token = localStorage.getItem("token");
  const baseURL = import.meta.env.VITE_API_BASE_URL || "/api";
  const HEARTBEAT_TIMEOUT = 60000; // 60秒无数据则视为连接中断

  let heartbeatTimer: ReturnType<typeof setTimeout> | null = null;

  const resetHeartbeat = () => {
    if (heartbeatTimer) clearTimeout(heartbeatTimer);
    heartbeatTimer = setTimeout(() => controller.abort(), HEARTBEAT_TIMEOUT);
  };

  const clearHeartbeat = () => {
    if (heartbeatTimer) {
      clearTimeout(heartbeatTimer);
      heartbeatTimer = null;
    }
  };

  resetHeartbeat(); // 开始计时

  fetch(`${baseURL}/teacher/assistant/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ message, session_id: sessionId }),
    signal: controller.signal,
  })
    .then(async (response) => {
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error("浏览器不支持流式读取");
      }

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        // 收到数据，重置心跳计时器
        resetHeartbeat();

        buffer += decoder.decode(value, { stream: true });

        // SSE 事件以 \n\n 分隔，逐个处理完整事件
        let sepIndex: number;
        while ((sepIndex = buffer.indexOf("\n\n")) !== -1) {
          const rawEvent = buffer.slice(0, sepIndex);
          buffer = buffer.slice(sepIndex + 2);
          parseSSEEvent(rawEvent, callbacks);
        }
      }
      // 处理残留
      if (buffer.trim()) {
        parseSSEEvent(buffer, callbacks);
      }
      clearHeartbeat();
      callbacks.onDone();
    })
    .catch((err) => {
      clearHeartbeat();
      if (err.name === "AbortError") return;
      callbacks.onError(err.message || "请求失败");
    });

  return controller;
}

/**
 * 解析单个 SSE 事件块
 *
 * 格式：
 *   data: 内容
 *   event: done
 *   data: [DONE]
 */
function parseSSEEvent(raw: string, callbacks: SSECallbacks) {
  let eventType = "";
  let dataLines: string[] = [];

  for (const line of raw.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    if (trimmed.startsWith("event:")) {
      eventType = trimmed.slice(6).trim();
    } else if (trimmed.startsWith("data:")) {
      dataLines.push(trimmed.slice(5).trim());
    }
  }

  const data = dataLines.join("\n");

  if (eventType === "error") {
    callbacks.onError(data || "服务端错误");
  } else if (eventType === "done") {
    // 正常结束标记，不输出内容
  } else {
    // 普通内容片段
    if (data) {
      callbacks.onMessage(data);
    }
  }
}
