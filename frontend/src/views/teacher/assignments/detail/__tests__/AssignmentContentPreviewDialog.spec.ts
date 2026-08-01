import ElementPlus from "element-plus";
import { defineComponent } from "vue";
import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import { AssignmentStatus } from "@/api/assignments";
import type { AssignmentDetail } from "@/api/assignments";
import AssignmentContentPreviewDialog from "../components/AssignmentContentPreviewDialog.vue";

const DialogStub = defineComponent({
  props: {
    modelValue: Boolean,
  },
  emits: ["update:modelValue"],
  template: `
    <section v-if="modelValue" data-testid="preview-dialog">
      <slot />
      <footer><slot name="footer" /></footer>
    </section>
  `,
});

function createAssignmentDetail(
  overrides: Partial<AssignmentDetail> = {}
): AssignmentDetail {
  return {
    id: "21",
    title: "实验2：神雕侠侣语料库分析",
    description:
      '<p>完成语料库分析报告</p><script>window.hacked = true</script>',
    teacherId: "3",
    teacherName: "张老师",
    classes: [{ id: "8", name: "自然语言处理 (NLP)" }],
    startDate: "2026-07-30T19:30:00",
    endDate: "2026-08-06T18:59:00",
    status: AssignmentStatus.PUBLISHED,
    isExpired: false,
    allowAttachments: true,
    attachments: [
      {
        fileName: "实验2-语料库分析.docx",
        fileUrl: "/uploads/assignment-21.docx",
        fileSize: 2048,
        fileType:
          "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      },
    ],
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
    ...overrides,
  };
}

function mountDialog(assignmentDetail: AssignmentDetail) {
  return mount(AssignmentContentPreviewDialog, {
    props: {
      modelValue: true,
      assignmentDetail,
    },
    global: {
      plugins: [ElementPlus],
      stubs: { ElDialog: DialogStub },
    },
  });
}

const richDescription = `
  <h2>实验说明</h2>
  <p style="text-align: center; color: rgb(79, 115, 232);">
    <strong>保留格式</strong>
  </p>
  <p><br></p>
  <p>第一段</p>
  <blockquote>引用内容</blockquote>
  <ol><li>第一项</li><li><em>第二项</em></li></ol>
  <pre><code>const answer = 42;</code></pre>
  <table><tbody><tr><td>单元格</td></tr></tbody></table>
  <img src="/uploads/example.png" onerror="window.hacked = true">
  <script>window.hacked = true</script>
`;

describe("AssignmentContentPreviewDialog", () => {
  it("按编辑器 HTML 原顺序呈现安全富文本，不做正文重排", () => {
    const wrapper = mountDialog(
      createAssignmentDetail({ description: richDescription })
    );

    const content = wrapper.get(".assignment-description");

    expect(content.classes()).toContain("editor-content-view");
    expect(content.find("h2").text()).toBe("实验说明");
    expect(content.find("p[style]").attributes("style")).toContain(
      "text-align: center"
    );
    expect(content.find("strong").text()).toBe("保留格式");
    expect(content.findAll("p")[1].html()).toContain("<br>");
    expect(content.find("blockquote").text()).toBe("引用内容");
    expect(content.findAll("ol > li").map((item) => item.text())).toEqual([
      "第一项",
      "第二项",
    ]);
    expect(content.find("pre code").text()).toBe("const answer = 42;");
    expect(content.find("table td").text()).toBe("单元格");
    expect(content.find("img").attributes("onerror")).toBeUndefined();
    expect(content.find("script").exists()).toBe(false);
    expect(content.find(".generated-summary").exists()).toBe(false);
    expect(content.find(".generated-callout").exists()).toBe(false);
  });

  it("只读展示发布内容、元数据和附件，并净化不安全 HTML", () => {
    const wrapper = mountDialog(createAssignmentDetail());

    expect(wrapper.text()).toContain("实验2：神雕侠侣语料库分析");
    expect(wrapper.text()).toContain("自然语言处理 (NLP)");
    expect(wrapper.text()).toContain("2026年07月30日 19:30");
    expect(wrapper.text()).toContain("2026年08月06日 18:59");
    expect(wrapper.text()).toContain("完成语料库分析报告");
    expect(
      wrapper.get(".assignment-description").find("script").exists()
    ).toBe(false);
    expect(wrapper.text()).toContain("实验2-语料库分析.docx");
    expect(wrapper.text()).toContain("2 KB");
  });

  it("描述和附件为空时显示空状态，关闭按钮只关闭弹窗", async () => {
    const wrapper = mountDialog(
      createAssignmentDetail({ description: "", attachments: [] })
    );

    expect(wrapper.text()).toContain("暂无作业要求");
    expect(wrapper.text()).toContain("暂无作业附件");

    await wrapper.get('[data-testid="close-preview"]').trigger("click");

    expect(wrapper.emitted("update:modelValue")).toEqual([[false]]);
  });
});
