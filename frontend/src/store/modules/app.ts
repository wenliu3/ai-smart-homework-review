// app.ts - 应用级状态管理
import type { RootState } from "../index";

// 应用级状态接口
export interface AppState {
  sidebar: {
    opened: boolean;
    withoutAnimation: boolean;
  };
  device: "desktop" | "tablet" | "mobile";
  // 其他全局UI状态可以在这里添加
}

// app模块定义 - 只保留全局UI状态
const appModule = {
  namespaced: true,

  state: {
    sidebar: {
      opened: localStorage.getItem("sidebarStatus")
        ? !!+localStorage.getItem("sidebarStatus")!
        : true,
      withoutAnimation: false,
    },
    device: "desktop",
  },

  mutations: {
    // 切换侧边栏
    TOGGLE_SIDEBAR(state: AppState) {
      state.sidebar.opened = !state.sidebar.opened;
      state.sidebar.withoutAnimation = false;
      if (state.sidebar.opened) {
        localStorage.setItem("sidebarStatus", "1");
      } else {
        localStorage.setItem("sidebarStatus", "0");
      }
    },

    // 关闭侧边栏
    CLOSE_SIDEBAR(state: AppState, withoutAnimation: boolean) {
      localStorage.setItem("sidebarStatus", "0");
      state.sidebar.opened = false;
      state.sidebar.withoutAnimation = withoutAnimation;
    },

    // 设置设备类型
    SET_DEVICE(state: AppState, device: "desktop" | "tablet" | "mobile") {
      state.device = device;
    },
  },

  actions: {
    // 切换侧边栏
    toggleSidebar({ commit }: any) {
      commit("TOGGLE_SIDEBAR");
    },

    // 关闭侧边栏
    closeSidebar(
      { commit }: any,
      { withoutAnimation }: { withoutAnimation: boolean }
    ) {
      commit("CLOSE_SIDEBAR", withoutAnimation);
    },

    // 设置设备类型
    setDevice({ commit }: any, device: "desktop" | "tablet" | "mobile") {
      commit("SET_DEVICE", device);
    },
  },

  getters: {
    sidebar: (state: AppState) => state.sidebar,
    sidebarOpened: (state: AppState) => state.sidebar.opened,
    device: (state: AppState) => state.device,
    isMobile: (state: AppState) => state.device === "mobile",
  },
};

export default appModule;
