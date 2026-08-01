import { flushPromises, shallowMount } from "@vue/test-utils";
import { createMemoryHistory, createRouter } from "vue-router";
import { describe, expect, it, vi } from "vitest";

import AssignmentDetail from "../index.vue";
import AssignmentContentPreviewDialog from "../components/AssignmentContentPreviewDialog.vue";
import AssignmentHeader from "../components/AssignmentHeader.vue";

vi.mock("@/api/assignments", () => ({
  getAssignmentDetail: vi.fn().mockResolvedValue({
    id: "21",
    title: "实验2：神雕侠侣语料库分析",
    description: "<p>完成语料库分析报告</p>",
    teacherId: "3",
    teacherName: "张老师",
    classes: [{ id: "8", name: "自然语言处理 (NLP)" }],
    startDate: "2026-07-30T19:30:00",
    endDate: "2026-08-06T18:59:00",
    status: "published",
    isExpired: false,
    allowAttachments: true,
    attachments: [],
    createdAt: "2026-07-30T10:00:00",
    updatedAt: "2026-07-30T10:00:00",
    totalStudents: 17,
    submissionStats: {
      totalSubmissions: 0,
      reviewedSubmissions: 0,
      pendingSubmissions: 0,
      draftSubmissions: 0,
      aiReviewed: 0,
      teacherReviewed: 0,
    },
  }),
  getAssignmentStudents: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  publishAssignment: vi.fn(),
  terminateAssignment: vi.fn(),
  AssignmentStatus: {},
}));

async function mountAssignmentDetail() {
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

  return { router, wrapper };
}

describe("AssignmentDetail", () => {
  it("从详情页编辑作业时进入已注册的编辑路由并保留作业 ID", async () => {
    const { router, wrapper } = await mountAssignmentDetail();

    wrapper.findComponent(AssignmentHeader).vm.$emit("edit");
    await flushPromises();

    expect(router.currentRoute.value.name).toBe("TeacherAssignmentsEdit");
    expect(router.currentRoute.value.query.id).toBe("21");
  });

  it("点击查看作业内容后打开弹窗并传入当前作业详情", async () => {
    const { wrapper } = await mountAssignmentDetail();

    wrapper.findComponent(AssignmentHeader).vm.$emit("preview");
    await wrapper.vm.$nextTick();

    const previewDialog = wrapper.findComponent(
      AssignmentContentPreviewDialog
    );
    expect(previewDialog.props("modelValue")).toBe(true);
    expect(previewDialog.props("assignmentDetail")?.id).toBe("21");
  });
});
