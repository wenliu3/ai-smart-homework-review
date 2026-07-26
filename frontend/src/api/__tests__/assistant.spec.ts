/**
 * 助手新版 SSE 客户端测试（任务 6-1）。
 *
 * 覆盖：
 * - 跨网络分块的 SSE 解析。
 * - 多行 data 字段拼接。
 * - 阶段事件映射（run.started / route.selected / agent.started / agent.completed / run.completed）。
 * - 错误事件、安全降级和完成事件。
 * - AbortController 取消。
 * - cancel API 调用。
 *
 * 这些测试先于实现编写，运行时应因模块不存在而失败。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

// Mock @/utils/request 以避免引入 router/store/element-plus 全链。
// streamAssistantRun 不经过 request（直接用 fetch），cancelRun/getRun 经过。
const requestMock = vi.fn();
vi.mock("@/utils/request", () => ({
  default: (config: any) => requestMock(config),
}));

import {
  parseSSEEvents,
  mapEventToPhase,
  streamAssistantRun,
  cancelRun,
  listApprovals,
  approveAction,
  rejectAction,
  type AssistantEvent,
} from "../assistant";

// ========== parseSSEEvents：SSE 文本 → 事件对象数组 ==========

describe("parseSSEEvents", () => {
  it("解析单个 data 行 JSON 事件", () => {
    const raw = "data: {\"type\":\"run.started\",\"data\":{}}\n\n";
    const events = parseSSEEvents(raw);
    expect(events).toHaveLength(1);
    expect(events[0].type).toBe("run.started");
    expect(events[0].data).toEqual({});
  });

  it("解析多个连续事件", () => {
    const raw = [
      "data: {\"type\":\"run.started\",\"data\":{}}",
      "",
      "data: {\"type\":\"route.selected\",\"data\":{\"intent\":\"teaching_data\"}}",
      "",
      "data: {\"type\":\"run.completed\",\"data\":{\"final_answer_length\":42}}",
      "",
      "data: [DONE]",
      "",
      "",
    ].join("\n");
    const events = parseSSEEvents(raw);
    expect(events.map((e) => e.type)).toEqual([
      "run.started",
      "route.selected",
      "run.completed",
    ]);
  });

  it("拼接多行 data 字段（同一事件内多行 data 用换行连接）", () => {
    // 模拟后端将超长 JSON 拆成两行 data
    const raw = [
      "data: {\"type\":\"content.delta\",\"data\":",
      'data: {"text":"hello"}}',
      "",
      "",
    ].join("\n");
    const events = parseSSEEvents(raw);
    expect(events).toHaveLength(1);
    expect(events[0].type).toBe("content.delta");
    expect(events[0].data.text).toBe("hello");
  });

  it("忽略非法 JSON 数据行但不抛错", () => {
    const raw = "data: not-json\n\ndata: {\"type\":\"run.started\",\"data\":{}}\n\n";
    const events = parseSSEEvents(raw);
    expect(events).toHaveLength(1);
    expect(events[0].type).toBe("run.started");
  });

  it("忽略 [DONE] 标记不当作事件", () => {
    const raw = "data: [DONE]\n\n";
    const events = parseSSEEvents(raw);
    expect(events).toEqual([]);
  });

  it("跳过注释行（以 : 开头）", () => {
    const raw = ": heartbeat\n\ndata: {\"type\":\"run.started\",\"data\":{}}\n\n";
    const events = parseSSEEvents(raw);
    expect(events).toHaveLength(1);
    expect(events[0].type).toBe("run.started");
  });

  it("处理末尾不完整的 buffer（无结尾 \\n\\n）返回已完整解析的事件", () => {
    const raw = "data: {\"type\":\"run.started\",\"data\":{}}\n\ndata: {\"type\":\"route";
    const events = parseSSEEvents(raw);
    expect(events).toHaveLength(1);
    expect(events[0].type).toBe("run.started");
  });

  it("处理 CRLF 行尾（\\r\\n\\r\\n）", () => {
    const raw = "data: {\"type\":\"run.started\",\"data\":{}}\r\n\r\n";
    const events = parseSSEEvents(raw);
    expect(events).toHaveLength(1);
    expect(events[0].type).toBe("run.started");
  });
});

// ========== mapEventToPhase：事件 → 安全阶段名称 ==========

describe("mapEventToPhase", () => {
  it("run.started 映射到启动阶段", () => {
    const phase = mapEventToPhase({ type: "run.started", data: {} });
    expect(phase).not.toBeNull();
    expect(phase!.label).toBeTruthy();
    expect(typeof phase!.label).toBe("string");
  });

  it("route.selected + teaching_data 映射到查询教学数据阶段", () => {
    const phase = mapEventToPhase({
      type: "route.selected",
      data: { intent: "teaching_data" },
    });
    expect(phase).not.toBeNull();
    expect(phase!.label).toContain("教学数据");
  });

  it("route.selected + teaching_strategy 映射到教学策略阶段", () => {
    const phase = mapEventToPhase({
      type: "route.selected",
      data: { intent: "teaching_strategy" },
    });
    expect(phase).not.toBeNull();
    expect(phase!.label).toContain("策略");
  });

  it("agent.started 映射到对应 Agent 阶段", () => {
    const phase = mapEventToPhase({
      type: "agent.started",
      data: { agent: "teaching_data" },
    });
    expect(phase).not.toBeNull();
  });

  it("agent.started + final_reviewer 映射到复核阶段", () => {
    const phase = mapEventToPhase({
      type: "agent.started",
      data: { agent: "final_reviewer" },
    });
    expect(phase).not.toBeNull();
    expect(phase!.label).toContain("复核");
  });

  it("run.completed 映射到完成阶段", () => {
    const phase = mapEventToPhase({ type: "run.completed", data: {} });
    expect(phase).not.toBeNull();
  });

  it("run.failed 映射到失败阶段", () => {
    const phase = mapEventToPhase({ type: "run.failed", data: {} });
    expect(phase).not.toBeNull();
  });

  it("run.cancelled 映射到已取消阶段", () => {
    const phase = mapEventToPhase({ type: "run.cancelled", data: {} });
    expect(phase).toEqual({ key: "run.cancelled", label: "已取消" });
  });

  it("未知事件类型返回 null（不抛错）", () => {
    const phase = mapEventToPhase({ type: "unknown.event", data: {} });
    expect(phase).toBeNull();
  });

  it("阶段名称不暴露内部 Agent 标识符（如 teaching_data 原文）", () => {
    // 安全要求：阶段标签必须是用户可读的中文，不是英文 snake_case 标识符
    const phase = mapEventToPhase({
      type: "agent.started",
      data: { agent: "teaching_data" },
    });
    expect(phase).not.toBeNull();
    expect(phase!.label).not.toMatch(/teaching_data/);
    expect(phase!.label).not.toMatch(/final_reviewer/);
  });

  it("阶段名称不包含数据库 ID / 工具参数 / Prompt 内容", () => {
    const phase = mapEventToPhase({
      type: "agent.started",
      data: {
        agent: "teaching_data",
        tool_args: { teacher_id: 42, db_session: "internal" },
        prompt: "You are a teaching data assistant...",
      },
    });
    expect(phase).not.toBeNull();
    expect(phase!.label).not.toContain("42");
    expect(phase!.label).not.toContain("teacher_id");
    expect(phase!.label).not.toContain("db_session");
    expect(phase!.label).not.toContain("You are");
  });
});

// ========== streamAssistantRun：JSON SSE 客户端 ==========

describe("streamAssistantRun", () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.useRealTimers();
  });

  /** 构造一个伪 ReadableStream，按 chunks 推送字符串。 */
  function makeChunkedStream(chunks: string[]): ReadableStream<Uint8Array> {
    const encoder = new TextEncoder();
    let i = 0;
    return new ReadableStream<Uint8Array>({
      pull(controller) {
        if (i < chunks.length) {
          controller.enqueue(encoder.encode(chunks[i++]));
        } else {
          controller.close();
        }
      },
    });
  }

  /** 构造一个伪成功响应，直接暴露 stream 避免被 Response 包装层干扰。 */
  function makeSuccessResponse(sseText: string, chunks: string[] = [sseText]) {
    const stream = makeChunkedStream(chunks.length ? chunks : [sseText]);
    return {
      ok: true,
      status: 200,
      body: stream,
      headers: new Headers({ "Content-Type": "text/event-stream" }),
      async json() {
        return JSON.parse(sseText);
      },
      async text() {
        return sseText;
      },
    } as unknown as Response;
  }

  it("跨网络分块正确拼接并触发 onEvent / onPhase / onDone", async () => {
    // 将完整 SSE 文本拆成 3 个分块，模拟 TCP 分片
    const fullText = [
      "data: {\"type\":\"run.started\",\"data\":{}}",
      "",
      "data: {\"type\":\"route.selected\",\"data\":{\"intent\":\"teaching_data\"}}",
      "",
      "data: {\"type\":\"agent.started\",\"data\":{\"agent\":\"teaching_data\"}}",
      "",
      "data: {\"type\":\"agent.completed\",\"data\":{\"agent\":\"teaching_data\"}}",
      "",
      "data: {\"type\":\"run.completed\",\"data\":{\"final_answer_length\":10}}",
      "",
      "data: [DONE]",
      "",
      "",
    ].join("\n");

    // 故意从 JSON 中间切分，验证 buffer 拼接
    const chunks = [
      fullText.slice(0, 80),
      fullText.slice(80, 200),
      fullText.slice(200),
    ];

    globalThis.fetch = vi.fn().mockResolvedValue(makeSuccessResponse(fullText, chunks));

    const events: AssistantEvent[] = [];
    const phases: string[] = [];
    let doneCalled = false;

    await new Promise<void>((resolve) => {
      streamAssistantRun("我有几个班级", "sess-test-001", {
        onEvent: (e) => {
          events.push(e);
          if (e.type === "run.completed") {
            doneCalled = true;
            resolve();
          }
        },
        onPhase: (p) => phases.push(p.label),
        onDone: () => resolve(),
        onError: () => resolve(),
      });
    });

    expect(events.map((e) => e.type)).toEqual([
      "run.started",
      "route.selected",
      "agent.started",
      "agent.completed",
      "run.completed",
    ]);
    expect(phases.length).toBeGreaterThan(0);
    expect(doneCalled).toBe(true);
  });

  it("解析多行 data 字段", async () => {
    const raw = [
      'data: {"type":"content.delta","data":',
      'data: {"text":"hello world"}}',
      "",
      "data: {\"type\":\"run.completed\",\"data\":{}}",
      "",
      "data: [DONE]",
      "",
      "",
    ].join("\n");

    globalThis.fetch = vi.fn().mockResolvedValue(makeSuccessResponse(raw));

    const events: AssistantEvent[] = [];
    await new Promise<void>((resolve) => {
      streamAssistantRun("hi", "sess-test-002", {
        onEvent: (e) => {
          events.push(e);
          if (e.type === "run.completed") resolve();
        },
        onDone: () => resolve(),
        onError: () => resolve(),
      });
    });

    const delta = events.find((e) => e.type === "content.delta");
    expect(delta).toBeDefined();
    expect(delta!.data.text).toBe("hello world");
  });

  it("逐段累计 content.delta 并把完整答案交给 onDone", async () => {
    const raw = [
      'data: {"type":"run.started","data":{"run_id":"run-stream-1"}}',
      "",
      'data: {"type":"content.delta","data":{"content":"hello"}}',
      "",
      'data: {"type":"content.delta","data":{"content":" world"}}',
      "",
      'data: {"type":"run.completed","data":{"run_id":"run-stream-1"}}',
      "",
      "data: [DONE]",
      "",
      "",
    ].join("\n");
    globalThis.fetch = vi.fn().mockResolvedValue(makeSuccessResponse(raw));

    const deltas: Array<[string, string]> = [];
    let answer: string | undefined;
    await new Promise<void>((resolve) => {
      streamAssistantRun("hi", "sess-stream-delta", {
        onDelta: (delta, accumulated) => deltas.push([delta, accumulated]),
        onDone: (finalAnswer) => {
          answer = finalAnswer;
          resolve();
        },
        onError: () => resolve(),
      });
    });

    expect(deltas).toEqual([
      ["hello", "hello"],
      [" world", "hello world"],
    ]);
    expect(answer).toBe("hello world");
  });

  it("错误事件触发 onError 且不暴露内部细节", async () => {
    const raw = [
      'data: {"type":"run.started","data":{}}',
      "",
      'data: {"type":"run.failed","data":{"error_code":"AGENT_CHAT_ERROR"}}',
      "",
      "data: [DONE]",
      "",
      "",
    ].join("\n");

    globalThis.fetch = vi.fn().mockResolvedValue(makeSuccessResponse(raw));

    let errorCode: string | null = null;
    let errorMessage: string | null = null;
    await new Promise<void>((resolve) => {
      streamAssistantRun("hi", "sess-test-003", {
        onError: (e) => {
          errorCode = e.code;
          errorMessage = e.message;
          resolve();
        },
        onDone: () => resolve(),
      });
    });

    expect(errorCode).toBe("AGENT_CHAT_ERROR");
    expect(errorMessage).toBeTruthy();
    // 安全：错误消息不能包含内部堆栈、pymysql 等内部信息
    expect(errorMessage).not.toMatch(/pymysql|Traceback|stack/i);
  });

  it("HTTP 错误状态触发 onError", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response("Forbidden", { status: 403 }),
    );

    let errored = false;
    await new Promise<void>((resolve) => {
      streamAssistantRun("hi", "sess-test-004", {
        onError: () => {
          errored = true;
          resolve();
        },
        onDone: () => resolve(),
      });
    });

    expect(errored).toBe(true);
  });

  it("网络异常触发 onError 而非抛错", async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new Error("network down"));

    let errored = false;
    await new Promise<void>((resolve) => {
      streamAssistantRun("hi", "sess-test-005", {
        onError: () => {
          errored = true;
          resolve();
        },
        onDone: () => resolve(),
      });
    });

    expect(errored).toBe(true);
  });

  it("AbortController.abort() 触发后停止消费流", async () => {
    // 模拟 fetch 抛出 AbortError
    const abortErr = new Error("aborted");
    abortErr.name = "AbortError";
    globalThis.fetch = vi.fn().mockRejectedValue(abortErr);

    let errored = false;
    let resolved = false;
    const controller = streamAssistantRun("hi", "sess-test-006", {
      onError: () => {
        errored = true;
      },
      onDone: () => {
        resolved = true;
      },
    });

    controller.abort();

    // 等待微任务让 Promise resolve
    await new Promise((r) => setTimeout(r, 50));

    // AbortError 不应触发 onError（属于用户主动取消）
    expect(errored).toBe(false);
    expect(resolved).toBe(false);
  });

  it("请求包含正确的 URL、方法和 Authorization 头", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      makeSuccessResponse("data: [DONE]\n\n"),
    );

    localStorage.setItem("token", "test-token-abc");

    await new Promise<void>((resolve) => {
      streamAssistantRun("hi", "sess-test-007", {
        onDone: () => resolve(),
        onError: () => resolve(),
      });
    });

    expect(globalThis.fetch).toHaveBeenCalledTimes(1);
    const [url, init] = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toContain("/api/assistant/runs/stream");
    expect(init.method).toBe("POST");
    expect(init.headers["Content-Type"]).toBe("application/json");
    expect(init.headers["Authorization"]).toBe("Bearer test-token-abc");
    expect(init.body).toContain("hi");
    expect(init.body).toContain("sess-test-007");
    // 请求体不接受 user_id / teacher_id / student_id
    expect(init.body).not.toContain("teacher_id");
    expect(init.body).not.toContain("user_id");

    localStorage.removeItem("token");
  });

  it("没有终态事件的流结束时报告 STREAM_INCOMPLETE", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      makeSuccessResponse("data: [DONE]\n\n"),
    );

    const onDone = vi.fn();
    let errorCode: string | null = null;
    await new Promise<void>((resolve) => {
      streamAssistantRun("hi", "sess-test-008", {
        onDone,
        onError: (error) => {
          errorCode = error.code;
          resolve();
        },
      });
    });

    expect(errorCode).toBe("STREAM_INCOMPLETE");
    expect(onDone).not.toHaveBeenCalled();
  });

  it("treats run.failed as a terminal event without calling onDone", async () => {
    const raw = [
      'data: {"type":"run.failed","data":{"error_code":"AGENT_CHAT_ERROR","message":"safe"}}',
      "",
      "data: [DONE]",
      "",
      "",
    ].join("\n");
    globalThis.fetch = vi.fn().mockResolvedValue(makeSuccessResponse(raw));

    const onError = vi.fn();
    const onDone = vi.fn();
    await new Promise<void>((resolve) => {
      streamAssistantRun("hi", "sess-failed-terminal", {
        onError: (error) => {
          onError(error);
          resolve();
        },
        onDone,
      });
    });
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(onError).toHaveBeenCalledTimes(1);
    expect(onDone).not.toHaveBeenCalled();
  });

  it("心跳超时（60 秒无数据）上报 STREAM_TIMEOUT 而非静默吞掉", async () => {
    vi.useFakeTimers();

    // 模拟一个一直挂起、只有 abort 时才以 AbortError 拒绝的 fetch（无任何数据）
    globalThis.fetch = vi.fn().mockImplementation(
      (_url: string, init: RequestInit) =>
        new Promise((_resolve, reject) => {
          init.signal?.addEventListener("abort", () => {
            const err = new Error("aborted");
            err.name = "AbortError";
            reject(err);
          });
        }),
    );

    const onError = vi.fn();
    const onDone = vi.fn();
    streamAssistantRun("hi", "sess-timeout", { onError, onDone });

    await vi.advanceTimersByTimeAsync(60_000);
    await Promise.resolve();

    expect(onError).toHaveBeenCalledTimes(1);
    expect(onError.mock.calls[0][0].code).toBe("STREAM_TIMEOUT");
    expect(onDone).not.toHaveBeenCalled();
  });

  it("用户主动 abort 仍保持静默（不误报 STREAM_TIMEOUT）", async () => {
    globalThis.fetch = vi.fn().mockImplementation(
      (_url: string, init: RequestInit) =>
        new Promise((_resolve, reject) => {
          init.signal?.addEventListener("abort", () => {
            const err = new Error("aborted");
            err.name = "AbortError";
            reject(err);
          });
        }),
    );

    const onError = vi.fn();
    const onDone = vi.fn();
    const controller = streamAssistantRun("hi", "sess-user-abort", {
      onError,
      onDone,
    });

    controller.abort();
    await new Promise((r) => setTimeout(r, 20));

    expect(onError).not.toHaveBeenCalled();
    expect(onDone).not.toHaveBeenCalled();
  });

  it("401 时借道 axios 触发 token 刷新并用新 token 重试一次", async () => {
    localStorage.setItem("token", "expired-token");
    const successText = [
      'data: {"type":"run.completed","data":{}}',
      "",
      "data: [DONE]",
      "",
      "",
    ].join("\n");

    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: false,
        status: 401,
        async json() {
          return { message: "token 已过期" };
        },
      })
      .mockResolvedValueOnce(makeSuccessResponse(successText));
    globalThis.fetch = fetchMock;

    // 模拟 request.ts 拦截器的 401 → refresh → 重试链路：刷新成功并写入新 token
    requestMock.mockImplementation(async () => {
      localStorage.setItem("token", "fresh-token");
      return { sessions: [] };
    });

    const onError = vi.fn();
    let done = false;
    await new Promise<void>((resolve) => {
      streamAssistantRun("hi", "sess-401-retry", {
        onDone: () => {
          done = true;
          resolve();
        },
        onError: (error) => {
          onError(error);
          resolve();
        },
      });
    });

    expect(done).toBe(true);
    expect(onError).not.toHaveBeenCalled();
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls[1][1].headers["Authorization"]).toBe(
      "Bearer fresh-token",
    );

    localStorage.removeItem("token");
  });

  it("刷新链路失败时报 AUTH_EXPIRED 且不再重试流式请求", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      async json() {
        return { message: "未授权" };
      },
    });
    globalThis.fetch = fetchMock;
    requestMock.mockRejectedValue(new Error("登录已过期"));

    const codes: string[] = [];
    await new Promise<void>((resolve) => {
      streamAssistantRun("hi", "sess-401-fail", {
        onError: (error) => {
          codes.push(error.code);
          resolve();
        },
        onDone: () => resolve(),
      });
    });

    expect(codes).toEqual(["AUTH_EXPIRED"]);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("刷新成功但重试仍 401 时只重试一次并报错", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      async json() {
        return { message: "认证失败" };
      },
    });
    globalThis.fetch = fetchMock;
    requestMock.mockResolvedValue({ sessions: [] });

    const errors: Array<{ code: string; message: string }> = [];
    await new Promise<void>((resolve) => {
      streamAssistantRun("hi", "sess-401-twice", {
        onError: (error) => {
          errors.push(error);
          resolve();
        },
        onDone: () => resolve(),
      });
    });

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(errors).toHaveLength(1);
    expect(errors[0].code).toBe("HTTP_ERROR");
  });

  it("supports CRLF separators while reading the live stream", async () => {
    const raw = [
      'data: {"type":"content.delta","data":{"content":"crlf"}}',
      'data: {"type":"run.completed","data":{}}',
      "data: [DONE]",
      "",
      "",
    ].join("\r\n\r\n");
    globalThis.fetch = vi.fn().mockResolvedValue(makeSuccessResponse(raw));

    const onDelta = vi.fn();
    await new Promise<void>((resolve) => {
      streamAssistantRun("hi", "sess-crlf", {
        onDelta,
        onDone: () => resolve(),
        onError: () => resolve(),
      });
    });

    expect(onDelta).toHaveBeenCalledWith("crlf", "crlf");
  });
});

// ========== cancelRun：取消运行 API ==========

describe("cancelRun", () => {
  beforeEach(() => {
    requestMock.mockReset();
  });

  it("POST /assistant/runs/{id}/cancel 取消运行", async () => {
    requestMock.mockResolvedValue({ runId: "run-001", status: "cancelled" });

    const result = await cancelRun("run-001");
    expect(result.status).toBe("cancelled");

    expect(requestMock).toHaveBeenCalledTimes(1);
    const config = requestMock.mock.calls[0][0];
    expect(config.url).toBe("/assistant/runs/run-001/cancel");
    expect(config.method).toBe("post");
  });

  it("已完成的运行返回当前状态而不报错", async () => {
    requestMock.mockResolvedValue({
      runId: "run-002",
      status: "completed",
      message: "运行已结束",
    });

    const result = await cancelRun("run-002");
    expect(result.status).toBe("completed");
  });

  it("404 时抛错（运行不存在或非本人）", async () => {
    requestMock.mockRejectedValue(new Error("运行不存在"));

    await expect(cancelRun("run-foreign")).rejects.toThrow();
  });
});

describe("multi-role phase mapping", () => {
  it.each([
    ["learning_coach", "辅导"],
    ["feedback_explanation", "反馈"],
    ["learning_plan", "规划"],
    ["operations_analysis", "运营"],
    ["audit_analysis", "审计"],
    ["model_governance", "模型"],
  ])("maps route %s to safe Chinese copy", (intent, copy) => {
    const phase = mapEventToPhase({
      type: "route.selected",
      data: { intent },
    });

    expect(phase?.label).toContain(copy);
    expect(phase?.label).not.toContain(intent);
  });

  it("does not expose an unknown internal agent identifier", () => {
    const phase = mapEventToPhase({
      type: "agent.started",
      data: { agent: "private_database_exporter" },
    });

    expect(phase).toEqual({ key: "agent.started", label: "正在处理" });
    expect(phase?.label).not.toContain("private_database_exporter");
  });
});

describe("approval API", () => {
  beforeEach(() => {
    requestMock.mockReset();
  });

  const approval = {
    approvalId: "approval-001",
    runId: "run-001",
    actionType: "update_model_config",
    targetType: "model_config",
    targetId: "model-1",
    parameters: { modelName: "gpt-test", status: 1 },
    summary: "更新模型配置",
    riskLevel: "high",
    status: "pending",
    expiresAt: "2026-07-25T12:00:00",
    result: null,
  };

  it("lists current user's pending approvals", async () => {
    requestMock.mockResolvedValue({ items: [approval] });

    const result = await listApprovals("pending");

    expect(result.items).toEqual([approval]);
    expect(requestMock).toHaveBeenCalledWith({
      url: "/assistant/approvals",
      method: "get",
      params: { status: "pending" },
    });
  });

  it("approves with the original parameters object", async () => {
    requestMock.mockResolvedValue({
      approvalId: approval.approvalId,
      status: "executed",
      result: { success: true },
    });

    await approveAction(approval.approvalId, approval.parameters);

    expect(requestMock).toHaveBeenCalledWith({
      url: `/assistant/approvals/${approval.approvalId}/approve`,
      method: "post",
      data: { payload: approval.parameters },
    });
  });

  it("rejects with a trimmed non-empty reason", async () => {
    requestMock.mockResolvedValue({ ...approval, status: "rejected" });

    await rejectAction(approval.approvalId, "  风险过高  ");

    expect(requestMock).toHaveBeenCalledWith({
      url: `/assistant/approvals/${approval.approvalId}/reject`,
      method: "post",
      data: { reason: "风险过高" },
    });
  });

  it("does not send an empty rejection reason", async () => {
    await expect(rejectAction(approval.approvalId, "   ")).rejects.toThrow(
      "拒绝原因不能为空",
    );
    expect(requestMock).not.toHaveBeenCalled();
  });
});
