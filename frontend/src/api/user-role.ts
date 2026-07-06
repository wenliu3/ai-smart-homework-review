import request from "@/utils/request";
import type { Role, UserMenu } from "@/types/role";

/**
 * 获取用户的角色
 * @param userId 用户ID，传入'current'表示当前登录用户
 * @returns 角色列表
 */
export function getUserRoles(userId: string = "current") {
  return request<Role[]>({
    url: `/permissions/user-roles/users/${userId}/roles`,
    method: "get",
  });
}

/**
 * 获取角色列表
 */
export function getRoleList(params?: any) {
  return request<{
    roles: Role[];
    total: number;
  }>({
    url: "/permissions/roles",
    method: "get",
    params,
  });
}

/**
 * 获取用户的权限
 * @param userId 用户ID，传入'current'表示当前登录用户
 * @returns 权限编码列表
 */
export function getUserPermissions(userId: string = "current") {
  return request<string[]>({
    url: `/permissions/user-roles/users/${userId}/permissions`,
    method: "get",
  });
}

/**
 * 获取用户的菜单
 * @param userId 用户ID，传入'current'表示当前登录用户
 * @returns 菜单树结构
 */
export function getUserMenus(userId: string = "current") {
  return request<UserMenu[]>({
    url: `/permissions/user-roles/users/${userId}/menus`,
    method: "get",
  });
}

/**
 * 一次获取用户的所有资源（角色、权限和菜单）
 * @param userId 用户ID，传入'current'表示当前登录用户
 * @returns 包含roles、permissions和menus的对象
 */
export function getUserResources(userId: string = "current") {
  return request<{
    roles: Role[];
    permissions: string[];
    menus: UserMenu[];
  }>({
    url: `/permissions/user-roles/users/${userId}/resources`,
    method: "get",
  });
}

/**
 * 为用户分配角色
 * @param userId 用户ID
 * @param roleIds 角色ID数组
 * @returns 是否成功
 */
export function assignRolesToUser(userId: string, roleIds: string[]) {
  return request<boolean>({
    url: `/permissions/user-roles/users/${userId}/roles`,
    method: "put",
    data: { roleIds },
  });
}
