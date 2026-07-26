/**
 * 运行产物摘要（规划 5.4）：把 /assistant/runs/{id}/artifacts 的产物
 * 压缩成用户可读的中文条目，挂在对应回答气泡下方。
 *
 * 安全要求同 timeline.ts：
 * - 未知产物类型直接跳过，绝不透出内部 artifact_type 标识符。
 * - evidence_refs 可能含内部资源 ID，只展示条数，不展示内容。
 */

export interface ArtifactCardItem {
  label: string;
  detail: string;
}

const DETAIL_MAX_CHARS = 60;

function truncate(text: string): string {
  if (text.length <= DETAIL_MAX_CHARS) return text;
  return `${text.slice(0, DETAIL_MAX_CHARS)}…`;
}

function reviewDetail(payload: Record<string, any> | null): string {
  if (!payload || typeof payload !== "object") return "已完成";
  if (payload.approved === true) return "已通过";
  if (payload.approved === false) {
    const issues = Array.isArray(payload.issues) ? payload.issues : [];
    const first = typeof issues[0] === "string" ? issues[0] : "";
    return first ? truncate(`未通过：${first}`) : "未通过，回答已调整";
  }
  return "已完成";
}

function specialistDetail(payload: Record<string, any> | null): string {
  if (!payload || typeof payload !== "object") return "已归档";
  const evidence = Array.isArray(payload.evidence_refs)
    ? payload.evidence_refs.length
    : 0;
  const limitations = Array.isArray(payload.limitations)
    ? payload.limitations.length
    : 0;
  const parts: string[] = [];
  if (evidence > 0) parts.push(`引用 ${evidence} 条数据`);
  if (limitations > 0) parts.push(`${limitations} 项局限说明`);
  return parts.length > 0 ? parts.join("，") : "已归档";
}

/** 把产物列表压缩为卡片条目；未知类型跳过，异常输入返回空数组。 */
export function summarizeArtifacts(
  items: Array<{ artifactType?: string; payload?: Record<string, any> | null }>,
): ArtifactCardItem[] {
  if (!Array.isArray(items)) return [];
  const cards: ArtifactCardItem[] = [];
  for (const item of items) {
    if (!item || typeof item !== "object") continue;
    if (item.artifactType === "review_result") {
      cards.push({ label: "安全审核", detail: reviewDetail(item.payload ?? null) });
    } else if (item.artifactType === "specialist_response") {
      cards.push({ label: "回答依据", detail: specialistDetail(item.payload ?? null) });
    }
  }
  return cards;
}
