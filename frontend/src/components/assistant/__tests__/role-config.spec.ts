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

  it("only grants the approval view to superadmin", () => {
    expect(getAssistantRoleConfig("teacher")?.canApprove).toBe(false);
    expect(getAssistantRoleConfig("student")?.canApprove).toBe(false);
    expect(getAssistantRoleConfig("superadmin")?.canApprove).toBe(true);
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
