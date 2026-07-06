import { createRouter, createWebHistory } from "vue-router";
import type { RouteRecordRaw } from "vue-router";

// 布局组件 - 使用布局入口文件
import LayoutIndex from "@/layouts/index.vue";

// 静态路由 - 不需要权限控制的路由
export const constantRoutes: Array<RouteRecordRaw> = [
  {
    path: "/login",
    name: "Login",
    component: () => import("../views/Login.vue"),
    meta: { requiresAuth: false },
  },

  {
    path: "/force-change-password",
    name: "ForceChangePassword",
    component: () => import("../views/ForceChangePassword.vue"),
    meta: { requiresAuth: true, skipPasswordCheck: true },
  },
  {
    path: "/redirect",
    name: "Redirect",
    component: () => import("../views/Redirect.vue"),
    meta: { requiresAuth: false },
  },
  {
    path: "/404",
    name: "NotFound",
    component: () => import("../views/NotFound.vue"),
    meta: { requiresAuth: false },
  },

  // Dashboard路由 - 根据角色跳转到不同的控制台
  {
    path: "/admin",
    component: LayoutIndex,
    redirect: "/admin/dashboard",
    meta: { requiresAuth: true },
    children: [
      {
        path: "dashboard",
        name: "AdminDashboard",
        component: () => import("@/views/dashboard/AdminDashboard.vue"),
        meta: {
          title: "管理员控制台",
          icon: "Setting",
          requiresAuth: true,
          roles: ["superadmin"],
        },
      },
    ],
  },
  {
    path: "/teacher",
    component: LayoutIndex,
    redirect: "/teacher/dashboard",
    meta: { requiresAuth: true },
    children: [
      {
        path: "dashboard",
        name: "TeacherDashboard",
        component: () => import("@/views/dashboard/TeacherDashboard.vue"),
        meta: {
          title: "教师工作台",
          icon: "EditPen",
          requiresAuth: true,
          roles: ["teacher"],
        },
      },
    ],
  },
  {
    path: "/student",
    component: LayoutIndex,
    redirect: "/student/dashboard",
    meta: { requiresAuth: true },
    children: [
      {
        path: "dashboard",
        name: "StudentDashboard",
        component: () => import("@/views/dashboard/StudentDashboard.vue"),
        meta: {
          title: "学生学习台",
          icon: "Reading",
          requiresAuth: true,
          roles: ["student"],
        },
      },
    ],
  },
  // 系统管理子页面
  {
    path: "/system",
    component: LayoutIndex,
    redirect: "/system/users",
    meta: { requiresAuth: true },
    children: [
      { path: "users", name: "SystemUsers", component: () => import("@/views/system/users/index.vue"), meta: { title: "用户管理", requiresAuth: true } },
      { path: "roles", name: "SystemRoles", component: () => import("@/views/system/roles/index.vue"), meta: { title: "角色管理", requiresAuth: true } },
      { path: "menus", name: "SystemMenus", component: () => import("@/views/system/menus/index.vue"), meta: { title: "菜单管理", requiresAuth: true } },
      { path: "ai_model", name: "SystemAiModel", component: () => import("@/views/system/ai_model/index.vue"), meta: { title: "AI模型管理", requiresAuth: true } },
      { path: "classes", name: "SystemClasses", component: () => import("@/views/system/classes/index.vue"), meta: { title: "班级管理", requiresAuth: true } },
      { path: "logs", name: "SystemLogs", component: () => import("@/views/system/logs/index.vue"), meta: { title: "操作日志", requiresAuth: true } },
    ],
  },
  // 教师端子页面（套在 LayoutIndex 里，保持侧边栏顶栏）
  {
    path: "/teacher/classes",
    component: LayoutIndex,
    meta: { requiresAuth: true },
    children: [
      { path: "", name: "TeacherClasses", component: () => import("@/views/teacher/classes/index.vue"), meta: { title: "班级管理", requiresAuth: true } },
      { path: "detail", name: "TeacherClassesDetail", component: () => import("@/views/teacher/classes/detail/index.vue"), meta: { title: "班级详情", requiresAuth: true } },
    ],
  },
  {
    path: "/teacher/assignments",
    component: LayoutIndex,
    meta: { requiresAuth: true },
    children: [
      { path: "", name: "TeacherAssignments", component: () => import("@/views/teacher/assignments/index.vue"), meta: { title: "作业管理", requiresAuth: true } },
      { path: "detail", name: "TeacherAssignmentsDetail", component: () => import("@/views/teacher/assignments/detail/index.vue"), meta: { title: "作业详情", requiresAuth: true } },
    ],
  },
  {
    path: "/teacher/assignmentsEdit",
    component: LayoutIndex,
    meta: { requiresAuth: true },
    children: [
      { path: "", name: "TeacherAssignmentsEdit", component: () => import("@/views/teacher/assignments/assigmentsEidt/index.vue"), meta: { title: "创建作业", requiresAuth: true } },
    ],
  },
  {
    path: "/teacher/assignments/edit",
    component: LayoutIndex,
    meta: { requiresAuth: true },
    children: [
      { path: "", name: "TeacherAssignmentsEdit2", component: () => import("@/views/teacher/assignments/assigmentsEidt/index.vue"), meta: { title: "编辑作业", requiresAuth: true } },
    ],
  },
  {
    path: "/teacher/ai-rules",
    component: LayoutIndex,
    meta: { requiresAuth: true },
    children: [
      { path: "", name: "TeacherAiRules", component: () => import("@/views/teacher/ai-rules/index.vue"), meta: { title: "AI批改规则", requiresAuth: true } },
    ],
  },
  {
    path: "/teacher/correcting",
    component: LayoutIndex,
    meta: { requiresAuth: true },
    children: [
      { path: "", name: "TeacherCorrecting", component: () => import("@/views/teacher/correcting/index.vue"), meta: { title: "批改管理", requiresAuth: true } },
      { path: "grading", name: "TeacherGrading", component: () => import("@/views/teacher/correcting/grading.vue"), meta: { title: "批改详情", requiresAuth: true } },
    ],
  },
  {
    path: "/teacher/plagiarism",
    component: LayoutIndex,
    meta: { requiresAuth: true },
    children: [
      { path: "", name: "TeacherPlagiarism", component: () => import("@/views/teacher/plagiarism/index.vue"), meta: { title: "文档查重", requiresAuth: true } },
    ],
  },
  {
    path: "/teacher/submissions",
    component: LayoutIndex,
    meta: { requiresAuth: true },
    children: [
      { path: "detail", name: "TeacherSubmissionDetail", component: () => import("@/views/teacher/assignments/detail/index.vue"), meta: { title: "提交详情", requiresAuth: true } },
    ],
  },
  // 学生端子页面（套在 LayoutIndex 里，保持侧边栏顶栏）
  {
    path: "/student/classes",
    component: LayoutIndex,
    meta: { requiresAuth: true },
    children: [
      { path: "", name: "StudentClasses", component: () => import("@/views/student/classes/index.vue"), meta: { title: "我的班级", requiresAuth: true } },
    ],
  },
  {
    path: "/student/assignments",
    component: LayoutIndex,
    meta: { requiresAuth: true },
    children: [
      { path: "", name: "StudentAssignments", component: () => import("@/views/student/assignments/index.vue"), meta: { title: "我的作业", requiresAuth: true } },
      { path: ":id", name: "StudentAssignmentDetail", component: () => import("@/views/student/assignments/detail.vue"), meta: { title: "作业详情", requiresAuth: true } },
    ],
  },
  {
    path: "/student/submissions",
    component: LayoutIndex,
    meta: { requiresAuth: true },
    children: [
      { path: "", name: "StudentSubmission", component: () => import("@/views/student/submissions/index.vue"), meta: { title: "提交作业", requiresAuth: true } },
    ],
  },
  // 根路径重定向 - 登录后跳转到这里，由权限控制逻辑处理角色跳转
  {
    path: "/",
    redirect: "/dashboard",
  },
  {
    path: "/dashboard",
    name: "Dashboard",
    component: () => import("@/views/Redirect.vue"),
    meta: { requiresAuth: true },
  },
  {
    path: "/403",
    name: "Forbidden",
    component: () => import("../views/NotFound.vue"),
    meta: { requiresAuth: false },
  },
];

// 创建路由实例 - 包含静态路由
const router = createRouter({
  history: createWebHistory(),
  routes: constantRoutes,
});

// 重置路由方法
export function resetRouter() {
  // 移除所有动态路由（保留常量路由）
  router.getRoutes().forEach((route) => {
    if (
      route.name &&
      [
        "Login", "ForceChangePassword", "NotFound", "Redirect", "Dashboard",
        "AdminDashboard", "TeacherDashboard", "StudentDashboard",
        "SystemUsers", "SystemRoles", "SystemMenus", "SystemAiModel", "SystemClasses", "SystemLogs",
        "TeacherClasses", "TeacherClassesDetail", "TeacherAssignments", "TeacherAssignmentsEdit", "TeacherAssignmentsEdit2", "TeacherAssignmentsDetail", "TeacherAiRules", "TeacherCorrecting", "TeacherGrading", "TeacherSubmissionDetail", "TeacherPlagiarism",
        "StudentClasses", "StudentAssignments", "StudentAssignmentDetail", "StudentSubmission",
      ].indexOf(route.name.toString()) === -1
    ) {
      router.removeRoute(route.name);
    }
  });
}

export default router;
