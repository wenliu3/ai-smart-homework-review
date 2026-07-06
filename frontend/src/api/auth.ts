import request from "@/utils/request";
import type {
  LoginParams,
  LoginResult,
  UserInfo,
  RefreshTokenResult,
  ChangePasswordParams,
  ResetPasswordParams,
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

/**
 * 忘记密码请求
 */
export const forgotPassword = (
  email: string
): Promise<{ success: boolean }> => {
  return request({
    url: "/v1/auth/forgot-password",
    method: "post",
    data: { email },
  });
};

/**
 * 重置密码
 */
export const resetPassword = (
  token: string,
  password: string
): Promise<{ success: boolean }> => {
  return request({
    url: "/v1/auth/reset-password",
    method: "post",
    data: { token, password },
  });
};

/**
 * 用户注册
 */
export interface RegisterParams {
  username: string;
  password: string;
  confirmPassword: string;
  email: string;
  name?: string;
}

export interface RegisterResult {
  token: string;
  success: boolean;
  message: string;
  userId?: string;
  expiresIn: number;
}

export const register = (data: RegisterParams): Promise<RegisterResult> => {
  return request({
    url: "/v1/auth/register",
    method: "post",
    data,
  });
};
