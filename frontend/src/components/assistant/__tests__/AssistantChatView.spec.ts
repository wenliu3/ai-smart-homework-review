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
