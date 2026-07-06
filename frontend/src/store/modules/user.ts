// user.ts - 用户相关状态管理
import {
  login,
  register,
  logout,
  refreshToken,
  getUserInfo,
} from "../../api/auth";
import router from "../../router";
import { ElMessage } from "element-plus";

/**
 * 用户模块 - 负责用户信息和认证管理
 *
 * 主要功能:
 * 1. 存储用户基础信息和认证状态
 * 2. 提供用户登录、注册、登出和令牌刷新功能
 * 3. 管理用户身份认证状态
 */

// 创建初始状态
const state = () => ({
  userInfo: JSON.parse(localStorage.getItem("userInfo") || "null"),
  refreshPromise: null, // 防止重复刷新的Promise缓存
});

// 定义getters
const getters = {
  getUserInfo: (state) => state.userInfo,
  getToken: (state) => state.userInfo?.token || localStorage.getItem("token"),
  getRefreshToken: (state) => state.userInfo?.refreshToken,
  isLoggedIn: (state) =>
    !!(state.userInfo?.token || localStorage.getItem("token")),
  mustChangePassword: (state) => state.userInfo?.mustChangePassword || false,
};

// 定义mutations
const mutations = {
  SET_USER_INFO(state, userInfo) {
    if (userInfo && state.userInfo) {
      // 如果已有用户信息则更新
      state.userInfo = { ...state.userInfo, ...userInfo };
    } else {
      // 否则直接设置
      state.userInfo = userInfo;
    }

    if (state.userInfo) {
      localStorage.setItem("userInfo", JSON.stringify(state.userInfo));
    } else {
      localStorage.removeItem("userInfo");
    }
  },

  SET_REFRESH_PROMISE(state, promise) {
    state.refreshPromise = promise;
  },
};

// 定义actions
const actions = {
  /**
   * 用户登录
   */
  async login({ commit }, { usernameOrEmailOrStudentId, password, rememberMe = false }) {
    try {
      const response = await login({ usernameOrEmailOrStudentId, password, rememberMe });

      // 保存token到localStorage
      localStorage.setItem("token", response.token);

      // 更新用户信息到Vuex
      commit("SET_USER_INFO", {
        token: response.token,
        refreshToken: response.refreshToken,
        tokenExpiresAt: Date.now() + response.expiresIn * 1000,
        mustChangePassword: response.mustChangePassword,
        isFirstLogin: response.isFirstLogin,
        ...(response.user && response.user),
      });

      return response;
    } catch (error) {
      // 错误处理交给调用方处理，这里只抛出
      throw error;
    }
  },

  /**
   * 获取用户详细信息
   */
  async getUserInfo({ commit, getters }) {
    const token = getters.getToken;
    if (!token) {
      return null;
    }

    try {
      const response = await getUserInfo();
      if (response?.user) {
        // 更新用户信息，保留token等认证信息
        commit("SET_USER_INFO", {
          ...getters.getUserInfo,
          ...response.user,
          token: getters.getToken,
        });

        return response.user;
      }

      return null;
    } catch (error) {
      throw error;
    }
  },

  /**
   * 用户注册
   */
  async register({ commit, dispatch }, registerData) {
    try {
      const response = await register(registerData);

      // 保存token
      localStorage.setItem("token", response.token);

      // 设置用户基本信息
      commit("SET_USER_INFO", {
        token: response.token,
        tokenExpiresAt: Date.now() + response.expiresIn * 1000,
      });

      // 获取用户信息和菜单
      await dispatch("getUserInfo");
      await dispatch("auth/initMenuRole", null, { root: true });

      router.push("/dashboard");

      return response;
    } catch (error) {
      throw error;
    }
  },

  /**
   * 刷新访问令牌
   */
  async refreshToken({ commit, state, getters }) {
    // 如果已经有刷新Promise在进行中，直接返回该Promise
    if (state.refreshPromise) {
      return state.refreshPromise;
    }

    const refreshTokenValue = getters.getRefreshToken;

    if (!refreshTokenValue) {
      console.warn('未找到刷新令牌，可能用户未勾选"记住我"或令牌已过期');
      // 清除用户信息并跳转到登录页
      commit("SET_USER_INFO", null);
      localStorage.removeItem("token");
      throw new Error("登录已过期，请重新登录");
    }

    // 创建刷新Promise
    const refreshPromise = (async () => {
      try {
        console.log(
          "开始刷新token，refreshToken:",
          refreshTokenValue.substring(0, 10) + "..."
        );
        const response = await refreshToken(refreshTokenValue);

        if (!response || !response.token) {
          throw new Error("刷新token失败：服务器返回无效响应");
        }

        // 更新用户信息
        const userInfo = {
          ...getters.getUserInfo,
          token: response.token,
          refreshToken: response.refreshToken || refreshTokenValue, // 使用新的refreshToken，如果没有则保持原有的
          tokenExpiresAt: Date.now() + response.expiresIn * 1000,
        };

        commit("SET_USER_INFO", userInfo);
        localStorage.setItem("token", response.token);

        console.log("token刷新成功");
        return response;
      } catch (error) {
        console.error("刷新token失败:", error);

        // 刷新失败时清除所有认证信息
        commit("SET_USER_INFO", null);
        localStorage.removeItem("token");

        // 重新抛出错误供上层处理
        throw error;
      } finally {
        // 清除刷新Promise缓存
        commit("SET_REFRESH_PROMISE", null);
      }
    })();

    // 保存刷新Promise
    commit("SET_REFRESH_PROMISE", refreshPromise);

    return refreshPromise;
  },

  /**
   * 用户登出
   */
  async logout({ commit, dispatch }) {
    try {
      await logout();
    } catch (error) {
      // 即使后端登出失败，前端也要清理本地状态
      console.warn("后端登出失败，但继续清理本地状态:", error);
    } finally {
      // 清除用户信息
      commit("SET_USER_INFO", null);
      localStorage.removeItem("token");

      // 清除权限信息
      await dispatch("auth/clearPermissions", null, { root: true });

      // 重定向到登录页
      router.push("/login");

      ElMessage.success("登出成功");
    }
  },
};

// 导出用户模块
export default {
  namespaced: true,
  state,
  getters,
  mutations,
  actions,
};
