import DOMPurify from "dompurify";
import { marked } from "marked";

marked.setOptions({ breaks: true, async: false });

function normalizeMarkdown(content: string): string {
  return content
    .replace(/^(#{1,6})([^\s#])/gm, "$1 $2")
    .replace(/^([-*])([^\s*-])/gm, "$1 $2");
}

export function renderSafeMarkdown(content: string): string {
  if (!content) return "";

  try {
    const rendered = marked.parse(normalizeMarkdown(content), { async: false });
    const html = typeof rendered === "string" ? rendered : content;
    return DOMPurify.sanitize(html, {
      USE_PROFILES: { html: true },
      // 聊天场景不需要图片：外链 <img> 可被用作数据外带通道（URL 携带敏感内容）
      FORBID_TAGS: ["img"],
    });
  } catch {
    return DOMPurify.sanitize(content, {
      USE_PROFILES: { html: true },
      FORBID_TAGS: ["img"],
    });
  }
}
