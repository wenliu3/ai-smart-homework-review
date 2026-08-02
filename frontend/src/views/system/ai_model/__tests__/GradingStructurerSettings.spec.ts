import ElementPlus from "element-plus";
import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { aiModelApi, type AiModel } from "@/api/ai-models";
import AiModelIndex from "../index.vue";

vi.mock("@/api/ai-models", () => ({
  aiModelApi: {
    getList: vi.fn(),
    getBalance: vi.fn(),
    getGradingStructurerConfig: vi.fn(),
    updateGradingStructurerConfig: vi.fn(),
    testStructuredOutput: vi.fn(),
  },
}));

const makeModel = (code: string, overrides: Partial<AiModel> = {}): AiModel => ({
  code,
  name: code === "deepseek" ? "DeepSeek" : "小米",
  provider: "test",
  modelName: `${code}-chat`,
  baseUrl: "https://example.com/v1",
  apiKey: "sk-t****cdef",
  status: "active",
  isDefault: code === "deepseek",
  totalUsage: 0,
  totalTokens: 0,
  lastBalance: 0,
  balanceCurrency: "CNY",
  updatedAt: "2026-01-01T00:00:00",
  ...overrides,
});

const BALANCE = {
  balance: 1,
  currency: "CNY",
  lastUpdated: new Date("2026-01-01T00:00:00"),
  status: "success" as const,
};

describe("GradingStructurerSettings（AI 模型页顶部卡片）", () => {
  let wrapper: VueWrapper | null = null;

  beforeEach(() => {
    vi.mocked(aiModelApi.getList).mockResolvedValue({
      models: [makeModel("deepseek"), makeModel("mimo")],
      summary: {
        totalModels: 2,
        activeModels: 2,
        totalUsage: 0,
        totalBalance: 0,
      },
    });
    vi.mocked(aiModelApi.getBalance).mockResolvedValue(BALANCE);
    vi.mocked(aiModelApi.getGradingStructurerConfig).mockResolvedValue({
      enabled: false,
      modelCode: null,
      model: null,
    });
  });

  afterEach(() => {
    wrapper?.unmount();
    wrapper = null;
    vi.clearAllMocks();
  });

  const mountPage = async () => {
    wrapper = mount(AiModelIndex, { global: { plugins: [ElementPlus] } });
    await flushPromises();
    await flushPromises();
    return wrapper;
  };

  const getSwitch = () =>
    wrapper!.get<HTMLInputElement>('[data-testid="structurer-enabled"]');

  it("渲染开关；开启后展示模型选择，未选择模型前禁止保存", async () => {
    await mountPage();

    expect(wrapper!.find('[data-testid="structurer-enabled"]').exists()).toBe(true);
    expect(wrapper!.find('[data-testid="structurer-model-select"]').exists()).toBe(false);

    await getSwitch().setValue(true);

    expect(wrapper!.find('[data-testid="structurer-model-select"]').exists()).toBe(true);
    expect(wrapper!.get('[data-testid="structurer-save"]').attributes("disabled")).toBeDefined();
  });

  it("选择模型并通过能力测试后才允许保存；切换模型后通过标记失效", async () => {
    vi.mocked(aiModelApi.testStructuredOutput).mockResolvedValue({
      success: true,
      modelCode: "deepseek",
      message: "结构化输出能力验证通过",
      responseTime: 12,
    });
    await mountPage();

    await getSwitch().setValue(true);
    await wrapper!.get<HTMLSelectElement>('[data-testid="structurer-model-select"]').setValue("deepseek");
    // 已选模型但未通过能力测试 → 仍禁止保存
    expect(wrapper!.get('[data-testid="structurer-save"]').attributes("disabled")).toBeDefined();

    await wrapper!.get('[data-testid="structurer-test"]').trigger("click");
    await flushPromises();

    expect(vi.mocked(aiModelApi.testStructuredOutput)).toHaveBeenCalledWith("deepseek");
    // 能力测试通过 → 允许保存
    expect(wrapper!.get('[data-testid="structurer-save"]').attributes("disabled")).toBeUndefined();

    // 切换模型 → 通过标记失效 → 再次禁止保存
    await wrapper!.get<HTMLSelectElement>('[data-testid="structurer-model-select"]').setValue("mimo");
    expect(wrapper!.get('[data-testid="structurer-save"]').attributes("disabled")).toBeDefined();
  });

  it("能力测试失败时仍禁止保存并显示错误摘要", async () => {
    vi.mocked(aiModelApi.testStructuredOutput).mockResolvedValue({
      success: false,
      modelCode: "deepseek",
      message: "结构化输出能力验证失败：模型未返回结构化输出",
    });
    await mountPage();

    await getSwitch().setValue(true);
    await wrapper!.get<HTMLSelectElement>('[data-testid="structurer-model-select"]').setValue("deepseek");
    await wrapper!.get('[data-testid="structurer-test"]').trigger("click");
    await flushPromises();

    expect(wrapper!.get('[data-testid="structurer-save"]').attributes("disabled")).toBeDefined();
    expect(wrapper!.text()).toContain("结构化输出能力验证失败");
  });

  it("关闭开关时无需选择模型即可保存；保存失败恢复服务端状态并显示错误", async () => {
    vi.mocked(aiModelApi.testStructuredOutput).mockResolvedValue({
      success: true,
      modelCode: "deepseek",
      message: "结构化输出能力验证通过",
      responseTime: 12,
    });
    vi.mocked(aiModelApi.updateGradingStructurerConfig).mockRejectedValue(
      new Error("保存失败，请重试"),
    );
    await mountPage();

    // 初始关闭：无需选择模型即可保存
    expect(wrapper!.get('[data-testid="structurer-save"]').attributes("disabled")).toBeUndefined();

    // 开启 → 选模型 → 通过能力测试 → 可保存
    await getSwitch().setValue(true);
    await wrapper!.get<HTMLSelectElement>('[data-testid="structurer-model-select"]').setValue("deepseek");
    await wrapper!.get('[data-testid="structurer-test"]').trigger("click");
    await flushPromises();
    expect(wrapper!.get('[data-testid="structurer-save"]').attributes("disabled")).toBeUndefined();

    await wrapper!.get('[data-testid="structurer-save"]').trigger("click");
    await flushPromises();

    expect(vi.mocked(aiModelApi.updateGradingStructurerConfig)).toHaveBeenCalledWith({
      enabled: true,
      modelCode: "deepseek",
    });
    // 保存失败：重新拉取服务端配置并恢复（初始为关闭）
    expect(vi.mocked(aiModelApi.getGradingStructurerConfig)).toHaveBeenCalledTimes(2);
    expect(getSwitch().element.checked).toBe(false);
    expect(wrapper!.find('[data-testid="structurer-model-select"]').exists()).toBe(false);
    expect(wrapper!.text()).toContain("保存失败");
  });
});
