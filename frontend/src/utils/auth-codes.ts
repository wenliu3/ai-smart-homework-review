/**
 * 前端认证状态码配置
 * 定义不同认证错误的弹框显示配置
 */

/**
 * 认证错误码枚举
 */
export enum AuthErrorCode {
  // 401
  TOKEN_EXPIRED = 10002, // 令牌已过期
  INVALID_TOKEN = 10003, // 无效的令牌
  REFRESH_TOKEN_EXPIRED = 10004, // 刷新令牌已过期
  ACCOUNT_DISABLED = 10005, // 账号已禁用
  ACCOUNT_LOCKED = 10006, // 账号已锁定
  TOKEN_REVOKED = 10015, // 令牌已被撤销（登出）
  // INVALID_CREDENTIALS = 10001, // 移除：这是登录失败的业务错误，不应该弹框
  USER_INACTIVE = 10014, // 用户未激活
  REFRESH_TOKEN_INVALID = 10012, // 刷新令牌无效或已过期
}

/**
 * 弹框配置接口
 */
export interface AuthDialogConfig {
  title: string; // 弹框标题
  message: string; // 提示信息
  confirmButtonText: string; // 确认按钮文案
  showCancelButton: boolean; // 是否显示取消按钮
  type: "warning" | "error" | "info"; // 弹框类型
  needRedirect: boolean; // 是否需要重定向到登录页
}

/**
 * 认证错误配置映射
 */
export const AUTH_ERROR_CONFIGS: Record<AuthErrorCode, AuthDialogConfig> = {
  [AuthErrorCode.TOKEN_EXPIRED]: {
    title: "登录已过期",
    message: "您的登录已过期，请重新登录",
    confirmButtonText: "重新登录",
    showCancelButton: false,
    type: "warning",
    needRedirect: true,
  },

  [AuthErrorCode.INVALID_TOKEN]: {
    title: "登录状态异常",
    message: "登录状态异常，请重新登录",
    confirmButtonText: "重新登录",
    showCancelButton: false,
    type: "error",
    needRedirect: true,
  },

  [AuthErrorCode.REFRESH_TOKEN_EXPIRED]: {
    title: "会话已过期",
    message: "会话已过期，请重新登录",
    confirmButtonText: "重新登录",
    showCancelButton: false,
    type: "warning",
    needRedirect: true,
  },

  [AuthErrorCode.ACCOUNT_DISABLED]: {
    title: "账号已禁用",
    message: "您的账号已被管理员禁用，请联系管理员",
    confirmButtonText: "我知道了",
    showCancelButton: false,
    type: "error",
    needRedirect: true,
  },

  [AuthErrorCode.ACCOUNT_LOCKED]: {
    title: "账号已锁定",
    message: "您的账号已被锁定，请联系管理员解锁",
    confirmButtonText: "我知道了",
    showCancelButton: false,
    type: "error",
    needRedirect: true,
  },

  [AuthErrorCode.TOKEN_REVOKED]: {
    title: "已在其他设备登录",
    message: "您的账号已在其他设备登录或已被管理员登出，请重新登录",
    confirmButtonText: "重新登录",
    showCancelButton: false,
    type: "warning",
    needRedirect: true,
  },

  // 移除 INVALID_CREDENTIALS 的配置，因为它现在被当作普通业务错误处理

  [AuthErrorCode.USER_INACTIVE]: {
    title: "账号未激活",
    message: "您的账号尚未激活，请联系管理员激活",
    confirmButtonText: "我知道了",
    showCancelButton: false,
    type: "info",
    needRedirect: true,
  },

  [AuthErrorCode.REFRESH_TOKEN_INVALID]: {
    title: "登录会话过期",
    message: "您的登录会话已过期，需要重新登录",
    confirmButtonText: "重新登录",
    showCancelButton: false,
    type: "warning",
    needRedirect: true,
  },
};

/**
 * 默认认证错误配置
 */
export const DEFAULT_AUTH_CONFIG: AuthDialogConfig = {
  title: "认证失败",
  message: "认证失败，请重新登录",
  confirmButtonText: "重新登录",
  showCancelButton: false,
  type: "warning",
  needRedirect: true,
};

/**
 * 获取认证错误配置
 * @param code 错误码
 * @returns 弹框配置
 */
export function getAuthConfig(code?: string | number): AuthDialogConfig {
  if (!code) return DEFAULT_AUTH_CONFIG;

  const numCode = typeof code === "string" ? parseInt(code) : code;
  return AUTH_ERROR_CONFIGS[numCode as AuthErrorCode] || DEFAULT_AUTH_CONFIG;
}
