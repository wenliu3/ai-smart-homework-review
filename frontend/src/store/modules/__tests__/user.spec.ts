import { createStore } from "vuex";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../../router", () => ({
  default: { push: vi.fn() },
}));

vi.mock("../../../store", () => ({
  default: { dispatch: vi.fn() },
}));

vi.mock("../../../api/auth", () => ({
  login: vi.fn(),
  register: vi.fn(),
  logout: vi.fn(),
  refreshToken: vi.fn(),
  getUserInfo: vi.fn(),
}));

import { login, refreshToken } from "../../../api/auth";
import { auth } from "../auth";
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

  it("替换为不含 token 的会话时删除旧 token", () => {
    const state = userModule.state();
    localStorage.setItem("token", "old-token");

    userModule.mutations.REPLACE_USER_INFO(state, {
      role: "teacher",
      username: "teacher",
    });

    expect(state.userInfo).toEqual({
      role: "teacher",
      username: "teacher",
    });
    expect(localStorage.getItem("token")).toBeNull();
  });

  it("登录成功时先清旧权限，再完整替换新会话", async () => {
    const events: string[] = [];
    const store = createStore<any>({
      modules: {
        user: userModule,
        auth,
      },
      plugins: [
        (store) => {
          store.subscribe((mutation) => events.push(mutation.type));
        },
      ],
    });
    store.state.user.userInfo = {
      token: "student-token",
      refreshToken: "student-refresh",
      role: "student",
      studentId: "2024041",
    };
    store.state.auth.roles = ["student"];
    store.state.auth.permissions = ["assignment:submit"];
    store.state.auth.menus = [{ path: "/student/assignments" }];
    vi.mocked(login).mockResolvedValue({
      token: "teacher-token",
      refreshToken: "teacher-refresh",
      expiresIn: 3600,
      mustChangePassword: false,
      isFirstLogin: false,
      user: {
        id: "teacher-1",
        username: "teacher",
        email: "teacher@example.com",
        name: "Teacher",
        role: "teacher",
        mustChangePassword: false,
      },
    });

    await store.dispatch("user/login", {
      usernameOrEmailOrStudentId: "teacher",
      password: "password",
      rememberMe: true,
    });

    expect(events).toEqual([
      "auth/CLEAR_AUTH_STATE",
      "user/REPLACE_USER_INFO",
    ]);
    expect(store.state.auth).toMatchObject({
      roles: [],
      permissions: [],
      menus: [],
    });
    expect(store.state.user.userInfo).toMatchObject({
      token: "teacher-token",
      refreshToken: "teacher-refresh",
      role: "teacher",
      username: "teacher",
    });
    expect(store.state.user.userInfo.studentId).toBeUndefined();
  });

  it("缺少刷新令牌时只抛错，不清理现有会话", async () => {
    const store = createStore<any>({ modules: { user: userModule } });
    store.state.user.userInfo = { token: "existing-token", role: "teacher" };

    await expect(store.dispatch("user/refreshToken")).rejects.toThrow(
      "登录已过期，请重新登录"
    );

    expect(store.state.user.userInfo).toEqual({
      token: "existing-token",
      role: "teacher",
    });
  });

  it("刷新接口失败时保留会话，并在 finally 清除刷新 Promise", async () => {
    const store = createStore<any>({ modules: { user: userModule } });
    store.state.user.userInfo = {
      token: "existing-token",
      refreshToken: "existing-refresh",
      role: "teacher",
    };
    const refreshError = new Error("refresh failed");
    vi.mocked(refreshToken).mockRejectedValue(refreshError);

    await expect(store.dispatch("user/refreshToken")).rejects.toBe(
      refreshError
    );

    expect(store.state.user.userInfo).toEqual({
      token: "existing-token",
      refreshToken: "existing-refresh",
      role: "teacher",
    });
    expect(store.state.user.refreshPromise).toBeNull();
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
