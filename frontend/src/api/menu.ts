import request from "@/utils/request";
import type { Menu } from "@/types/menu";

/**
 * 获取菜单列表
 * @param params 查询参数
 * @returns 菜单列表
 */
export function getMenuList(params?: {
  tree?: string;
  name?: string;
  path?: string;
  status?: string;
  hidden?: string;
  type?: string;
}) {
  return request<Menu[]>({
    url: "/permissions/menus",
    method: "get",
    params,
  });
}

/**
 * 根据ID获取菜单详情
 * @param id 菜单ID
 * @returns 菜单详细信息
 */
export function getMenuById(id: string) {
  return request<Menu>({
    url: `/permissions/menus/${id}`,
    method: "get",
  });
}

/**
 * 创建菜单
 * @param data 菜单数据
 * @returns 创建的菜单信息
 */
export function createMenu(data: Partial<Menu>) {
  return request<Menu>({
    url: "/permissions/menus",
    method: "post",
    data,
  });
}

/**
 * 更新菜单
 * @param id 菜单ID
 * @param data 菜单数据
 * @returns 更新后的菜单信息
 */
export function updateMenu(id: string, data: Partial<Menu>) {
  return request<Menu>({
    url: `/permissions/menus/${id}`,
    method: "put",
    data,
  });
}

/**
 * 删除菜单
 * @param id 菜单ID
 * @returns 操作结果
 */
export function deleteMenu(id: string) {
  return request<{ success: boolean }>({
    url: `/permissions/menus/${id}`,
    method: "delete",
  });
}
