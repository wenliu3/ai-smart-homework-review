import { mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

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

const mountResubmissionForm = () =>
  mount(SubmissionForm, {
    props: {
      assignment: {
        id: "21",
        title: "附件作业",
        dueDate: "2026-08-05T18:00:00",
        status: "published",
        allowAttachments: true,
      },
      submission: {
        id: "8",
        assignmentId: "21",
        studentId: "3",
        content: "<p>已提交正文</p>",
        attachments: [
          {
            fileName: "正式提交附件.pdf",
            fileUrl: "/uploads/submitted.pdf",
            fileSize: 128,
            fileType: "application/pdf",
          },
        ],
        wordCount: 6,
        status: "submitted" as const,
        submittedAt: "2026-08-01T12:00:00",
        updatedAt: "2026-08-01T12:00:00",
        createdAt: "2026-08-01T12:00:00",
        isDraft: false,
        submissionCount: 1,
      },
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
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true }));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

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

  it("取消重新提交并卸载表单时不删除正式提交的历史附件", () => {
    const wrapper = mountResubmissionForm();

    wrapper.unmount();

    expect(fetch).not.toHaveBeenCalled();
  });

  it("移除历史附件后取消重新提交时不删除正式提交文件", async () => {
    const wrapper = mountResubmissionForm();
    const submittedAttachments = wrapper.props("submission")!.attachments;

    await wrapper.get(".file-remove").trigger("click");
    wrapper.unmount();

    expect(fetch).not.toHaveBeenCalled();
    expect(submittedAttachments).toHaveLength(1);
    expect(submittedAttachments[0].fileUrl).toBe(
      "/uploads/submitted.pdf"
    );
  });
});
