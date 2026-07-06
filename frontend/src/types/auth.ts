/**
 * 登录参数
 */
export interface LoginParams {
  usernameOrEmailOrStudentId: string;
  password: string;
  rememberMe?: boolean;
}

/**
 * 登录结果
 */
export interface LoginResult {
  token: string;
  refreshToken: string;
  expiresIn: number;
  userId?: string;
  mustChangePassword?: boolean; // 是否需要强制修改密码
  isFirstLogin?: boolean; // 是否首次登录
  user?: {
    id: string;
    username: string;
    email: string;
    name: string;
    role: string;
    mustChangePassword: boolean;
  };
}

/**
 * 用户信息
 */
export interface UserInfo {
  id: string;
  username: string;
  name: string;
  avatar?: string;
  email?: string;
  role: string;
  status: "active" | "inactive" | "locked";
  mustChangePassword?: boolean; // 是否需要强制修改密码
  firstLoginAt?: string; // 首次登录时间
  createdAt: string;
  updatedAt: string;
}

/**
 * 刷新Token结果
 */
export interface RefreshTokenResult {
  token: string;
  refreshToken?: string;
  expiresIn: number;
}

/**
 * 修改密码参数
 */
export interface ChangePasswordParams {
  currentPassword: string;
  newPassword: string;
  confirmPassword: string;
}

/**
 * 忘记密码参数
 */
export interface ForgotPasswordParams {
  email: string;
}

/**
 * 重置密码参数
 */
export interface ResetPasswordParams {
  token: string;
  password: string;
  confirmPassword: string;
}

/**
 * 统一API响应结构
 */
export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: {
    code: string;
    message: string;
  };
}
