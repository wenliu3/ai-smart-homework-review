import { flushPromises, shallowMount } from "@vue/test-utils";
import { createMemoryHistory, createRouter } from "vue-router";
import { describe, expect, it, vi } from "vitest";

import AssignmentDetail from "../index.vue";
import AssignmentHeader from "../components/AssignmentHeader.vue";

vi.mock("@/api/assignments", () => ({
  getAssignmentDetail: vi.fn().mockResolvedValue(null),
  getAssignmentStudents: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  publishAssignment: vi.fn(),
  terminateAssignment: vi.fn(),
  AssignmentStatus: {},
}));

describe("AssignmentDetail", () => {
  it("从详情页编辑作业时进入已注册的编辑路由并保留作业 ID", async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        {
          path: "/teacher/assignments/detail",
          component: AssignmentDetail,
        },
        {
          path: "/teacher/assignmentsEdit",
          name: "TeacherAssignmentsEdit",
          component: { template: "<div>assignment editor</div>" },
        },
      ],
    });

    await router.push({
      path: "/teacher/assignments/detail",
      query: { id: "21" },
    });
    await router.isReady();

    const wrapper = shallowMount(AssignmentDetail, {
      global: {
        plugins: [router],
        stubs: { "el-pagination": true },
      },
    });
    await flushPromises();

    wrapper.findComponent(AssignmentHeader).vm.$emit("edit");
    await flushPromises();

    expect(router.currentRoute.value.name).toBe("TeacherAssignmentsEdit");
    expect(router.currentRoute.value.query.id).toBe("21");
  });
});
