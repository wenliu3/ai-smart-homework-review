/**
 * 运行步骤时间线（规划阶段 5.4）：从 SSE 事件流累积步骤状态。
 *
 * 纯函数，与 API 模块解耦（组件单测 mock @/api/assistant 不受影响）。
 * 内部 agent 标识符一律映射为中文，未知名称回退通用文案，绝不透出。
 */

export interface TimelineStep {
  key: string;
  label: string;
  status: "running" | "done";
}

const AGENT_LABELS: Record<string, string> = {
  teacher_data_agent: "查询教学数据",
  teaching_data: "查询教学数据",
  teacher_strategy_agent: "生成教学策略",
  teaching_strategy: "生成教学策略",
  teacher_action_agent: "起草待审批操作",
  final_reviewer_agent: "安全审核",
  final_reviewer: "安全审核",
  learning_coach_agent: "学习辅导",
  feedback_explainer_agent: "解释学习反馈",
  learning_planner_agent: "制定学习规划",
  student_final_reviewer: "安全审核",
  operations_analysis_agent: "运营分析",
  audit_analysis_agent: "脱敏审计",
  model_governance_agent: "模型治理分析",
  admin_final_reviewer: "安全审核",
};

export function agentLabel(name: unknown): string {
  if (typeof name !== "string" || !name) return "处理中";
  return AGENT_LABELS[name] || "处理中";
}

/** 把一个 SSE 事件并入时间线；返回新数组（不可变更新）。 */
export function reduceTimelineEvent(
  steps: TimelineStep[],
  event: { type: string; data?: Record<string, any> },
): TimelineStep[] {
  if (event.type === "route.selected") {
    if (steps.some((step) => step.key === "route")) return steps;
    return [...steps, { key: "route", label: "分析请求", status: "done" }];
  }
  if (event.type === "agent.started") {
    const agent = String(event.data?.agent ?? "");
    if (!agent || steps.some((step) => step.key === agent)) return steps;
    return [...steps, {
      key: agent,
      label: agentLabel(agent),
      status: "running",
    }];
  }
  if (event.type === "agent.completed") {
    const agent = String(event.data?.agent ?? "");
    return steps.map((step) =>
      step.key === agent ? { ...step, status: "done" as const } : step,
    );
  }
  return steps;
}
