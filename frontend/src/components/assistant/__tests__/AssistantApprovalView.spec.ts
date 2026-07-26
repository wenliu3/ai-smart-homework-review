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

describe("AssistantApprovalView 已处理标签", () => {
  const executed = {
    ...approval,
    approvalId: "approval-done",
    summary: "发布《第三章作业》",
    actionType: "publish_assignment",
    targetType: "assignment",
    parameters: {
      assignmentId: 7,
      beforeSnapshot: { title: "第三章作业", status: "draft" },
    },
    status: "executed",
    result: { success: true },
  };

  function mountView() {
    return mount(AssistantApprovalView, {
      global: {
        stubs: {
          "el-button": {
            template: '<button :disabled="disabled"><slot /></button>',
            props: ["disabled"],
          },
          "el-empty": { template: "<div />" },
          "el-alert": { template: "<div><slot /></div>" },
        },
      },
    });
  }

  beforeEach(() => {
    vi.clearAllMocks();
    listApprovals.mockResolvedValue({ items: [approval, executed] });
    approveAction.mockResolvedValue({ status: "executed" });
    rejectAction.mockResolvedValue({ ...approval, status: "rejected" });
  });

  it("默认只拉待审批，切到已处理后拉全量并剔除 pending", async () => {
    const wrapper = mountView();
    await flushPromises();
    expect(listApprovals).toHaveBeenCalledWith("pending");

    await wrapper.get('[data-testid="approval-tab-history"]').trigger("click");
    await flushPromises();

    expect(listApprovals).toHaveBeenLastCalledWith(undefined);
    expect(wrapper.text()).toContain("发布《第三章作业》");
    expect(wrapper.text()).not.toContain("更新模型配置");
  });

  it("已处理项不渲染批准/拒绝按钮，改为展示执行结果", async () => {
    const wrapper = mountView();
    await flushPromises();
    await wrapper.get('[data-testid="approval-tab-history"]').trigger("click");
    await flushPromises();

    expect(
      wrapper.find('[data-testid="approve-approval-done"]').exists(),
    ).toBe(false);
    expect(
      wrapper.find('[data-testid="reject-approval-done"]').exists(),
    ).toBe(false);
    expect(wrapper.text()).toContain("执行成功");
  });

  it("切换标签会清掉未完成的二次确认状态", async () => {
    const wrapper = mountView();
    await flushPromises();

    await wrapper.get('[data-testid="approve-approval-1"]').trigger("click");
    expect(wrapper.text()).toContain("再次点击确认");

    await wrapper.get('[data-testid="approval-tab-history"]').trigger("click");
    await flushPromises();
    await wrapper.get('[data-testid="approval-tab-pending"]').trigger("click");
    await flushPromises();

    expect(wrapper.text()).not.toContain("再次点击确认");
    expect(wrapper.text()).toContain("批准并执行");
  });

  it("参数区用字段级 diff 渲染，不再输出原始 JSON", async () => {
    listApprovals.mockResolvedValue({
      items: [{
        ...approval,
        actionType: "update_assignment",
        parameters: {
          assignmentId: 7,
          changes: { title: "新标题" },
          beforeSnapshot: { title: "旧标题" },
        },
      }],
    });
    const wrapper = mountView();
    await flushPromises();

    expect(wrapper.text()).toContain("旧标题");
    expect(wrapper.text()).toContain("新标题");
    expect(wrapper.text()).not.toContain("beforeSnapshot");
  });

  it("操作类型显示中文而不是内部标识符", async () => {
    const wrapper = mountView();
    await flushPromises();
    await wrapper.get('[data-testid="approval-tab-history"]').trigger("click");
    await flushPromises();

    expect(wrapper.text()).toContain("发布作业");
    expect(wrapper.text()).not.toContain("publish_assignment");
  });
});
