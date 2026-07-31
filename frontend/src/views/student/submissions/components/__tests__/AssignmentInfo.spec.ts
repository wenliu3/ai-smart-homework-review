import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import AssignmentInfo from "../AssignmentInfo.vue";

const assignment = {
  id: "21",
  title: "语料库分析",
  description: "<p>阅读附件后完成实验报告</p>",
  attachments: [
    {
      fileName: "实验2-语料库分析.docx",
      fileUrl: "/uploads/assignment.docx",
      fileSize: 23459,
      fileType:
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    },
  ],
  allowAttachments: true,
  dueDate: "2026-08-05T18:00:00",
  maxScore: 100,
  teacherName: "边国维",
  aiRule: null,
  status: "published" as const,
};

describe("AssignmentInfo", () => {
  it("展示状态摘要、截止时间和教师附件", () => {
    const wrapper = mount(AssignmentInfo, {
      props: {
        assignment,
        submission: null,
        statusTagType: "warning",
        statusText: "未知状态",
        isOverdue: false,
      },
      global: {
        stubs: {
          "el-icon": { template: "<i><slot /></i>" },
          "el-button": {
            emits: ["click"],
            template: '<button type="button"><slot /></button>',
          },
        },
      },
    });

    expect(wrapper.get('[data-testid="assignment-status"]').text()).toContain(
      "待提交"
    );
    expect(wrapper.get('[data-testid="assignment-deadline"]').text()).toContain(
      "2026"
    );
    expect(wrapper.text()).toContain("边国维");
    expect(wrapper.text()).toContain("实验2-语料库分析.docx");
    expect(wrapper.text()).toContain("22.9 KB");
  });

  it("过期时突出展示已截止状态", () => {
    const wrapper = mount(AssignmentInfo, {
      props: {
        assignment,
        submission: null,
        statusTagType: "danger",
        statusText: "未提交",
        isOverdue: true,
      },
      global: {
        stubs: {
          "el-icon": { template: "<i><slot /></i>" },
          "el-button": {
            emits: ["click"],
            template: '<button type="button"><slot /></button>',
          },
        },
      },
    });

    expect(wrapper.get('[data-testid="assignment-status"]').text()).toContain(
      "已截止"
    );
  });
});
