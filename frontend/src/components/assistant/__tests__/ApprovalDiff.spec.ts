import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import ApprovalDiff from "../ApprovalDiff.vue";

function mountDiff(parameters: Record<string, unknown>) {
  return mount(ApprovalDiff, { props: { parameters } });
}

describe("ApprovalDiff", () => {
  it("渲染变更字段的原值与新值", () => {
    const wrapper = mountDiff({
      assignmentId: 7,
      changes: { title: "新标题" },
      beforeSnapshot: { title: "旧标题" },
    });

    const row = wrapper.get('[data-testid="diff-row-title"]');
    expect(row.text()).toContain("旧标题");
    expect(row.text()).toContain("新标题");
    expect(row.classes()).toContain("row-changed");
  });

  it("发布/删除类动作展示对象当前信息与说明文案", () => {
    const wrapper = mountDiff({
      assignmentId: 7,
      beforeSnapshot: { title: "第三章作业", status: "draft" },
    });

    expect(wrapper.text()).toContain("第三章作业");
    expect(wrapper.text()).toContain("本次操作不修改这些字段");
    // 没有变更时不显示「新值」列
    expect(wrapper.find("thead").exists()).toBe(false);
  });

  it("没有任何可展示内容时给出明确提示", () => {
    const wrapper = mountDiff({ assignmentId: 7 });

    expect(wrapper.text()).toContain("本次操作不修改任何字段");
  });

  it("不暴露 beforeSnapshot 等内部键名", () => {
    const wrapper = mountDiff({
      assignmentId: 7,
      changes: { title: "新标题" },
      beforeSnapshot: { title: "旧标题" },
    });

    expect(wrapper.text()).not.toContain("beforeSnapshot");
    expect(wrapper.text()).not.toContain("assignmentId");
  });

  it("用中文字段名而不是原始键名", () => {
    const wrapper = mountDiff({
      changes: { allowAttachments: true },
      beforeSnapshot: { allowAttachments: false },
    });

    expect(wrapper.text()).toContain("允许学生上传附件");
    expect(wrapper.text()).toContain("是");
  });
});
