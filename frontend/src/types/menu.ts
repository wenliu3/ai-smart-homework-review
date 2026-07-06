/**
 * 菜单项类型
 */
export interface Menu {
  _id: string;
  name: string;
  code: string; // 权限编码，用于前端权限控制和后端鉴权
  path: string;
  component?: string;
  redirect?: string;
  type: "menu" | "button";
  parentId?: string | null;
  icon?: string;
  sort: number;
  hidden?: boolean;
  status: "active" | "inactive";
  meta?: {
    title?: string;
    icon?: string;
    keepAlive?: boolean;
    requireAuth?: boolean;
  };
  children?: Menu[];
  createdBy?:
    | string
    | {
        _id: string;
        username: string;
        name: string;
      };
  createdAt?: string;
  updatedAt?: string;
  isSystem?: boolean;
}

/**
 * 创建菜单DTO
 */
export interface CreateMenuDto {
  name: string;
  code: string; // 权限编码，用于前端权限控制和后端鉴权
  path: string;
  component?: string;
  redirect?: string;
  type: "menu" | "button";
  parentId?: string | null;
  icon?: string;
  sort: number;
  hidden?: boolean;
  status?: "active" | "inactive";
  meta?: {
    title?: string;
    keepAlive?: boolean;
    requireAuth?: boolean;
  };
}

/**
 * 更新菜单DTO
 */
export interface UpdateMenuDto {
  name?: string;
  path?: string;
  component?: string;
  redirect?: string;
  icon?: string;
  sort?: number;
  hidden?: boolean;
  status?: "active" | "inactive";
  parentId?: string | null;
  meta?: {
    title?: string;
    keepAlive?: boolean;
    requireAuth?: boolean;
  };
}
