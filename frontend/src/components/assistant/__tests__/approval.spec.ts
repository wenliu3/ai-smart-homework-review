import { describe, expect, it } from "vitest";

import { approvalActionLabel, parseApprovalRequired } from "../approval";

describe("parseApprovalRequired", () => {
  it("把 snake_case 事件负载转成驼峰结构", () => {
    const payload = parseApprovalRequired({
      approval_id: "approval-1",
      action_type: "publish_assignment",
      target_type: "assignment",
      target_id: "7",
      risk_level: "high",
      summary: "发布《第三章作业》",
      expires_at: "2026-07-26T20:00:00",
    });

    expect(payload).toEqual({
      approvalId: "approval-1",
      actionType: "publish_assignment",
      targetType: "assignment",
      targetId: "7",
      riskLevel: "high",
      summary: "发布《第三章作业》",
      expiresAt: "2026-07-26T20:00:00",
    });
  });

  it("缺少 approval_id 时返回 null，不产生半截卡片", () => {
    expect(parseApprovalRequired({ summary: "无 ID" })).toBeNull();
    expect(parseApprovalRequired({ approval_id: "" })).toBeNull();
    expect(parseApprovalRequired(undefined)).toBeNull();
    expect(parseApprovalRequired(null)).toBeNull();
  });

  it("缺省字段退化为安全默认值", () => {
    const payload = parseApprovalRequired({ approval_id: "approval-2" });

    expect(payload?.riskLevel).toBe("high");
    expect(payload?.targetId).toBeNull();
    expect(payload?.summary).toBe("");
  });
});

describe("approvalActionLabel", () => {
  it.each([
    ["publish_assignment", "发布作业"],
    ["update_assignment", "修改作业"],
    ["delete_assignment", "删除作业"],
    ["submit_teacher_score", "提交教师评分"],
  ])("%s 显示为中文 %s", (actionType, label) => {
    expect(approvalActionLabel(actionType)).toBe(label);
  });

  it("未知动作原样返回，不留空白", () => {
    expect(approvalActionLabel("brand_new_action")).toBe("brand_new_action");
  });
});
