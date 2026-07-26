/**
 * 审批草案的字段级 diff（规划阶段 3A.4 / 决策 D2）。
 *
 * 旧值快照由后端在创建草案时冻结在 payload.beforeSnapshot 里并参与哈希复验，
 * 因此这里只做纯展示：绝不修改 parameters，也绝不把改动回传给审批接口
 * （后端会逐字节复验载荷，任何改动都会被 400 拒绝）。
 */
import type { DiffRow } from "./types";

/** 服务端注入的保留键，只用于定位对象与展示，不参与 diff。 */
const RESERVED_KEYS = new Set(["assignmentId", "beforeSnapshot"]);

const FIELD_LABELS: Record<string, string> = {
  title: "标题",
  description: "描述",
  classes: "班级",
  startDate: "开始时间",
  endDate: "截止时间",
  allowAttachments: "允许学生上传附件",
  status: "状态",
  teacherScore: "教师评分",
  teacherReviewContent: "教师评语",
  submissionId: "提交记录",
  maxScore: "满分",
  prompt: "提示词",
  modelType: "模型类型",
  visibility: "可见性",
  tags: "标签",
  name: "名称",
  code: "编码",
  modelName: "模型名称",
  baseUrl: "接口地址",
  isDefault: "设为默认",
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return (
    typeof value === "object" && value !== null && !Array.isArray(value)
  );
}

/** 把任意参数值渲染成可读文本；空值统一为空串，供界面显示占位。 */
export function formatDiffValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "";
  if (typeof value === "boolean") return value ? "是" : "否";
  if (typeof value === "number") return String(value);
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

export function diffFieldLabel(key: string): string {
  return FIELD_LABELS[key] || key;
}

/**
 * 由审批载荷推导字段级 diff 行。
 *
 * - `changes` 存在时逐字段比对快照，产出 changed / added / removed。
 * - 没有 `changes`（发布、删除等）时，用快照产出 context 行，
 *   让审批人看清这次操作作用在哪个对象上。
 * - 没有快照的新建类动作，全部参数按 added 展示。
 */
export function buildDiffRows(
  parameters: Record<string, unknown>,
): DiffRow[] {
  if (!isRecord(parameters)) return [];

  const snapshot = isRecord(parameters.beforeSnapshot)
    ? parameters.beforeSnapshot
    : {};

  let changes: Record<string, unknown>;
  if ("changes" in parameters) {
    // changes 存在但不是对象：视为无可展示变更，不猜测
    changes = isRecord(parameters.changes) ? parameters.changes : {};
  } else {
    changes = Object.fromEntries(
      Object.entries(parameters).filter(([key]) => !RESERVED_KEYS.has(key)),
    );
  }

  if (Object.keys(changes).length === 0) {
    return Object.entries(snapshot).map(([key, value]) => ({
      key,
      label: diffFieldLabel(key),
      before: formatDiffValue(value),
      after: "",
      kind: "context" as const,
    }));
  }

  const rows: DiffRow[] = [];
  for (const [key, next] of Object.entries(changes)) {
    if (RESERVED_KEYS.has(key)) continue;
    const hasBefore = Object.prototype.hasOwnProperty.call(snapshot, key);
    const before = formatDiffValue(snapshot[key]);
    const after = formatDiffValue(next);
    if (before === after) continue;
    let kind: DiffRow["kind"];
    if (!hasBefore || before === "") {
      kind = "added";
    } else if (after === "") {
      kind = "removed";
    } else {
      kind = "changed";
    }
    rows.push({ key, label: diffFieldLabel(key), before, after, kind });
  }
  return rows;
}
