import { describe, expect, it } from "vitest";

import { summarizeArtifacts } from "../artifacts";

describe("summarizeArtifacts", () => {
  it("审核通过与专家依据映射为中文条目", () => {
    const cards = summarizeArtifacts([
      {
        artifactType: "specialist_response",
        payload: {
          answer: "回答正文",
          evidence_refs: ["assignments:1", "submissions:2"],
          limitations: ["数据截至昨天"],
        },
      },
      {
        artifactType: "review_result",
        payload: { approved: true, issues: [] },
      },
    ]);

    expect(cards).toEqual([
      { label: "回答依据", detail: "引用 2 条数据，1 项局限说明" },
      { label: "安全审核", detail: "已通过" },
    ]);
  });

  it("审核未通过展示第一条问题并截断，不透出内部结构", () => {
    const longIssue = "辅".repeat(100);
    const cards = summarizeArtifacts([
      {
        artifactType: "review_result",
        payload: { approved: false, issues: [longIssue] },
      },
    ]);

    expect(cards[0].label).toBe("安全审核");
    expect(cards[0].detail.startsWith("未通过：")).toBe(true);
    expect(cards[0].detail.length).toBeLessThanOrEqual(61);
    expect(cards[0].detail.endsWith("…")).toBe(true);
  });

  it("evidence_refs 内容绝不出现在摘要里，只展示条数", () => {
    const cards = summarizeArtifacts([
      {
        artifactType: "specialist_response",
        payload: { answer: "x", evidence_refs: ["secret_table:99"], limitations: [] },
      },
    ]);

    expect(cards[0].detail).toBe("引用 1 条数据");
    expect(cards[0].detail).not.toContain("secret_table");
  });

  it("未知产物类型跳过，不透出 artifact_type 标识符", () => {
    const cards = summarizeArtifacts([
      { artifactType: "dimension_results", payload: { foo: 1 } },
      { artifactType: "review_result", payload: { approved: true } },
    ]);

    expect(cards).toHaveLength(1);
    expect(cards[0].label).toBe("安全审核");
  });

  it("异常输入不抛错", () => {
    expect(summarizeArtifacts(null as never)).toEqual([]);
    expect(summarizeArtifacts([null as never, {} as never])).toEqual([]);
    expect(
      summarizeArtifacts([
        { artifactType: "review_result", payload: null },
        { artifactType: "specialist_response", payload: null },
      ]),
    ).toEqual([
      { label: "安全审核", detail: "已完成" },
      { label: "回答依据", detail: "已归档" },
    ]);
  });
});
