import { createStore } from "vuex";
import { auth } from "./modules/auth";
import appModule from "./modules/app";
import userModule from "./modules/user";
import dashboardModule from "./modules/dashboard";

// 定义根状态类型
export interface RootState {
  version: string;
}

// 创建Vuex实例 - 只注册必要的全局状态模块
const store = createStore({
  state: {
    version: "1.0.0",
  },
  modules: {
    auth, // 认证与权限状态
    app: appModule, // 应用UI状态
    user: userModule, // 用户基本信息
    dashboard: dashboardModule, // 看板数据状态
  },
});

// 导出store实例
export default store;
