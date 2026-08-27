import ElementPlus from "element-plus";
import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { getAvailableAiRules } from "@/api/ai-rule";
import AiRuleSelector from "../AiRuleSelector.vue";

vi.mock("@/api/ai-rule", () => ({
  getAvailableAiRules: vi.fn(),
}));

const getAvailableAiRulesMock = vi.mocked(getAvailableAiRules);

describe("AiRuleSelector", () => {
  beforeEach(() => {
    getAvailableAiRulesMock.mockResolvedValue([
      {
        id: "9",
        name: "实验报告规则",
        description: "",
        modelType: "zhipu",
        prompt: "按实验要求评分",
        visibility: "private",
        tags: [],
        maxScore: 60,
      },
    ]);
  });

  it("选中规则时 emit 的快照保留 maxScore", async () => {
    const wrapper = mount(AiRuleSelector, {
      props: { modelValue: null },
      global: { plugins: [ElementPlus] },
    });
    await flushPromises();

    // 打开规则选择弹框
    await wrapper.get(".config-btn").trigger("click");
    await flushPromises();

    // 模拟用户在下拉框中选择 id=9 的规则
    (wrapper.vm as unknown as { tempSelectedRuleId: string }).tempSelectedRuleId =
      "9";
    await wrapper.vm.$nextTick();

    // 点击「确定」
    const confirmButton = wrapper.find(".dialog-footer .el-button--primary");
    expect(confirmButton.exists()).toBe(true);
    await confirmButton.trigger("click");
    await flushPromises();

    expect(wrapper.emitted("update:modelValue")?.at(-1)?.[0]).toEqual({
      id: "9",
      name: "实验报告规则",
      modelType: "zhipu",
      prompt: "按实验要求评分",
      maxScore: 60,
    });
  });

  it("规则未带 maxScore 时 emit 的快照兜底为 100", async () => {
    getAvailableAiRulesMock.mockResolvedValue([
      {
        id: "9",
        name: "实验报告规则",
        description: "",
        modelType: "zhipu",
        prompt: "按实验要求评分",
        visibility: "private",
        tags: [],
      },
    ]);
    const wrapper = mount(AiRuleSelector, {
      props: { modelValue: null },
      global: { plugins: [ElementPlus] },
    });
    await flushPromises();

    await wrapper.get(".config-btn").trigger("click");
    await flushPromises();

    (wrapper.vm as unknown as { tempSelectedRuleId: string }).tempSelectedRuleId =
      "9";
    await wrapper.vm.$nextTick();

    const confirmButton = wrapper.find(".dialog-footer .el-button--primary");
    expect(confirmButton.exists()).toBe(true);
    await confirmButton.trigger("click");
    await flushPromises();

    expect(wrapper.emitted("update:modelValue")?.at(-1)?.[0]).toEqual({
      id: "9",
      name: "实验报告规则",
      modelType: "zhipu",
      prompt: "按实验要求评分",
      maxScore: 100,
    });
  });
});
