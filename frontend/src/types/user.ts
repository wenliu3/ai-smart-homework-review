/**
 * 用户相关类型定义
 */

// 用户角色类型
export type UserRole = "superadmin" | "teacher" | "student";

// 用户状态类型
export type UserStatus = "active" | "inactive";

// 用户基本信息
export interface User {
  _id: string;
  username: string;
  email: string;
  name: string;
  role: UserRole;
  status: UserStatus;
  studentId?: string;
  phone?: string;
  avatar?: string;
  meta?: Record<string, any>;
  permissions?: string[];
  lastLogin?: Date;
  createdAt?: Date;
  updatedAt?: Date;
  // 认证信息 - 仅在前端状态中使用
  token?: string;
  refreshToken?: string;
  tokenExpiresAt?: number;
}

// 创建用户DTO
export interface CreateUserDto {
  username: string;
  email: string;
  password: string;
  name: string;
  role?: UserRole;
  studentId?: string;
  phone?: string;
  status?: UserStatus;
  avatar?: string;
  meta?: Record<string, any>;
}

// 更新用户DTO
export interface UpdateUserDto {
  username?: string;
  email?: string;
  name?: string;
  role?: UserRole;
  studentId?: string;
  phone?: string;
  status?: UserStatus;
  avatar?: string;
  meta?: Record<string, any>;
}

// 用户查询参数
export interface UserQueryParams {
  page?: number;
  limit?: number;
  username?: string;
  email?: string;
  name?: string;
  status?: UserStatus;
  role?: UserRole;
  keyword?: string;
  sortField?: string;
  sortOrder?: "asc" | "desc";
}

// 用户列表响应
export interface UserListResponse {
  items: User[];
  total: number;
  page: number;
  limit: number;
}

// 修改密码DTO
export interface ChangePasswordDto {
  currentPassword: string;
  newPassword: string;
}
