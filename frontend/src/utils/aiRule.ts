/**
 * AI 规则快照工具 — 快照统一携带 maxScore（旧数据缺失时兜底 100）。
 */

/**
 * 归一化规则快照：保证返回对象带 maxScore，缺失时按 100 兜底。
 * @param rule 规则对象（可为完整规则或简化快照，含可选 maxScore）
 */
export function normalizeAiRuleSnapshot<T>(
  rule: T & { maxScore?: number },
): T & { maxScore: number } {
  return { ...rule, maxScore: rule.maxScore ?? 100 };
}
