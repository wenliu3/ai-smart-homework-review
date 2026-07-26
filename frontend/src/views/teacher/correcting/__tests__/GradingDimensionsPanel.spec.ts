import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { getRunArtifacts } = vi.hoisted(() => ({
  getRunArtifacts: vi.fn(),
}));

vi.mock("@/api/assistant", () => ({ getRunArtifacts }));

import GradingDimensionsPanel from "../components/GradingDimensionsPanel.vue";

const OUTCOME_ARTIFACT = {
  artifactType: "grading_outcome",
  schemaVersion: "v1",
  createdAt: "2026-07-26T20:00:00",
  payload: {
    needs_human_review: true,
    review_reasons: ["两次独立评分差异超过满分 10%"],
    primary: {
      items: [
        {
          criterion_id: "correctness",
          title: "正确性",
          score: 55,
          max_score: 60,
          feedback: "论证完整",
          evidence_refs: ["submission:text:1"],
        },
        {
          criterion_id: "clarity",
          title: "表达",
          score: 30,
          max_score: 40,
          feedback: "结构清晰",
          evidence_refs: [],
        },
      ],
    },
    review: {
      items: [
        {
          criterion_id: "correctness",
          title: "正确性",
          score: 48,
          max_score: 60,
          feedback: "部分论证缺依据",
          evidence_refs: ["submission:text:1"],
        },
      ],
    },
  },
};

function mountPanel(runId: string | null = "run-1") {
  return mount(GradingDimensionsPanel, {
    props: { runId },
    global: {
      stubs: {
        "el-alert": {
          template:
            '<div class="alert"><slot />{{ title }} {{ description }}</div>',
          props: ["title", "description", "type"],
        },
      },
    },
  });
}

describe("GradingDimensionsPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getRunArtifacts.mockResolvedValue({
      runId: "run-1",
      items: [OUTCOME_ARTIFACT],
    });
  });

  it("渲染分维度评分：主批改与复核分数并排，含评语与证据", async () => {
    const wrapper = mountPanel();
    await flushPromises();

    const row = wrapper.get('[data-testid="dimension-correctness"]');
    expect(row.text()).toContain("正确性");
    expect(row.text()).toContain("55 / 60");
    expect(row.text()).toContain("48 / 60");
    expect(row.text()).toContain("submission:text:1");
    // 复核缺某维度时显示占位
    expect(
      wrapper.get('[data-testid="dimension-clarity"]').text(),
    ).toContain("- / 40");
  });

  it("需要人工复核时展示原因", async () => {
    const wrapper = mountPanel();
    await flushPromises();

    const alert = wrapper.get('[data-testid="grading-review-alert"]');
    expect(alert.text()).toContain("两次独立评分差异超过满分 10%");
  });

  it("降级产物显示转人工提示", async () => {
    getRunArtifacts.mockResolvedValue({
      runId: "run-1",
      items: [{
        artifactType: "grading_raw_draft",
        schemaVersion: "v1",
        createdAt: null,
        payload: { stage: "grading_agent", error: "校验失败" },
      }],
    });
    const wrapper = mountPanel();
    await flushPromises();

    expect(
      wrapper.find('[data-testid="grading-degraded-alert"]').exists(),
    ).toBe(true);
    expect(
      wrapper.find('[data-testid="grading-dimensions-table"]').exists(),
    ).toBe(false);
  });

  it("没有 runId 时不请求也不渲染", async () => {
    const wrapper = mountPanel(null);
    await flushPromises();

    expect(getRunArtifacts).not.toHaveBeenCalled();
    expect(wrapper.find(".dimensions-panel").exists()).toBe(false);
  });

  it("产物接口报错时静默隐藏", async () => {
    getRunArtifacts.mockRejectedValue(new Error("404"));
    const wrapper = mountPanel();
    await flushPromises();

    expect(wrapper.find(".dimensions-panel").exists()).toBe(false);
  });
});
