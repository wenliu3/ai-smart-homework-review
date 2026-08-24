import request from "@/utils/request";
import type {
  User,
  UserListResponse,
  CreateUserDto,
} from "@/types/user";

/**
 * 获取用户详细信息（管理员编辑用户时使用）
 * @param userId 用户ID
 * @returns 用户详细信息
 */
export const getUser = (userId: string): Promise<User> => {
  return request({
    url: `/users/${userId}`,
    method: "get",
  });
};

/**
 * 更新用户信息（单角色设计：role 随本接口直接修改）
 * @param userId 用户ID
 * @param data 更新的数据
 * @returns 更新后的用户信息
 */
export const updateUser = (
  userId: string,
  data: Partial<User>
): Promise<User> => {
  if (!userId) {
    return Promise.reject(new Error("用户ID不能为空"));
  }

  // 创建一个新对象，避免修改原始数据
  const updateData = { ...data };

  // 移除不可修改的字段
  delete updateData.username;
  delete updateData._id;
  delete updateData.createdAt;
  delete updateData.updatedAt;

  return request({
    url: `/users/${userId}`,
    method: "patch",
    data: updateData,
  });
};

// 获取用户列表的参数
export interface GetUsersParams {
  role?: string;
  page?: number;
  limit?: number;
  sortField?: string;
  sortOrder?: "asc" | "desc";
  keyword?: string;
}

/**
 * 获取用户列表（仅超级管理员；支持按角色筛选）
 */
export const getUsers = (
  params?: GetUsersParams
): Promise<UserListResponse> => {
  return request({
    url: "/users",
    method: "get",
    params,
  });
};

/**
 * 创建用户（仅超级管理员）
 */
export const createUser = (data: CreateUserDto): Promise<User> => {
  return request({
    url: "/users",
    method: "post",
    data,
  });
};

/**
 * 删除用户（仅超级管理员）
 */
export const deleteUser = (
  id: string
): Promise<{ success: boolean; message: string }> => {
  return request({
    url: `/users/${id}`,
    method: "delete",
  });
};

/**
 * 重置用户密码（仅超级管理员）
 * @param userId 用户ID
 * @param newPassword 可选的新密码，不提供则使用系统默认密码
 * @returns 操作结果
 */
export const resetUserPassword = (
  userId: string,
  newPassword?: string
): Promise<{ success: boolean; message: string }> => {
  const data = newPassword ? { newPassword } : {};

  return request({
    url: `/users/${userId}/reset-password`,
    method: "post",
    data,
  });
};

/**
 * 批量导入用户（教师/超级管理员）
 * @param users 用户数据数组
 * @returns 导入结果
 */
export const importUsersBatch = (users: any[]): Promise<any> => {
  return request({
    url: "/users/batch-import",
    method: "post",
    data: users,
  });
};

/**
 * 批量删除用户（仅超级管理员）
 * @param userIds 用户ID数组
 * @returns 删除结果
 */
export const deleteUsersBatch = (
  userIds: string[]
): Promise<{
  success: boolean;
  total: number;
  successCount: number;
  failureCount: number;
  failures?: Array<{
    userId: string;
    reason: string;
  }>;
}> => {
  return request({
    url: "/users/batch-delete",
    method: "post",
    data: { userIds },
  });
};
