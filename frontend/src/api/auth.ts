import request from "@/utils/request";
import type {
  LoginParams,
  LoginResult,
  RefreshTokenResult,
  ChangePasswordParams,
} from "@/types/auth";

/**
 * 用户登录
 */
export const login = (data: LoginParams): Promise<LoginResult> => {
  return request({
    url: "/v1/auth/login",
    method: "post",
    data,
  });
};

/**
 * 用户退出登录
 */
export const logout = (): Promise<{ success: boolean }> => {
  return request({
    url: "/v1/auth/logout",
    method: "post",
  });
};

/**
 * 刷新访问令牌
 */
export const refreshToken = (
  refreshToken: string
): Promise<RefreshTokenResult> => {
  return request({
    url: "/v1/auth/refresh-token",
    method: "post",
    data: { refreshToken },
  });
};

/**
 * 获取当前用户信息
 */
export function getUserInfo() {
  return request({
    url: "/v1/auth/profile",
    method: "get",
  });
}

/**
 * 修改密码
 */
export function changePassword(data: ChangePasswordParams) {
  return request<{ message: string }>({
    url: "/v1/auth/password",
    method: "put",
    data,
  });
}

/**
 * 首次登录强制修改密码
 */
export function firstChangePassword(data: ChangePasswordParams) {
  return request<{ message: string }>({
    url: "/v1/auth/first-password-change",
    method: "put",
    data,
  });
}
