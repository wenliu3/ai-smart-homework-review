import { getUserResources } from "../../api/user-role";
import store from "../../store";

/**
 * Auth模块 - 负责菜单、路由和权限管理
 *
 * 主要功能:
 * 1. 存储用户的角色、权限和菜单信息
 * 2. 提供权限判断和菜单过滤功能
 */
export const auth = {
  namespaced: true,

  state: () => ({
    permissions: [],
    menus: [],
    roles: [],
  }),

  getters: {
    // 用户权限列表 - 存储的是code字段值，用于前端权限控制
    userPermissions: (state) => state.permissions,

    // 用户角色列表
    userRoles: (state) => state.roles,

    // 后端返回的完整菜单树
    userMenus: (state) => state.menus,

    // 左侧导航菜单 - 过滤掉type为button的菜单项
    leftMenus: (state) => {
      const filterMenus = (menus) => {
        return menus
          .filter((menu) => menu.type !== "button")
          .map((menu) => ({
            ...menu,
            children: menu.children ? filterMenus(menu.children) : [],
          }));
      };
      return filterMenus(state.menus);
    },
  },

  mutations: {
    // 设置权限列表 - 权限列表存储的是按钮类型菜单的code字段值
    SET_PERMISSIONS(state, permissions) {
      state.permissions = permissions;
      localStorage.setItem("permissions", JSON.stringify(permissions));
    },

    // 设置菜单树
    SET_MENUS(state, menus) {
      state.menus = menus;
      localStorage.setItem("menus", JSON.stringify(menus));
    },

    // 设置角色列表
    SET_ROLES(state, roles) {
      state.roles = roles;
      localStorage.setItem("roles", JSON.stringify(roles));
    },

    // 清除所有授权状态
    CLEAR_AUTH_STATE(state) {
      state.permissions = [];
      state.menus = [];
      state.roles = [];
      localStorage.removeItem("permissions");
      localStorage.removeItem("menus");
      localStorage.removeItem("roles");
      localStorage.removeItem("userInfo");
      localStorage.removeItem("token");
    },
  },

  actions: {
    /**
     * 初始化菜单和角色数据 - 应用启动时调用
     * 并行获取用户信息和用户所有授权资源
     */
    async initMenuRole({ commit, dispatch }) {
      try {
        // 并行获取用户信息和授权资源
        await Promise.all([
          store.dispatch("user/getUserInfo"),
          dispatch("fetchUserResources"),
        ]);

        return true;
      } catch (error) {
        console.error("初始化数据失败:", error);
        throw error;
      }
    },

    /**
     * 获取用户所有资源（角色、权限和菜单）
     */
    async fetchUserResources({ commit }) {
      try {
        const { roles, permissions, menus } = await getUserResources("current");
        commit("SET_ROLES", roles);
        commit("SET_PERMISSIONS", permissions);
        commit("SET_MENUS", menus);

        return { roles, permissions, menus };
      } catch (error) {
        console.error("获取用户资源失败:", error);
        throw error;
      }
    },

    /**
     * 清除权限数据
     * 用于登出或切换用户时清理状态
     */
    clearPermissions({ commit }) {
      console.log("clearPermissions");
      commit("CLEAR_AUTH_STATE");
    },
  },
};
