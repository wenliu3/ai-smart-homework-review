import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../../router", () => ({
  default: { push: vi.fn() },
}));

vi.mock("../../../api/auth", () => ({
  login: vi.fn(),
  register: vi.fn(),
  logout: vi.fn(),
  refreshToken: vi.fn(),
  getUserInfo: vi.fn(),
}));

import userModule from "../user";

describe("user session state", () => {
  beforeEach(() => localStorage.clear());

  it("新登录会话完整替换旧账号字段", () => {
    const state = userModule.state();
    state.userInfo = {
      token: "student-token",
      refreshToken: "student-refresh",
      role: "student",
      studentId: "2024041",
    };

    userModule.mutations.REPLACE_USER_INFO(state, {
      token: "teacher-token",
      refreshToken: "teacher-refresh",
      role: "teacher",
      username: "teacher",
    });

    expect(state.userInfo).toEqual({
      token: "teacher-token",
      refreshToken: "teacher-refresh",
      role: "teacher",
      username: "teacher",
    });
    expect(state.userInfo.studentId).toBeUndefined();
    expect(localStorage.getItem("token")).toBe("teacher-token");
  });

  it("清理会话同时清除内存和本地存储", () => {
    const state = userModule.state();
    state.userInfo = { token: "old-token", refreshToken: "old-refresh" };
    (state as any).refreshPromise = Promise.resolve();
    localStorage.setItem("token", "old-token");
    localStorage.setItem("userInfo", JSON.stringify(state.userInfo));

    userModule.mutations.CLEAR_SESSION(state);

    expect(state.userInfo).toBeNull();
    expect(state.refreshPromise).toBeNull();
    expect(localStorage.getItem("token")).toBeNull();
    expect(localStorage.getItem("userInfo")).toBeNull();
  });
});
