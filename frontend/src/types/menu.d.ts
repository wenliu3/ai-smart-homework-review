/**
 * 菜单项类型
 */
export interface Menu {
  _id: string;
  name: string;
  code?: string;
  path?: string;
  component?: string;
  redirect?: string;
  type: "menu" | "button";
  parentId?: string;
  icon?: string;
  sort: number;
  hidden: boolean;
  status: "active" | "inactive";
  meta?: {
    title: string;
    keepAlive?: boolean;
    requireAuth?: boolean;
    [key: string]: any;
  };
  children?: Menu[];
  createdAt?: string;
  updatedAt?: string;
  [key: string]: any;
}

/**
 * 创建菜单DTO
 */
export interface CreateMenuDto {
  name: string;
  code?: string;
  path?: string;
  component?: string;
  redirect?: string;
  type: "menu" | "button";
  parentId?: string;
  icon?: string;
  sort: number;
  hidden: boolean;
  status: "active" | "inactive";
  meta?: {
    title: string;
    keepAlive?: boolean;
    requireAuth?: boolean;
    [key: string]: any;
  };
  _id?: string; // 编辑时可能包含ID
}

/**
 * 更新菜单DTO
 */
export interface UpdateMenuDto {
  name?: string;
  code?: string;
  path?: string;
  component?: string;
  redirect?: string;
  type?: "menu" | "button";
  parentId?: string;
  icon?: string;
  sort?: number;
  hidden?: boolean;
  status?: "active" | "inactive";
  meta?: {
    title?: string;
    keepAlive?: boolean;
    requireAuth?: boolean;
    [key: string]: any;
  };
}
