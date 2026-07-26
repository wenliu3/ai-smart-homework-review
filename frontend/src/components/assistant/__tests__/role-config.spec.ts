import { describe, expect, it } from "vitest";

import {
  getAssistantRoleConfig,
  isAssistantRole,
} from "../role-config";

describe("assistant role config", () => {
  it.each([
    ["teacher", "AI教学助手"],
    ["student", "AI学习助手"],
    ["superadmin", "AI管理助手"],
  ])("maps %s to the expected title", (role, title) => {
    expect(getAssistantRoleConfig(role)?.title).toBe(title);
    expect(isAssistantRole(role)).toBe(true);
  });

  it("grants the approval view to teacher and superadmin only", () => {
    expect(getAssistantRoleConfig("teacher")?.canApprove).toBe(true);
    expect(getAssistantRoleConfig("superadmin")?.canApprove).toBe(true);
    expect(getAssistantRoleConfig("student")?.canApprove).toBe(false);
  });

  it("tells teachers that write operations need their own approval", () => {
    const teacher = getAssistantRoleConfig("teacher");

    expect(teacher?.safetyNotice).toContain("审批");
    expect(teacher?.capabilities.join("")).toContain("审批");
  });

  it("does not fall back to teacher for an unknown role", () => {
    expect(getAssistantRoleConfig("guest")).toBeNull();
    expect(getAssistantRoleConfig(undefined)).toBeNull();
    expect(isAssistantRole("guest")).toBe(false);
  });

  it("provides role-specific copy", () => {
    const student = getAssistantRoleConfig("student");
    const admin = getAssistantRoleConfig("superadmin");

    expect(student?.welcome).toContain("学习");
    expect(student?.safetyNotice).toContain("独立完成");
    expect(admin?.welcome).toContain("管理");
    expect(admin?.capabilities.join("")).toContain("审计");
  });
});
