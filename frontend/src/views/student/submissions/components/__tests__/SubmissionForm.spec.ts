import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import SubmissionForm from "../SubmissionForm.vue";

const mountForm = () =>
  mount(SubmissionForm, {
    props: {
      assignment: {
        id: "21",
        title: "仅正文作业",
        dueDate: "2026-08-05T18:00:00",
        status: "published",
        allowAttachments: false,
      },
      submission: {
        id: "8",
        assignmentId: "21",
        studentId: "3",
        content: "<p>已有正文</p>",
        attachments: [
          {
            fileName: "旧草稿附件.pdf",
            fileUrl: "/uploads/old.pdf",
            fileSize: 128,
            fileType: "application/pdf",
          },
        ],
        wordCount: 4,
        status: "draft" as const,
        submittedAt: null,
        updatedAt: "2026-08-01T12:00:00",
        createdAt: "2026-08-01T12:00:00",
        isDraft: true,
        submissionCount: 1,
      },
      isOverdue: false,
    },
    global: {
      stubs: {
        WangEditor: {
          props: ["modelValue"],
          template: '<textarea data-testid="editor" />',
        },
        "el-alert": { template: "<section><slot /></section>" },
        "el-button": { template: "<button><slot /></button>" },
        "el-icon": { template: "<i><slot /></i>" },
        "el-progress": true,
      },
    },
  });

const mountAttachmentEnabledForm = () =>
  mount(SubmissionForm, {
    props: {
      assignment: {
        id: "22",
        title: "附件作业",
        dueDate: "2026-08-05T18:00:00",
        status: "published",
        allowAttachments: true,
      },
      submission: null,
      isOverdue: false,
    },
    global: {
      stubs: {
        WangEditor: { template: '<textarea data-testid="editor" />' },
        "el-alert": { template: "<section><slot /></section>" },
        "el-button": { template: "<button><slot /></button>" },
        "el-icon": { template: "<i><slot /></i>" },
        "el-progress": true,
      },
    },
  });

describe("SubmissionForm", () => {
  it("教师禁止附件时隐藏上传入口并从提交参数中剔除历史附件", () => {
    const wrapper = mountForm();

    expect(wrapper.text()).toContain("本作业仅支持正文提交");
    expect(wrapper.find(".upload-card").exists()).toBe(false);
    expect(
      (wrapper.vm as unknown as { getUploadedAttachments: () => unknown[] })
        .getUploadedAttachments()
    ).toEqual([]);
  });

  it("教师允许附件时保留上传入口", () => {
    const wrapper = mountAttachmentEnabledForm();

    expect(wrapper.find(".upload-card").exists()).toBe(true);
    expect(wrapper.text()).toContain("上传附件");
  });
});
