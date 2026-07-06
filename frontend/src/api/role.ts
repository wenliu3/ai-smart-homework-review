import request from "@/utils/request";
import type { Role } from "@/types/role";
import {
  getUserRoles,
  getUserMenus,
  getUserPermissions,
  getUserResources,
  assignRolesToUser,
} from "./user-role";

// 重新导出user-role.ts中已有的方法
export {
  getUserRoles,
  getUserMenus,
  getUserPermissions,
  getUserResources,
  assignRolesToUser,
};

/**
 * 获取角色列表
 * @param params 查询参数
 * @returns 角色列表和总数
 */
export function getRoleList(params?: {
  page?: number;
  limit?: number;
  search?: string;
  status?: string;
  isSystem?: boolean;
  sort?: string;
  order?: "asc" | "desc";
}) {
  return request<{
    items: Role[];
    total: number;
    page: number;
    limit: number;
  }>({
    url: "/permissions/roles",
    method: "get",
    params,
  });
}

/**
 * 根据ID获取角色详情
 * @param id 角色ID
 * @returns 角色详细信息
 */
export function getRoleById(id: string) {
  return request<Role>({
    url: `/permissions/roles/${id}`,
    method: "get",
  });
}

/**
 * 获取角色及其菜单
 * @param id 角色ID
 * @returns 角色及其菜单信息
 */
export function getRoleWithMenus(id: string) {
  return request<Role & { menus: any[] }>({
    url: `/permissions/roles/${id}/with-menus`,
    method: "get",
  });
}

/**
 * 创建角色
 * @param data 角色数据
 * @returns 创建的角色信息
 */
export interface CreateRoleDto {
  name: string;
  code: string;
  description: string;
  status?: "active" | "inactive";
  remark?: string;
  menuIds?: string[];
}

export function createRole(data: CreateRoleDto) {
  return request<Role>({
    url: "/permissions/roles",
    method: "post",
    data,
  });
}

/**
 * 更新角色
 * @param id 角色ID
 * @param data 角色数据
 * @returns 更新后的角色信息
 */
export interface UpdateRoleDto {
  name?: string;
  description?: string;
  status?: "active" | "inactive";
  remark?: string;
  menuIds?: string[];
}

export function updateRole(id: string, data: UpdateRoleDto) {
  return request<Role>({
    url: `/permissions/roles/${id}`,
    method: "put",
    data,
  });
}

/**
 * 删除角色
 * @param id 角色ID
 * @returns 操作结果
 */
export function deleteRole(id: string) {
  return request<{ success: boolean }>({
    url: `/permissions/roles/${id}`,
    method: "delete",
  });
}

/**
 * 为角色分配菜单和权限
 * @param id 角色ID
 * @param menuIds 菜单ID数组
 * @returns 更新后的角色信息
 */
export interface AssignMenusDto {
  menuIds: string[];
}

export function assignMenusToRole(id: string, menuIds: string[]) {
  return request<Role>({
    url: `/permissions/roles/${id}/menus`,
    method: "put",
    data: { menuIds },
  });
}

/**
 * 为用户分配角色
 * @deprecated 请使用 assignRolesToUser 代替
 * @param userId 用户ID
 * @param roleIds 角色ID数组
 * @returns 是否成功
 */
export interface AssignRolesDto {
  roleIds: string[];
}

export function assignUserRoles(userId: string, data: AssignRolesDto) {
  console.warn("assignUserRoles 已废弃，请使用 assignRolesToUser 代替");
  return assignRolesToUser(userId, data.roleIds);
}
