/**
 * AI功能配置
 */
export const AI_CONFIG = {
  // AI功能上线时间（早于此时间的作业可能不支持AI评价）
  FEATURE_LAUNCH_DATE: new Date("2024-01-01"),

  // 轮询配置
  POLLING: {
    MAX_COUNT: 60, // 最大轮询次数（约5-8分钟）
    TIMEOUT_MS: 30000, // 超时时间（30秒）

    // 渐进式轮询间隔
    INTERVALS: {
      INITIAL: 3000, // 前10次：每3秒
      MEDIUM: 5000, // 10-22次：每5秒
      SLOW: 8000, // 22-40次：每8秒
      FINAL: 15000, // 40次后：每15秒
    },
  },

  // AI评价条件检查
  REQUIREMENTS: {
    // 是否检查作业创建时间
    CHECK_CREATION_DATE: true,

    // 是否检查AI规则配置
    CHECK_AI_RULES: true,

    // 是否检查作业状态
    CHECK_ASSIGNMENT_STATUS: true,
  },
};

/**
 * 检查作业是否过期
 */
export function isAssignmentOverdue(assignment: any): boolean {
  if (!assignment || !assignment.dueDate) {
    return false;
  }

  const dueDate = new Date(assignment.dueDate);
  const now = new Date();

  return now > dueDate;
}

/**
 * 检查作业是否支持AI评价
 */
export function checkAiSupport(assignment: any): {
  supported: boolean;
  reason: string;
} {
  if (!assignment) {
    return { supported: false, reason: "作业信息不存在" };
  }

  // 检查作业状态
  if (AI_CONFIG.REQUIREMENTS.CHECK_ASSIGNMENT_STATUS) {
    if (assignment.status === "terminated") {
      return { supported: false, reason: "作业已终止" };
    }

    if (assignment.status === "draft") {
      return { supported: false, reason: "作业为草稿状态" };
    }
  }

  // 检查作业是否过期
  if (isAssignmentOverdue(assignment)) {
    return { supported: false, reason: "作业已过期，不支持AI评价" };
  }

  // 检查创建时间
  if (AI_CONFIG.REQUIREMENTS.CHECK_CREATION_DATE && assignment.createdAt) {
    const createdAt = new Date(assignment.createdAt);
    if (createdAt < AI_CONFIG.FEATURE_LAUNCH_DATE) {
      return { supported: false, reason: "历史作业，不支持AI评价" };
    }
  }

  // 检查AI规则配置
  if (AI_CONFIG.REQUIREMENTS.CHECK_AI_RULES) {
    if (!assignment.aiRule || !assignment.aiRule.prompt) {
      return { supported: false, reason: "作业未配置AI评价规则" };
    }
  }

  return { supported: true, reason: "支持AI评价" };
}
