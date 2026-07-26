/**
 * 审批相关的纯展示映射。
 *
 * 刻意不放在 `@/api/assistant`：审批相关组件的单测会用 vi.mock 整体替换
 * 该模块，把纯函数放这里可避免每个 mock 工厂都得跟着补导出。
 */
import type { ApprovalActionType } from "@/api/assistant";

/** approval.required 事件负载：只含审批提示所需的安全字段。 */
export interface ApprovalRequiredPayload {
  approvalId: string;
  actionType: ApprovalActionType;
  targetType: string;
  targetId: string | null;
  riskLevel: "low" | "medium" | "high";
  summary: string;
  expiresAt: string;
}

const ACTION_TYPE_LABELS: Record<string, string> = {
  create_assignment_draft: "创建作业草稿",
  create_ai_rule: "创建 AI 批改规则",
  submit_teacher_score: "提交教师评分",
  update_model_config: "修改模型配置",
  publish_assignment: "发布作业",
  update_assignment: "修改作业",
  delete_assignment: "删除作业",
};

/** 把动作类型映射为中文；未知类型原样返回，避免界面出现空白。 */
export function approvalActionLabel(actionType: string): string {
  return ACTION_TYPE_LABELS[actionType] || actionType;
}

/** 把 approval.required 事件的 snake_case 负载转成前端使用的驼峰结构。 */
export function parseApprovalRequired(
  data: Record<string, any> | undefined | null,
): ApprovalRequiredPayload | null {
  const approvalId = data?.approval_id;
  if (typeof approvalId !== "string" || !approvalId) return null;
  return {
    approvalId,
    actionType: data?.action_type,
    targetType: data?.target_type ?? "",
    targetId: data?.target_id ?? null,
    riskLevel: data?.risk_level ?? "high",
    summary: typeof data?.summary === "string" ? data.summary : "",
    expiresAt: typeof data?.expires_at === "string" ? data.expires_at : "",
  };
}
