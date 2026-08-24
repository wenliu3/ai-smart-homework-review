import request from "@/utils/request";
import type { Role } from "@/types/role";

/**
 * 获取角色列表（仅超级管理员）
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
 * 获取角色及其菜单（仅超级管理员）
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
 * 创建角色（仅超级管理员）
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
 * 更新角色（仅超级管理员）
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
 * 删除角色（仅超级管理员）
 * @param id 角色ID
 * @returns 操作结果
 */
export function deleteRole(id: string) {
  return request<{ success: boolean }>({
    url: `/permissions/roles/${id}`,
    method: "delete",
  });
}
