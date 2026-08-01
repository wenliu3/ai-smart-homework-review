import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";

const dispatch = vi.fn().mockResolvedValue(undefined);
const push = vi.fn();

vi.mock("vuex", () => ({
  useStore: () => ({
    getters: {
      "dashboard/isLoading": () => false,
      "dashboard/studentStats": {
        completedSubmissions: 3,
        averageScore: 88,
        joinedClasses: 2,
        onTimeRate: 92,
        pendingAssignments: 1,
        pendingAssignmentsList: [
          {
            assignmentId: "21",
            classId: "3",
            title: "语料库分析",
            className: "自然语言处理",
            status: "not_started",
            endDate: new Date(Date.now() + 2 * 60 * 60 * 1000).toISOString(),
          },
        ],
        recentSubmissions: [],
        submissionStatusStats: [],
        performanceAnalysis: {
          excellentCount: 1,
          goodCount: 1,
          passCount: 1,
        },
      },
      "user/getUserInfo": { name: "测试学生" },
    },
    dispatch,
  }),
}));
vi.mock("vue-router", () => ({ useRouter: () => ({ push }) }));

import StudentDashboard from "../StudentDashboard.vue";

describe("StudentDashboard", () => {
  it("将紧急待办放在图表之前并突出临近截止", async () => {
    const wrapper = mount(StudentDashboard, {
      global: {
        stubs: {
          StatCard: {
            props: ["title", "subtitle"],
            template:
              "<article class='stat-card-stub'>{{ title }} {{ subtitle }}</article>",
          },
          DonutChart: true,
          BarChart: true,
          "el-button": { template: "<button><slot /></button>" },
          "el-icon": { template: "<i><slot /></i>" },
          "el-empty": true,
          "el-tag": { template: "<span><slot /></span>" },
          "el-table": true,
          "el-table-column": true,
        },
      },
    });
    await flushPromises();

    const html = wrapper.html();
    expect(wrapper.text()).toContain("测试学生");
    expect(wrapper.text()).toContain("当前还有 1 项作业待完成");
    expect(wrapper.text()).toContain("已评价");
    expect(wrapper.text()).toContain("累计");
    expect(wrapper.find('[data-testid="priority-todos"]').exists()).toBe(true);
    expect(wrapper.find(".todo-item--urgent").exists()).toBe(true);
    expect(html.indexOf('data-testid="priority-todos"')).toBeLessThan(
      html.indexOf('data-testid="dashboard-charts"')
    );
  });
});
