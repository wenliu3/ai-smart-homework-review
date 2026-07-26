import { describe, expect, it } from "vitest";

import { buildDiffRows, formatDiffValue } from "../diff";

describe("buildDiffRows", () => {
  it("把 changes 与快照的差异标为 changed，并带上中文字段名", () => {
    const rows = buildDiffRows({
      assignmentId: 7,
      changes: { title: "新标题" },
      beforeSnapshot: { title: "旧标题", description: "描述" },
    });

    expect(rows).toEqual([
      {
        key: "title",
        label: "标题",
        before: "旧标题",
        after: "新标题",
        kind: "changed",
      },
    ]);
  });

  it("快照里没有的字段标为 added", () => {
    const rows = buildDiffRows({
      assignmentId: 7,
      changes: { description: "补充说明" },
      beforeSnapshot: { title: "旧标题" },
    });

    expect(rows[0].kind).toBe("added");
    expect(rows[0].before).toBe("");
  });

  it("值未变化的字段不产出行", () => {
    const rows = buildDiffRows({
      assignmentId: 7,
      changes: { title: "同样的标题" },
      beforeSnapshot: { title: "同样的标题" },
    });

    expect(rows).toEqual([]);
  });

  it("changes 里显式置空标为 removed", () => {
    const rows = buildDiffRows({
      assignmentId: 7,
      changes: { description: null },
      beforeSnapshot: { description: "原描述" },
    });

    expect(rows[0].kind).toBe("removed");
    expect(rows[0].before).toBe("原描述");
    expect(rows[0].after).toBe("");
  });

  it("无 changes 的动作（发布/删除）以 context 行展示对象当前信息", () => {
    const rows = buildDiffRows({
      assignmentId: 7,
      beforeSnapshot: { title: "第三章作业", status: "draft" },
    });

    expect(rows.map((row) => row.kind)).toEqual(["context", "context"]);
    expect(rows[0]).toMatchObject({ label: "标题", before: "第三章作业" });
  });

  it("保留键本身绝不参与 diff", () => {
    const rows = buildDiffRows({
      assignmentId: 7,
      changes: { title: "新标题" },
      beforeSnapshot: { title: "旧标题" },
    });

    const keys = rows.map((row) => row.key);
    expect(keys).not.toContain("assignmentId");
    expect(keys).not.toContain("beforeSnapshot");
  });

  it("没有快照的新建类动作把全部参数展示为 added", () => {
    const rows = buildDiffRows({
      title: "新作业",
      description: "说明",
    });

    expect(rows).toHaveLength(2);
    expect(rows.every((row) => row.kind === "added")).toBe(true);
  });

  it("完全没有可展示内容时返回空数组", () => {
    expect(buildDiffRows({ assignmentId: 7 })).toEqual([]);
    expect(buildDiffRows({})).toEqual([]);
  });

  it("嵌套对象与数组按 JSON 字符串比较且不抛错", () => {
    const rows = buildDiffRows({
      assignmentId: 7,
      changes: { classes: ["一班", "二班"] },
      beforeSnapshot: { classes: ["一班"] },
    });

    expect(rows[0].kind).toBe("changed");
    expect(rows[0].before).toContain("一班");
    expect(rows[0].after).toContain("二班");
  });

  it("非对象输入不抛错", () => {
    expect(buildDiffRows(null as never)).toEqual([]);
    expect(
      buildDiffRows({ changes: "not-an-object" } as never),
    ).toEqual([]);
  });
});

describe("formatDiffValue", () => {
  it("布尔值渲染成中文", () => {
    expect(formatDiffValue(true)).toBe("是");
    expect(formatDiffValue(false)).toBe("否");
  });

  it("空值渲染成空串", () => {
    expect(formatDiffValue(null)).toBe("");
    expect(formatDiffValue(undefined)).toBe("");
  });

  it("数字与字符串原样渲染", () => {
    expect(formatDiffValue(85)).toBe("85");
    expect(formatDiffValue("文本")).toBe("文本");
  });
});
