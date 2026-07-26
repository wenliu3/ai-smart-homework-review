export type AssistantRole = "teacher" | "student" | "superadmin";

export interface AssistantRoleConfig {
  role: AssistantRole;
  title: string;
  welcome: string;
  capabilities: string[];
  inputPlaceholder: string;
  safetyNotice: string;
  canApprove: boolean;
}

const ROLE_CONFIGS: Record<AssistantRole, AssistantRoleConfig> = {
  teacher: {
    role: "teacher",
    title: "AI教学助手",
    welcome: "你好！我是你的 AI 教学助手",
    capabilities: [
      "教学数据查询",
      "教学策略建议",
      "批改与查重解释",
      "写操作草案与审批",
    ],
    inputPlaceholder: "请输入教学问题，回车发送，Shift+回车换行",
    safetyNotice: "发布、修改、删除和改分只会生成草案，需你本人在审批面板确认后才执行。",
    canApprove: true,
  },
  student: {
    role: "student",
    title: "AI学习助手",
    welcome: "你好！我是你的 AI 学习助手",
    capabilities: ["启发式学习辅导", "本人反馈解释", "学习规划建议"],
    inputPlaceholder: "请输入学习问题，回车发送，Shift+回车换行",
    safetyNotice: "助手会提供思路和提示，请独立完成并提交自己的作业。",
    canApprove: false,
  },
  superadmin: {
    role: "superadmin",
    title: "AI管理助手",
    welcome: "你好！我是你的 AI 管理助手",
    capabilities: ["聚合运营分析", "脱敏审计", "模型治理"],
    inputPlaceholder: "请输入管理问题，回车发送，Shift+回车换行",
    safetyNotice: "写操作只有在审批载荷复验通过后才会执行。",
    canApprove: true,
  },
};

export function isAssistantRole(role: unknown): role is AssistantRole {
  return (
    role === "teacher" ||
    role === "student" ||
    role === "superadmin"
  );
}

export function getAssistantRoleConfig(
  role: unknown,
): AssistantRoleConfig | null {
  return isAssistantRole(role) ? ROLE_CONFIGS[role] : null;
}
