import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import AssistantChatView from "../AssistantChatView.vue";
import { getAssistantRoleConfig } from "../role-config";

describe("AssistantChatView", () => {
  it("shows student-specific copy and emits a trimmed message", async () => {
    const wrapper = mount(AssistantChatView, {
      props: {
        config: getAssistantRoleConfig("student")!,
        messages: [],
        streamingContent: "",
        isGenerating: false,
        currentPhase: "",
      },
      global: {
        stubs: {
          "el-icon": { template: "<i><slot /></i>" },
          "el-button": {
            template: "<button><slot /></button>",
          },
        },
      },
    });

    expect(wrapper.text()).toContain("AI 学习助手");
    expect(wrapper.text()).toContain("独立完成");

    await wrapper.get("textarea").setValue("  请解释这道题  ");
    await wrapper.get('[data-testid="assistant-send"]').trigger("click");

    expect(wrapper.emitted("send")?.[0]).toEqual(["请解释这道题"]);
  });

  it("中文输入法组词回车不发送，普通回车正常发送", async () => {
    const wrapper = mount(AssistantChatView, {
      props: {
        config: getAssistantRoleConfig("student")!,
        messages: [],
        streamingContent: "",
        isGenerating: false,
        currentPhase: "",
      },
      global: {
        stubs: {
          "el-icon": { template: "<i><slot /></i>" },
          "el-button": {
            template: "<button><slot /></button>",
          },
        },
      },
    });

    const textarea = wrapper.get("textarea");
    await textarea.setValue("正在组词的内容");

    // IME 组词上屏的回车（isComposing 为 true）不应触发发送
    await textarea.trigger("keydown", { key: "Enter", isComposing: true });
    expect(wrapper.emitted("send")).toBeUndefined();

    // 部分浏览器 IME 场景下 keyCode 为 229，同样不应发送
    await textarea.trigger("keydown", { key: "Enter", keyCode: 229 });
    expect(wrapper.emitted("send")).toBeUndefined();

    // 普通回车正常发送
    await textarea.trigger("keydown", { key: "Enter" });
    expect(wrapper.emitted("send")?.[0]).toEqual(["正在组词的内容"]);
  });

  it("emits stop while generating", async () => {
    const wrapper = mount(AssistantChatView, {
      props: {
        config: getAssistantRoleConfig("teacher")!,
        messages: [],
        streamingContent: "",
        isGenerating: true,
        currentPhase: "正在处理",
      },
      global: {
        stubs: {
          "el-icon": { template: "<i><slot /></i>" },
          "el-button": {
            template: "<button><slot /></button>",
          },
        },
      },
    });

    await wrapper.get('[data-testid="assistant-stop"]').trigger("click");
    expect(wrapper.emitted("stop")).toHaveLength(1);
  });
});

describe("AssistantChatView 审批卡片", () => {
  const approvalMessage = {
    role: "assistant" as const,
    content: "发布《第三章作业》",
    html: "",
    kind: "approval" as const,
    approval: {
      approvalId: "approval-1",
      actionType: "publish_assignment",
      targetType: "assignment",
      targetId: "7",
      riskLevel: "high",
      summary: "发布《第三章作业》",
      expiresAt: "2026-07-26T20:00:00",
    },
  };

  function mountWithApproval() {
    return mount(AssistantChatView, {
      props: {
        config: getAssistantRoleConfig("teacher")!,
        messages: [approvalMessage],
        streamingContent: "",
        isGenerating: false,
        currentPhase: "",
      },
      global: {
        stubs: {
          "el-icon": { template: "<i><slot /></i>" },
          "el-button": { template: "<button><slot /></button>" },
        },
      },
    });
  }

  it("把审批消息渲染成卡片而不是 Markdown 气泡", () => {
    const wrapper = mountWithApproval();

    const card = wrapper.get('[data-testid="chat-approval-card"]');
    expect(card.text()).toContain("发布作业");
    expect(card.text()).toContain("发布《第三章作业》");
    expect(card.text()).toContain("需要你确认后才会执行");
  });

  it("点击「去审批」向上抛出 open-approvals", async () => {
    const wrapper = mountWithApproval();

    await wrapper.get('[data-testid="chat-open-approvals"]').trigger("click");

    expect(wrapper.emitted("open-approvals")).toHaveLength(1);
  });

  it("卡片不暴露内部动作标识符", () => {
    expect(mountWithApproval().text()).not.toContain("publish_assignment");
  });
});

describe("AssistantChatView 反馈按钮", () => {
  const assistantMessage = {
    role: "assistant" as const,
    content: "这是回答",
    html: "<p>这是回答</p>",
    runId: "run-fb-1",
  };

  function mountWithMessages(messages: any[]) {
    return mount(AssistantChatView, {
      props: {
        config: getAssistantRoleConfig("teacher")!,
        messages,
        streamingContent: "",
        isGenerating: false,
        currentPhase: "",
      },
      global: {
        stubs: {
          "el-icon": { template: "<i><slot /></i>" },
          "el-button": { template: "<button><slot /></button>" },
        },
      },
    });
  }

  it("有 runId 的助手消息显示 👍/👎，点击向上抛 feedback", async () => {
    const wrapper = mountWithMessages([assistantMessage]);

    await wrapper.get('[data-testid="feedback-up-run-fb-1"]').trigger("click");

    expect(wrapper.emitted("feedback")?.[0]).toEqual(["run-fb-1", 1]);
  });

  it("重复点击同一评分不重复上报，换评分会上报", async () => {
    const wrapper = mountWithMessages([assistantMessage]);

    await wrapper.get('[data-testid="feedback-up-run-fb-1"]').trigger("click");
    await wrapper.get('[data-testid="feedback-up-run-fb-1"]').trigger("click");
    await wrapper.get('[data-testid="feedback-down-run-fb-1"]').trigger("click");

    expect(wrapper.emitted("feedback")).toEqual([
      ["run-fb-1", 1],
      ["run-fb-1", -1],
    ]);
  });

  it("用户消息与无 runId 的消息不渲染反馈按钮", () => {
    const wrapper = mountWithMessages([
      { role: "user", content: "问题", html: "<p>问题</p>" },
      { role: "assistant", content: "旧回答", html: "<p>旧回答</p>" },
    ]);

    expect(wrapper.find('[data-testid^="feedback-"]').exists()).toBe(false);
  });
});
