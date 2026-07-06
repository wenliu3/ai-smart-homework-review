import request from "@/utils/request";
import type {
  User,
  UserQueryParams,
  UserListResponse,
  CreateUserDto,
  UpdateUserDto,
} from "@/types/user";

/**
 * 登录
 * @param credentials 登录凭证
 * @returns 登录结果
 */
export const login = (credentials: { email: string; password: string }) => {
  return request({
    url: "/auth/login",
    method: "post",
    data: credentials,
  });
};

/**
 * 注册
 * @param userData 用户数据
 * @returns 注册结果
 */
export const register = (userData: {
  name: string;
  email: string;
  password: string;
}) => {
  return request({
    url: "/auth/register",
    method: "post",
    data: userData,
  });
};

/**
 * 获取用户详细信息
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
 * 获取当前用户个人资料
 * @returns 当前用户资料
 */
export const getUserProfile = (): Promise<User> => {
  return request({
    url: "/users/profile",
    method: "get",
  });
};

/**
 * 更新用户个人资料
 * @param userData 用户资料数据
 * @returns 更新后的资料
 */
export const updateUserProfile = (userData: any) => {
  return request({
    url: "/users/profile",
    method: "put",
    data: userData,
  });
};

/**
 * 更新用户信息
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

/**
 * 更改密码
 * @param passwordData 密码数据
 * @returns 操作结果
 */
export const changePassword = (passwordData: {
  currentPassword: string;
  newPassword: string;
}) => {
  return request({
    url: "/users/password",
    method: "put",
    data: passwordData,
  });
};

/**
 * 更新用户密码
 * @param userId 用户ID
 * @param data 新旧密码
 * @returns 操作结果
 */
export const updateUserPassword = (
  userId: string,
  data: { oldPassword: string; newPassword: string }
): Promise<{ success: boolean; message: string }> => {
  return request({
    url: `/users/${userId}/password`,
    method: "patch",
    data,
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
 * 获取用户列表（支持按角色筛选）
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
 * 创建用户
 */
export const createUser = (data: CreateUserDto): Promise<User> => {
  return request({
    url: "/users",
    method: "post",
    data,
  });
};

/**
 * 删除用户
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
 * 重置用户密码
 * @param userId 用户ID
 * @param newPassword 可选的新密码，不提供则随机生成
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
 * 批量导入用户
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
 * 批量删除用户
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

// 为了兼容可能使用user.service.ts的代码，提供默认导出
// 实际项目中应该统一使用命名导出
export default {
  login,
  register,
  getUserProfile,
  updateUserProfile,
  changePassword,
  getUsers,
  getUser,
  createUser,
  updateUser,
  deleteUser,
  resetPassword: resetUserPassword,
};
