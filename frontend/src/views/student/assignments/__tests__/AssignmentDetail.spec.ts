import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";

const getStudentAssignment = vi.hoisted(() => vi.fn());

vi.mock("@/api/assignments", () => ({ getStudentAssignment }));
vi.mock("vue-router", () => ({
  useRoute: () => ({ params: { id: "21" }, query: { classId: "3" } }),
  useRouter: () => ({ back: vi.fn(), push: vi.fn() }),
}));

import AssignmentAttachmentList from "../../components/AssignmentAttachmentList.vue";
import AssignmentDetail from "../detail.vue";

describe("学生作业详情", () => {
  beforeEach(() => {
    getStudentAssignment.mockResolvedValue({
      id: "21",
      title: "语料库分析",
      description: "<p>完成实验报告</p>",
      teacherName: "边国维",
      endDate: "2026-08-05T18:00:00",
      status: "in_progress",
      isExpired: false,
      hasDraft: false,
      hasSubmitted: false,
      attachments: [
        {
          fileName: "实验2-语料库分析.docx",
          fileUrl: "/uploads/assignment.docx",
          fileSize: 23459,
          fileType:
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        },
      ],
    });
  });

  it("使用共享附件组件展示教师附件", async () => {
    const wrapper = mount(AssignmentDetail, {
      global: {
        stubs: {
          "el-button": {
            emits: ["click"],
            template: '<button type="button"><slot /></button>',
          },
          "el-icon": { template: "<i><slot /></i>" },
          "el-tag": { template: "<span><slot /></span>" },
        },
        directives: { loading: () => undefined },
      },
    });
    await flushPromises();

    expect(wrapper.findComponent(AssignmentAttachmentList).exists()).toBe(true);
    expect(wrapper.text()).toContain("实验2-语料库分析.docx");
  });
});
