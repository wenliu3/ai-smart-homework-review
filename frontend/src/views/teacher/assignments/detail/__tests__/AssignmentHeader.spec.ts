import ElementPlus from "element-plus";
import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import { AssignmentStatus } from "@/api/assignments";
import type { AssignmentDetail } from "@/api/assignments";
import AssignmentHeader from "../components/AssignmentHeader.vue";

function createAssignmentDetail(
  status: AssignmentStatus
): AssignmentDetail {
  return {
    id: "21",
    title: "实验2：神雕侠侣语料库分析",
    description: "<p>完成语料库分析报告</p>",
    teacherId: "3",
    teacherName: "张老师",
    classes: [{ id: "8", name: "自然语言处理 (NLP)" }],
    startDate: "2026-07-30T19:30:00",
    endDate: "2026-08-06T18:59:00",
    status,
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
  };
}

function mountHeader(assignmentDetail: AssignmentDetail | null) {
  return mount(AssignmentHeader, {
    props: { assignmentDetail },
    global: { plugins: [ElementPlus] },
  });
}

describe("AssignmentHeader", () => {
  it("已发布作业显示查看作业内容并发出 preview 事件", async () => {
    const wrapper = mountHeader(
      createAssignmentDetail(AssignmentStatus.PUBLISHED)
    );
    const previewButton = wrapper.get(
      '[data-testid="preview-assignment"]'
    );

    expect(previewButton.text()).toContain("查看作业内容");
    await previewButton.trigger("click");

    expect(wrapper.emitted("preview")).toHaveLength(1);
  });

  it("草稿作业显示预览作业内容", () => {
    const wrapper = mountHeader(createAssignmentDetail(AssignmentStatus.DRAFT));

    expect(
      wrapper.get('[data-testid="preview-assignment"]').text()
    ).toContain("预览作业内容");
  });

  it("作业详情尚未加载时禁用内容按钮", () => {
    const wrapper = mountHeader(null);

    expect(
      wrapper.get('[data-testid="preview-assignment"]').attributes("disabled")
    ).toBeDefined();
  });
});
