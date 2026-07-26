import type { BaseEntity } from "./common";

/**
 * 定义用户菜单类型，用于从后端返回的菜单数据
 */
export interface UserMenu {
  _id: string;
  name: string;
  code?: string;
  path: string;
  component?: string;
  redirect?: string;
  type: "menu" | "button";
  parentId?: string | null;
  icon?: string;
  permission?: string | null;
  sort?: number;
  hidden?: boolean;
  status?: "active" | "inactive";
  meta?: {
    title?: string;
    keepAlive?: boolean;
    requireAuth?: boolean;
    activeMenu?: string;
    hidden?: boolean;
    icon?: string;
    [key: string]: any;
  };
  children?: UserMenu[];
}

/**
 * 角色数据模型
 */
export interface Role extends BaseEntity {
  /**
   * 角色名称
   */
  name: string;

  /**
   * 角色编码
   */
  code: string;

  /**
   * 角色描述
   */
  description: string;

  /**
   * 菜单ID数组
   */
  menuIds: string[];

  /**
   * 权限标识数组
   */
  permissions: string[];

  /**
   * 是否为系统内置角色
   */
  isSystem: boolean;

  /**
   * 状态：active-正常，inactive-禁用
   */
  status: "active" | "inactive";

  /**
   * 备注
   */
  remark?: string;

  /**
   * 创建人ID
   */
  createdBy?: string;

  /**
   * 创建时间
   */
  createdAt?: string;

  /**
   * 更新时间
   */
  updatedAt?: string;
}

/**
 * 角色选项定义
 */
export interface RoleOption {
  _id: string;
  name: string;
  code: string;
  description?: string;
}

/**
 * 角色查询参数
 */
export interface RoleQueryParams {
  /**
   * 页码
   */
  page?: number;

  /**
   * 每页数量
   */
  limit?: number;

  /**
   * 关键词搜索
   */
  search?: string;

  /**
   * 角色状态
   */
  status?: string;

  /**
   * 是否系统角色
   */
  isSystem?: boolean;

  /**
   * 排序字段
   */
  sort?: string;

  /**
   * 排序方向
   */
  order?: "asc" | "desc";
}

/**
 * 创建角色参数
 */
export interface CreateRoleParams {
  /**
   * 角色名称
   */
  name: string;

  /**
   * 角色编码
   */
  code: string;

  /**
   * 角色描述
   */
  description: string;

  /**
   * 角色状态
   */
  status?: "active" | "inactive";

  /**
   * 备注
   */
  remark?: string;

  /**
   * 初始菜单ID列表
   */
  menuIds?: string[];
}

/**
 * 更新角色参数
 */
export interface UpdateRoleParams {
  /**
   * 角色名称
   */
  name?: string;

  /**
   * 角色描述
   */
  description?: string;

  /**
   * 角色状态
   */
  status?: "active" | "inactive";

  /**
   * 备注
   */
  remark?: string;
}

/**
 * 分配菜单参数
 */
export interface AssignMenusParams {
  /**
   * 菜单ID数组
   */
  menuIds: string[];
}

/**
 * 分配角色参数
 */
export interface AssignRolesParams {
  /**
   * 角色ID数组
   */
  roleIds: string[];
}
