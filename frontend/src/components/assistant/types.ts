export interface RenderedAssistantMessage {
  role: "user" | "assistant";
  content: string;
  html: string;
  /** 普通文本气泡，或聊天流中内嵌的待审批草案卡片。 */
  kind?: "text" | "approval";
  approval?: ApprovalCardData;
}

/** approval.required 事件在聊天流里渲染成的卡片数据（只含安全字段）。 */
export interface ApprovalCardData {
  approvalId: string;
  actionType: string;
  targetType: string;
  targetId: string | null;
  riskLevel: string;
  summary: string;
  expiresAt: string;
}

/** 审批草案的单行字段级差异。 */
export interface DiffRow {
  key: string;
  label: string;
  before: string;
  after: string;
  kind: "added" | "changed" | "removed" | "context";
}
