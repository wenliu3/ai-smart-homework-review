import request from "@/utils/request";
import type { Role, UserMenu } from "@/types/role";

/**
 * 一次获取当前用户的所有资源（角色、权限和菜单）
 * @param userId 用户ID，传入'current'表示当前登录用户（普通用户仅可查询自己）
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
