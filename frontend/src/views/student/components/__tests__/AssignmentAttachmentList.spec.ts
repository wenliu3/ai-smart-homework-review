import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import AssignmentAttachmentList from "../AssignmentAttachmentList.vue";

const attachments = [
  {
    fileName: "实验说明.pdf",
    fileUrl: "/uploads/guide.pdf",
    fileSize: 1024,
    fileType: "application/pdf",
  },
  {
    fileName: "实验模板.docx",
    fileUrl: "/uploads/template.docx",
    fileSize: 2 * 1024 * 1024,
    fileType:
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  },
];

const elementStubs = {
  "el-button": {
    emits: ["click"],
    template:
      '<button type="button" @click="$emit(\'click\')"><slot /></button>',
  },
  "el-icon": { template: "<i><slot /></i>" },
};

describe("AssignmentAttachmentList", () => {
  it("展示附件名称、文件大小和类型标识", () => {
    const wrapper = mount(AssignmentAttachmentList, {
      props: { attachments },
      global: {
        stubs: elementStubs,
      },
    });

    expect(wrapper.text()).toContain("实验说明.pdf");
    expect(wrapper.text()).toContain("1 KB");
    expect(wrapper.text()).toContain("PDF");
    expect(wrapper.text()).toContain("实验模板.docx");
    expect(wrapper.text()).toContain("2 MB");
    expect(wrapper.text()).toContain("DOCX");
  });

  it("点击下载时向父组件发送对应附件", async () => {
    const wrapper = mount(AssignmentAttachmentList, {
      props: { attachments },
      global: {
        stubs: elementStubs,
      },
    });

    await wrapper.findAll("button")[1].trigger("click");

    expect(wrapper.emitted("download")).toEqual([[attachments[1]]]);
  });

  it("没有附件时不渲染附件区域", () => {
    const wrapper = mount(AssignmentAttachmentList, {
      props: { attachments: [] },
      global: { stubs: elementStubs },
    });

    expect(wrapper.find(".assignment-attachment-list").exists()).toBe(false);
  });
});
