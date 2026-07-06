import {
  getAdminOverview,
  getAiModelStats,
  getTeacherStats,
  getStudentStats,
} from "@/api/dashboard";
import type {
  AdminOverviewResponse,
  TeacherStatsResponse,
  StudentStatsResponse,
  AiModelStatsResponse,
} from "@/api/dashboard";

// Dashboard Vuex 模块
const dashboardModule = {
  namespaced: true,

  state: () => ({
    adminData: null as AdminOverviewResponse | null,
    teacherData: null as TeacherStatsResponse | null,
    studentData: null as StudentStatsResponse | null,
    aiModelData: null as AiModelStatsResponse | null,
    loading: {
      admin: false,
      teacher: false,
      student: false,
      aiModel: false,
    },
    lastUpdated: {
      admin: null,
      teacher: null,
      student: null,
      aiModel: null,
    },
    error: {
      admin: null,
      teacher: null,
      student: null,
      aiModel: null,
    },
  }),

  mutations: {
    // 管理员数据
    SET_ADMIN_DATA(state: any, data: AdminOverviewResponse) {
      state.adminData = data;
      state.lastUpdated.admin = new Date();
      state.error.admin = null;
    },

    SET_ADMIN_LOADING(state: any, loading: boolean) {
      state.loading.admin = loading;
    },

    SET_ADMIN_ERROR(state: any, error: string) {
      state.error.admin = error;
      state.loading.admin = false;
    },

    // 教师数据
    SET_TEACHER_DATA(state: any, data: TeacherStatsResponse) {
      state.teacherData = data;
      state.lastUpdated.teacher = new Date();
      state.error.teacher = null;
    },

    SET_TEACHER_LOADING(state: any, loading: boolean) {
      state.loading.teacher = loading;
    },

    SET_TEACHER_ERROR(state: any, error: string) {
      state.error.teacher = error;
      state.loading.teacher = false;
    },

    // 学生数据
    SET_STUDENT_DATA(state: any, data: StudentStatsResponse) {
      state.studentData = data;
      state.lastUpdated.student = new Date();
      state.error.student = null;
    },

    SET_STUDENT_LOADING(state: any, loading: boolean) {
      state.loading.student = loading;
    },

    SET_STUDENT_ERROR(state: any, error: string) {
      state.error.student = error;
      state.loading.student = false;
    },

    // AI模型数据
    SET_AI_MODEL_DATA(state: any, data: AiModelStatsResponse) {
      state.aiModelData = data;
      state.lastUpdated.aiModel = new Date();
      state.error.aiModel = null;
    },

    SET_AI_MODEL_LOADING(state: any, loading: boolean) {
      state.loading.aiModel = loading;
    },

    SET_AI_MODEL_ERROR(state: any, error: string) {
      state.error.aiModel = error;
      state.loading.aiModel = false;
    },

    // 清除数据
    CLEAR_DASHBOARD_DATA(state: any) {
      state.adminData = null;
      state.teacherData = null;
      state.studentData = null;
      state.aiModelData = null;
      state.lastUpdated = {
        admin: null,
        teacher: null,
        student: null,
        aiModel: null,
      };
      state.error = {
        admin: null,
        teacher: null,
        student: null,
        aiModel: null,
      };
    },
  },

  actions: {
    // 获取管理员看板数据
    async fetchAdminDashboard({ commit }, refresh = false) {
      commit("SET_ADMIN_LOADING", true);
      try {
        const data = await getAdminOverview(refresh);
        commit("SET_ADMIN_DATA", data);
      } catch (error: any) {
        const errorMessage =
          error.response?.data?.message ||
          error.message ||
          "获取管理员看板数据失败";
        commit("SET_ADMIN_ERROR", errorMessage);
        console.error("获取管理员看板数据失败:", error);
        throw error;
      } finally {
        commit("SET_ADMIN_LOADING", false);
      }
    },

    // 获取AI模型统计数据
    async fetchAiModelStats({ commit }, refresh = false) {
      commit("SET_AI_MODEL_LOADING", true);
      try {
        const data = await getAiModelStats(refresh);
        commit("SET_AI_MODEL_DATA", data);
      } catch (error: any) {
        const errorMessage =
          error.response?.data?.message ||
          error.message ||
          "获取AI模型统计失败";
        commit("SET_AI_MODEL_ERROR", errorMessage);
        console.error("获取AI模型统计失败:", error);
        throw error;
      } finally {
        commit("SET_AI_MODEL_LOADING", false);
      }
    },

    // 获取教师看板数据
    async fetchTeacherDashboard({ commit }, refresh = false) {
      commit("SET_TEACHER_LOADING", true);
      try {
        const data = await getTeacherStats(refresh);
        commit("SET_TEACHER_DATA", data);
      } catch (error: any) {
        const errorMessage =
          error.response?.data?.message ||
          error.message ||
          "获取教师看板数据失败";
        commit("SET_TEACHER_ERROR", errorMessage);
        console.error("获取教师看板数据失败:", error);
        throw error;
      } finally {
        commit("SET_TEACHER_LOADING", false);
      }
    },

    // 获取学生看板数据
    async fetchStudentDashboard({ commit }, refresh = false) {
      commit("SET_STUDENT_LOADING", true);
      try {
        const data = await getStudentStats(refresh);
        commit("SET_STUDENT_DATA", data);
      } catch (error: any) {
        const errorMessage =
          error.response?.data?.message ||
          error.message ||
          "获取学生看板数据失败";
        commit("SET_STUDENT_ERROR", errorMessage);
        console.error("获取学生看板数据失败:", error);
        throw error;
      } finally {
        commit("SET_STUDENT_LOADING", false);
      }
    },

    // 刷新所有数据
    async refreshAllData({ dispatch }, userRole: string) {
      const promises = [];

      if (userRole === "SUPER_ADMIN") {
        promises.push(dispatch("fetchAdminDashboard", true));
        promises.push(dispatch("fetchAiModelStats", true));
      } else if (userRole === "TEACHER") {
        promises.push(dispatch("fetchTeacherDashboard", true));
      } else if (userRole === "STUDENT") {
        promises.push(dispatch("fetchStudentDashboard", true));
      }

      await Promise.allSettled(promises);
    },

    // 清除数据
    clearDashboardData({ commit }) {
      commit("CLEAR_DASHBOARD_DATA");
    },
  },

  getters: {
    // 检查数据是否过期
    isDataStale:
      (state) => (type: "admin" | "teacher" | "student" | "aiModel") => {
        const lastUpdated = state.lastUpdated[type];
        if (!lastUpdated) return true;

        const staleThreshold = 5 * 60 * 1000; // 5分钟
        return Date.now() - lastUpdated.getTime() > staleThreshold;
      },

    // 获取加载状态
    isLoading:
      (state) => (type: "admin" | "teacher" | "student" | "aiModel") => {
        return state.loading[type];
      },

    // 获取错误状态
    getError:
      (state) => (type: "admin" | "teacher" | "student" | "aiModel") => {
        return state.error[type];
      },

    // 获取数据最后更新时间
    getLastUpdated:
      (state) => (type: "admin" | "teacher" | "student" | "aiModel") => {
        return state.lastUpdated[type];
      },

    // 管理员看板数据
    adminOverview: (state) => state.adminData,
    aiModelStats: (state) => state.aiModelData,

    // 教师看板数据
    teacherStats: (state) => state.teacherData,

    // 学生看板数据
    studentStats: (state) => state.studentData,

    // 检查是否有任何加载中的请求
    hasAnyLoading: (state) => {
      return Object.values(state.loading).some((loading) => loading);
    },

    // 检查是否有任何错误
    hasAnyError: (state) => {
      return Object.values(state.error).some((error) => error !== null);
    },
  },
};

export default dashboardModule;
