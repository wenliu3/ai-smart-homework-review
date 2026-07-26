import { flushPromises, mount } from "@vue/test-utils";
import { nextTick } from "vue";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AssistantPanel from "../AssistantPanel.vue";

const apiMocks = vi.hoisted(() => ({
  cancelRun: vi.fn(),
  createSession: vi.fn(),
  deleteSession: vi.fn(),
  getRunArtifacts: vi.fn(),
  getSessionMessages: vi.fn(),
  listSessions: vi.fn(),
  renameSession: vi.fn(),
  streamAssistantRun: vi.fn(),
  submitRunFeedback: vi.fn(),
}));

vi.mock("@/api/assistant", () => apiMocks);

// 渲染消息与流式内容的聊天视图桩，便于断言竞态场景下的界面状态
const ChatViewStub = {
  name: "AssistantChatView",
  props: ["config", "messages", "streamingContent", "isGenerating", "currentPhase"],
  template: `
    <div>
      <div data-testid="messages">{{ messages.map((m) => m.content).join("|") }}</div>
      <div data-testid="artifacts">{{ messages.flatMap((m) => (m.artifacts || []).map((a) => a.label + ":" + a.detail)).join("|") }}</div>
      <div data-testid="streaming">{{ streamingContent }}</div>
      <button data-testid="send" @click="$emit('send', 'hello')" />
    </div>
  `,
  methods: {
    focus() {},
    scrollToBottom() {},
  },
};

const HistoryViewStub = {
  name: "AssistantHistoryView",
  props: ["sessions", "loading", "error"],
  template:
    '<button data-testid="pick-session" @click="$emit(\'select\', \'session-2\')" />',
};

function mountPanel() {
  return mount(AssistantPanel, {
    props: { visible: true, role: "student" as const },
    global: {
      stubs: {
        transition: false,
        "el-icon": { template: "<i><slot /></i>" },
        "el-button": { template: "<button><slot /></button>" },
        "el-tooltip": { template: "<span><slot /></span>" },
        AssistantChatView: ChatViewStub,
        AssistantHistoryView: HistoryViewStub,
        AssistantApprovalView: true,
      },
    },
  });
}

describe("AssistantPanel lifecycle", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    apiMocks.createSession.mockResolvedValue({ sessionId: "session-1" });
    apiMocks.listSessions.mockResolvedValue({ sessions: [] });
    apiMocks.getRunArtifacts.mockResolvedValue({ runId: "run-1", items: [] });
    apiMocks.cancelRun.mockResolvedValue({
      runId: "run-1",
      status: "cancelled",
    });
    apiMocks.streamAssistantRun.mockImplementation(
      (_message: string, _sessionId: string, callbacks: any) => {
        callbacks.onEvent({
          type: "run.started",
          data: { run_id: "run-1" },
        });
        return new AbortController();
      },
    );
  });

  it("发送时携带当前页面路径作为 pageContext", async () => {
    const wrapper = mountPanel();
    await wrapper.get('[data-testid="send"]').trigger("click");
    await flushPromises();

    expect(apiMocks.streamAssistantRun).toHaveBeenCalledWith(
      "hello",
      "session-1",
      expect.any(Object),
      expect.objectContaining({ pageContext: expect.any(String) }),
    );
  });

  it("运行完成后产物摘要挂到对应回答下，拉取失败不影响对话", async () => {
    let capturedCallbacks: any = null;
    apiMocks.streamAssistantRun.mockImplementation(
      (_message: string, _sessionId: string, callbacks: any) => {
        capturedCallbacks = callbacks;
        callbacks.onEvent({ type: "run.started", data: { run_id: "run-1" } });
        return new AbortController();
      },
    );
    apiMocks.getSessionMessages.mockResolvedValue({
      sessionId: "session-1",
      messages: [
        { role: "user", content: "hello", runId: "run-1" },
        { role: "assistant", content: "这是回答", runId: "run-1" },
      ],
    });
    apiMocks.getRunArtifacts.mockResolvedValue({
      runId: "run-1",
      items: [
        {
          artifactType: "review_result",
          schemaVersion: "v1",
          payload: { approved: true, issues: [] },
          createdAt: null,
        },
      ],
    });

    const wrapper = mountPanel();
    await wrapper.get('[data-testid="send"]').trigger("click");
    await flushPromises();
    capturedCallbacks.onDone("这是回答");
    await flushPromises();

    expect(apiMocks.getRunArtifacts).toHaveBeenCalledWith("run-1");
    expect(wrapper.get('[data-testid="artifacts"]').text()).toContain(
      "安全审核:已通过",
    );

    // 第二轮产物拉取失败：对话正常，不新增产物条目
    apiMocks.getRunArtifacts.mockRejectedValue(new Error("network"));
    await wrapper.get('[data-testid="send"]').trigger("click");
    await flushPromises();
    capturedCallbacks.onDone("第二轮回答");
    await flushPromises();

    expect(wrapper.get('[data-testid="messages"]').text()).toContain(
      "这是回答",
    );
  });

  it("cancels both local stream and backend run when hidden", async () => {
    const wrapper = mount(AssistantPanel, {
      props: { visible: true, role: "student" },
      global: {
        stubs: {
          transition: false,
          "el-icon": { template: "<i><slot /></i>" },
          "el-button": { template: "<button><slot /></button>" },
          "el-tooltip": { template: "<span><slot /></span>" },
          AssistantChatView: {
            template:
              '<button data-testid="send" @click="$emit(\'send\', \'hello\')" />',
            methods: {
              focus() {},
              scrollToBottom() {},
            },
          },
          AssistantHistoryView: true,
          AssistantApprovalView: true,
        },
      },
    });

    await wrapper.get('[data-testid="send"]').trigger("click");
    await nextTick();
    expect(apiMocks.streamAssistantRun).toHaveBeenCalledTimes(1);

    await wrapper.setProps({ visible: false });
    await vi.waitFor(() => {
      expect(apiMocks.cancelRun).toHaveBeenCalledWith("run-1");
    });
  });

  it("does not start a hidden run when session creation resolves late", async () => {
    let resolveSession!: (value: { sessionId: string }) => void;
    apiMocks.createSession.mockReturnValue(
      new Promise((resolve) => {
        resolveSession = resolve;
      }),
    );
    const wrapper = mount(AssistantPanel, {
      props: { visible: true, role: "student" },
      global: {
        stubs: {
          transition: false,
          "el-icon": { template: "<i><slot /></i>" },
          "el-button": { template: "<button><slot /></button>" },
          "el-tooltip": { template: "<span><slot /></span>" },
          AssistantChatView: {
            template:
              '<button data-testid="send" @click="$emit(\'send\', \'hello\')" />',
            methods: {
              focus() {},
              scrollToBottom() {},
            },
          },
          AssistantHistoryView: true,
          AssistantApprovalView: true,
        },
      },
    });

    await wrapper.get('[data-testid="send"]').trigger("click");
    await wrapper.setProps({ visible: false });
    resolveSession({ sessionId: "session-late" });
    await vi.waitFor(() => {
      expect(apiMocks.createSession).toHaveBeenCalledTimes(1);
    });
    await nextTick();

    expect(apiMocks.streamAssistantRun).not.toHaveBeenCalled();
  });

  it("onDone 拉取消息期间用户已发新消息时，不用旧快照覆盖当前会话", async () => {
    let capturedCallbacks: any = null;
    apiMocks.streamAssistantRun.mockImplementation(
      (_message: string, _sessionId: string, callbacks: any) => {
        capturedCallbacks = callbacks;
        callbacks.onEvent({ type: "run.started", data: { run_id: "run-1" } });
        return new AbortController();
      },
    );

    let resolveStale!: (value: any) => void;
    apiMocks.getSessionMessages.mockReturnValue(
      new Promise((resolve) => {
        resolveStale = resolve;
      }),
    );

    const wrapper = mountPanel();

    // 第一轮发送并进入完成回调（getSessionMessages 挂起）
    await wrapper.get('[data-testid="send"]').trigger("click");
    await flushPromises();
    const firstCallbacks = capturedCallbacks;
    firstCallbacks.onDone("第一轮回答");
    await nextTick();

    // finishRun 已解锁输入：用户此时发出第二条消息
    await wrapper.get('[data-testid="send"]').trigger("click");
    await flushPromises();

    // 旧会话快照此时才返回，不应覆盖新一轮的消息列表
    resolveStale({
      sessionId: "session-1",
      messages: [{ role: "assistant", content: "stale-snapshot" }],
    });
    await flushPromises();

    const messagesText = wrapper.get('[data-testid="messages"]').text();
    expect(messagesText).not.toContain("stale-snapshot");
    expect(messagesText).toContain("hello");
  });

  it("生成中从历史加载其他会话：先取消当前运行，流式内容不串入新会话", async () => {
    let capturedCallbacks: any = null;
    apiMocks.streamAssistantRun.mockImplementation(
      (_message: string, _sessionId: string, callbacks: any) => {
        capturedCallbacks = callbacks;
        callbacks.onEvent({ type: "run.started", data: { run_id: "run-1" } });
        return new AbortController();
      },
    );
    apiMocks.getSessionMessages.mockResolvedValue({
      sessionId: "session-2",
      messages: [{ role: "assistant", content: "第二个会话的历史消息" }],
    });

    const wrapper = mountPanel();

    await wrapper.get('[data-testid="send"]').trigger("click");
    await flushPromises();

    capturedCallbacks.onDelta("旧会话增量", "旧会话增量");
    await nextTick();
    expect(wrapper.get('[data-testid="streaming"]').text()).toContain(
      "旧会话增量",
    );

    // 生成中打开历史并选择另一个会话
    await wrapper.get('[data-testid="assistant-history"]').trigger("click");
    await flushPromises();
    await wrapper.get('[data-testid="pick-session"]').trigger("click");
    await flushPromises();

    expect(apiMocks.cancelRun).toHaveBeenCalledWith("run-1");
    expect(wrapper.get('[data-testid="streaming"]').text()).toBe("");
    const messagesText = wrapper.get('[data-testid="messages"]').text();
    expect(messagesText).toContain("第二个会话的历史消息");
    expect(messagesText).not.toContain("旧会话增量");

    // 旧运行迟到的流式增量不再渲染
    capturedCallbacks.onDelta("迟到增量", "迟到增量");
    await nextTick();
    expect(wrapper.get('[data-testid="streaming"]').text()).toBe("");
  });

  it("生成中关闭面板：部分流式内容收编进消息，重开后无残留气泡", async () => {
    let capturedCallbacks: any = null;
    apiMocks.streamAssistantRun.mockImplementation(
      (_message: string, _sessionId: string, callbacks: any) => {
        capturedCallbacks = callbacks;
        callbacks.onEvent({ type: "run.started", data: { run_id: "run-1" } });
        return new AbortController();
      },
    );

    const wrapper = mountPanel();

    await wrapper.get('[data-testid="send"]').trigger("click");
    await flushPromises();
    capturedCallbacks.onDelta("部分回答", "部分回答");
    await nextTick();

    await wrapper.setProps({ visible: false });
    await flushPromises();

    expect(apiMocks.cancelRun).toHaveBeenCalledWith("run-1");

    await wrapper.setProps({ visible: true });
    await nextTick();

    expect(wrapper.get('[data-testid="streaming"]').text()).toBe("");
    expect(wrapper.get('[data-testid="messages"]').text()).toContain(
      "部分回答",
    );
  });
});

describe("AssistantPanel 审批卡片", () => {
  // 教师角色 + 能读到 kind 的聊天视图桩
  const ApprovalAwareChatStub = {
    name: "AssistantChatView",
    props: [
      "config",
      "messages",
      "streamingContent",
      "isGenerating",
      "currentPhase",
    ],
    template: `
      <div>
        <div data-testid="messages">{{ messages.map((m) => m.content).join("|") }}</div>
        <div data-testid="kinds">{{ messages.map((m) => m.kind || "text").join("|") }}</div>
        <div data-testid="approval-ids">{{ messages.filter((m) => m.approval).map((m) => m.approval.approvalId).join("|") }}</div>
        <button data-testid="send" @click="$emit('send', 'hello')" />
        <button data-testid="open-approvals" @click="$emit('open-approvals')" />
      </div>
    `,
    methods: {
      focus() {},
      scrollToBottom() {},
    },
  };

  function mountTeacherPanel() {
    return mount(AssistantPanel, {
      props: { visible: true, role: "teacher" as const },
      global: {
        stubs: {
          transition: false,
          "el-icon": { template: "<i><slot /></i>" },
          "el-button": { template: "<button><slot /></button>" },
          "el-tooltip": { template: "<span><slot /></span>" },
          AssistantChatView: ApprovalAwareChatStub,
          AssistantHistoryView: true,
          AssistantApprovalView: {
            template: '<div data-testid="approval-view" />',
          },
        },
      },
    });
  }

  const approvalEvent = {
    type: "approval.required",
    data: {
      approval_id: "approval-1",
      action_type: "publish_assignment",
      target_type: "assignment",
      target_id: "7",
      risk_level: "high",
      summary: "发布《第三章作业》",
      expires_at: "2026-07-26T20:00:00",
    },
  };

  beforeEach(() => {
    vi.clearAllMocks();
    apiMocks.createSession.mockResolvedValue({ sessionId: "session-1" });
    apiMocks.listSessions.mockResolvedValue({ sessions: [] });
    apiMocks.getRunArtifacts.mockResolvedValue({ runId: "run-1", items: [] });
    apiMocks.cancelRun.mockResolvedValue({
      runId: "run-1",
      status: "cancelled",
    });
    apiMocks.getSessionMessages.mockResolvedValue({
      sessionId: "session-1",
      messages: [
        { role: "user", content: "hello" },
        { role: "assistant", content: "已生成待审批草案" },
      ],
    });
  });

  it("approval.required 事件在对话里插入审批卡片", async () => {
    apiMocks.streamAssistantRun.mockImplementation(
      (_message: string, _sessionId: string, callbacks: any) => {
        callbacks.onEvent({ type: "run.started", data: { run_id: "run-1" } });
        callbacks.onEvent(approvalEvent);
        return new AbortController();
      },
    );

    const wrapper = mountTeacherPanel();
    await wrapper.get('[data-testid="send"]').trigger("click");
    await flushPromises();

    expect(wrapper.get('[data-testid="kinds"]').text()).toContain("approval");
    expect(wrapper.get('[data-testid="approval-ids"]').text()).toBe(
      "approval-1",
    );
  });

  it("onDone 用服务端消息覆盖后审批卡片仍在", async () => {
    let capturedCallbacks: any = null;
    apiMocks.streamAssistantRun.mockImplementation(
      (_message: string, _sessionId: string, callbacks: any) => {
        capturedCallbacks = callbacks;
        callbacks.onEvent({ type: "run.started", data: { run_id: "run-1" } });
        callbacks.onEvent(approvalEvent);
        return new AbortController();
      },
    );

    const wrapper = mountTeacherPanel();
    await wrapper.get('[data-testid="send"]').trigger("click");
    await flushPromises();

    capturedCallbacks.onDone("已生成待审批草案");
    await flushPromises();

    const messagesText = wrapper.get('[data-testid="messages"]').text();
    expect(messagesText).toContain("已生成待审批草案");
    expect(wrapper.get('[data-testid="approval-ids"]').text()).toBe(
      "approval-1",
    );
  });

  it("缺少 approval_id 的事件不插入卡片", async () => {
    apiMocks.streamAssistantRun.mockImplementation(
      (_message: string, _sessionId: string, callbacks: any) => {
        callbacks.onEvent({ type: "run.started", data: { run_id: "run-1" } });
        callbacks.onEvent({ type: "approval.required", data: { summary: "x" } });
        return new AbortController();
      },
    );

    const wrapper = mountTeacherPanel();
    await wrapper.get('[data-testid="send"]').trigger("click");
    await flushPromises();

    expect(wrapper.get('[data-testid="kinds"]').text()).not.toContain(
      "approval",
    );
  });

  it("第二轮完成刷新消息后，第一轮的审批卡片不被冲掉", async () => {
    let round = 0;
    let capturedCallbacks: any = null;
    apiMocks.streamAssistantRun.mockImplementation(
      (_message: string, _sessionId: string, callbacks: any) => {
        capturedCallbacks = callbacks;
        callbacks.onEvent({ type: "run.started", data: { run_id: "run-1" } });
        callbacks.onEvent(
          round === 0
            ? approvalEvent
            : {
                ...approvalEvent,
                data: { ...approvalEvent.data, approval_id: "approval-2" },
              },
        );
        round += 1;
        return new AbortController();
      },
    );

    const wrapper = mountTeacherPanel();
    await wrapper.get('[data-testid="send"]').trigger("click");
    await flushPromises();
    capturedCallbacks.onDone("第一轮回答");
    await flushPromises();

    await wrapper.get('[data-testid="send"]').trigger("click");
    await flushPromises();
    capturedCallbacks.onDone("第二轮回答");
    await flushPromises();

    expect(wrapper.get('[data-testid="approval-ids"]').text()).toBe(
      "approval-1|approval-2",
    );
  });

  it("新建对话清空本会话累积的审批卡片", async () => {
    let capturedCallbacks: any = null;
    apiMocks.streamAssistantRun.mockImplementation(
      (_message: string, _sessionId: string, callbacks: any) => {
        capturedCallbacks = callbacks;
        callbacks.onEvent({ type: "run.started", data: { run_id: "run-1" } });
        callbacks.onEvent(approvalEvent);
        return new AbortController();
      },
    );

    const wrapper = mountTeacherPanel();
    await wrapper.get('[data-testid="send"]').trigger("click");
    await flushPromises();
    // 生成结束后「新建对话」才可点（生成中该按钮 disabled）
    capturedCallbacks.onDone("已生成待审批草案");
    await flushPromises();
    expect(wrapper.get('[data-testid="approval-ids"]').text()).toBe(
      "approval-1",
    );

    // 头部「新建对话」是 header-actions 里的第一个按钮
    await wrapper.findAll(".header-actions button")[0].trigger("click");
    await flushPromises();

    expect(wrapper.get('[data-testid="approval-ids"]').text()).toBe("");
    expect(wrapper.get('[data-testid="messages"]').text()).toBe("");
  });

  it("聊天卡片的「去审批」切到审批视图", async () => {
    apiMocks.streamAssistantRun.mockImplementation(() => new AbortController());
    const wrapper = mountTeacherPanel();

    await wrapper.get('[data-testid="open-approvals"]').trigger("click");
    await flushPromises();

    expect(wrapper.find('[data-testid="approval-view"]').exists()).toBe(true);
  });

  it("教师看得到审批入口，学生看不到", () => {
    const teacher = mountTeacherPanel();
    expect(
      teacher.find('[data-testid="assistant-approvals"]').exists(),
    ).toBe(true);

    const student = mountPanel();
    expect(
      student.find('[data-testid="assistant-approvals"]').exists(),
    ).toBe(false);
  });
});
