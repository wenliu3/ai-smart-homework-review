import { describe, expect, it } from "vitest";

import {
  getResponseErrorMessage,
  isPublicAuthRequest,
  shouldAttachAccessToken,
  shouldAttemptTokenRefresh,
} from "../auth-request";

describe("auth request policy", () => {
  it.each([
    "/v1/auth/login",
    "/api/v1/auth/login?redirect=%2F",
    "/v1/auth/register",
    "/v1/auth/forgot-password",
    "/v1/auth/reset-password",
    "/v1/auth/refresh-token",
    "/auth/login",
    "/auth/register",
  ])("将 %s 识别为公开认证请求", (url) => {
    expect(isPublicAuthRequest(url)).toBe(true);
    expect(shouldAttachAccessToken(url)).toBe(false);
    expect(shouldAttemptTokenRefresh(401, url, false)).toBe(false);
  });

  it("只对未重试过的受保护 401 请求刷新令牌", () => {
    expect(
      shouldAttemptTokenRefresh(401, "/teacher/assignments", false)
    ).toBe(true);
    expect(
      shouldAttemptTokenRefresh(401, "/teacher/assignments", true)
    ).toBe(false);
    expect(
      shouldAttemptTokenRefresh(403, "/teacher/assignments", false)
    ).toBe(false);
  });

  it("保留后端认证错误消息", () => {
    expect(
      getResponseErrorMessage({ message: "账号或密码错误" }, "登录失败")
    ).toBe("账号或密码错误");
  });
});
