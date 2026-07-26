import { mount, flushPromises } from "@vue/test-utils";
import { nextTick } from "vue";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { listApprovals, approveAction, rejectAction } = vi.hoisted(() => ({
  listApprovals: vi.fn(),
  approveAction: vi.fn(),
  rejectAction: vi.fn(),
}));

vi.mock("@/api/assistant", () => ({
  listApprovals,
  approveAction,
  rejectAction,
}));

import AssistantApprovalView from "../AssistantApprovalView.vue";

const approval = {
  approvalId: "approval-1",
  runId: "run-1",
  actionType: "update_model_config",
  targetType: "model_config",
  targetId: "model-1",
  parameters: { modelName: "safe-model", status: 1 },
  summary: "更新模型配置",
  riskLevel: "high",
  status: "pending",
  expiresAt: "2026-07-25T12:00:00",
  result: null,
};

describe("AssistantApprovalView", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    listApprovals.mockResolvedValue({ items: [approval] });
    approveAction.mockResolvedValue({ status: "executed" });
    rejectAction.mockResolvedValue({ ...approval, status: "rejected" });
  });

  it("loads pending approvals and approves with original parameters", async () => {
    const wrapper = mount(AssistantApprovalView, {
      global: {
        stubs: {
          "el-button": {
            template: '<button :disabled="disabled"><slot /></button>',
            props: ["disabled"],
          },
          "el-input": {
            template: "<textarea />",
          },
          "el-empty": { template: "<div>暂无待审批操作</div>" },
          "el-alert": { template: "<div><slot /></div>" },
        },
      },
    });
    await flushPromises();

    expect(listApprovals).toHaveBeenCalledWith("pending");
    expect(wrapper.text()).toContain("更新模型配置");
    expect(wrapper.text()).toContain("safe-model");

    await wrapper.get('[data-testid="approve-approval-1"]').trigger("click");
    expect(wrapper.text()).toContain("再次点击确认");
    await wrapper.get('[data-testid="approve-approval-1"]').trigger("click");
    await flushPromises();

    expect(approveAction).toHaveBeenCalledWith(
      "approval-1",
      approval.parameters,
    );
  });

  it("并发审批时各卡片独立禁用，任一请求结束只解禁自己", async () => {
    const approval2 = {
      ...approval,
      approvalId: "approval-2",
      summary: "另一个待审批操作",
    };
    listApprovals.mockResolvedValue({ items: [approval, approval2] });

    let resolveApprove!: (value: any) => void;
    approveAction.mockReturnValue(
      new Promise((resolve) => {
        resolveApprove = resolve;
      }),
    );

    const wrapper = mount(AssistantApprovalView, {
      global: {
        stubs: {
          "el-button": {
            template: '<button :disabled="disabled"><slot /></button>',
            props: ["disabled"],
          },
          "el-input": { template: "<textarea />" },
          "el-empty": { template: "<div />" },
          "el-alert": { template: "<div><slot /></div>" },
        },
      },
    });
    await flushPromises();

    // 双击确认批准第一个审批（请求挂起中）
    await wrapper.get('[data-testid="approve-approval-1"]').trigger("click");
    await wrapper.get('[data-testid="approve-approval-1"]').trigger("click");
    await nextTick();

    // 第一个卡片的两个按钮均禁用，第二个卡片不受影响
    expect(
      wrapper.get('[data-testid="approve-approval-1"]').attributes("disabled"),
    ).toBeDefined();
    expect(
      wrapper.get('[data-testid="reject-approval-1"]').attributes("disabled"),
    ).toBeDefined();
    expect(
      wrapper.get('[data-testid="approve-approval-2"]').attributes("disabled"),
    ).toBeUndefined();
    expect(
      wrapper.get('[data-testid="reject-approval-2"]').attributes("disabled"),
    ).toBeUndefined();

    resolveApprove({ status: "executed", result: null });
    await flushPromises();

    // 请求结束后自己解禁
    expect(
      wrapper.get('[data-testid="approve-approval-1"]').attributes("disabled"),
    ).toBeUndefined();
  });

  it("does not reject with a blank reason", async () => {
    const wrapper = mount(AssistantApprovalView, {
      global: {
        stubs: {
          "el-button": {
            template: '<button :disabled="disabled"><slot /></button>',
            props: ["disabled"],
          },
          "el-input": { template: "<textarea />" },
          "el-empty": { template: "<div />" },
          "el-alert": { template: "<div><slot /></div>" },
        },
      },
    });
    await flushPromises();

    await wrapper.get('[data-testid="reject-approval-1"]').trigger("click");
    expect(rejectAction).not.toHaveBeenCalled();
    expect(wrapper.text()).toContain("请输入拒绝原因");
  });
});
