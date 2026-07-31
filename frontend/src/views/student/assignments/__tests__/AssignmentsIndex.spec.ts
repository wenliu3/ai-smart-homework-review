import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  getMyAssignments: vi.fn(),
  getMyAssignmentStatistics: vi.fn(),
}));

vi.mock("@/api/assignments", () => api);
vi.mock("vue-router", () => ({ useRouter: () => ({ push: vi.fn() }) }));

import AssignmentsIndex from "../index.vue";

describe("学生作业列表", () => {
  beforeEach(() => {
    api.getMyAssignments.mockResolvedValue({
      items: [
        {
          id: "21",
          title: "语料库分析",
          classId: "3",
          className: "自然语言处理",
          teacherName: "边国维",
          endDate: "2026-08-05T18:00:00",
          hasDraft: false,
          hasSubmitted: false,
          isExpired: false,
        },
      ],
      total: 1,
    });
    api.getMyAssignmentStatistics.mockResolvedValue({
      totalAssignments: 1,
      submittedCount: 0,
      todoCount: 1,
      draftCount: 0,
      expiredCount: 0,
      reviewedCount: 0,
    });
  });

  it("提供可直接切换的状态筛选并保留桌面与移动布局", async () => {
    const wrapper = mount(AssignmentsIndex, {
      global: {
        directives: { loading: () => undefined },
        stubs: {
          PageHeader: {
            template: "<header><slot /><slot name='actions' /></header>",
          },
          AdaptiveTableContainer: {
            template:
              "<main><slot name='search' /><slot name='table' table-height='480px' /><slot name='pagination' /></main>",
          },
          "el-card": { template: "<section><slot /></section>" },
          "el-button": { template: "<button><slot /></button>" },
          "el-empty": true,
          "el-icon": { template: "<i><slot /></i>" },
          "el-pagination": true,
          "el-tag": { template: "<span><slot /></span>" },
          "el-table": { template: "<div><slot /></div>" },
          "el-table-column": true,
        },
      },
    });
    await flushPromises();

    expect(wrapper.find('[data-testid="assignment-filter-all"]').exists()).toBe(
      true
    );
    expect(
      wrapper.find('[data-testid="assignment-filter-todo"]').exists()
    ).toBe(true);
    expect(wrapper.find(".assignment-list-desktop").exists()).toBe(true);
    expect(wrapper.find(".assignment-list-mobile").exists()).toBe(true);
  });
});
