import router, { resetRouter } from "./index";
import store from "@/store";
import type {
  RouteLocationNormalized,
  NavigationGuardNext,
  RouteRecordRaw,
} from "vue-router";
import NProgress from "nprogress";
import "nprogress/nprogress.css";
import type { UserMenu } from "@/types/role";
import AppLayout from "@/layouts/index.vue";

// NProgress配置 - 不显示加载圈
NProgress.configure({ showSpinner: false });

// 路由白名单 - 不需要登录即可访问的路由路径
const whiteList = ["/login", "/register", "/404", "/403"];

/**
 * 根据用户角色获取对应的Dashboard路径
 * @param roles 用户角色数组
 * @returns Dashboard路径
 */
// 根据用户角色获取对应的 dashboard 路径
function getRoleDashboardPath(roles: string[]): string {
  if (roles.includes("superadmin")) {
    return "/admin/dashboard";
  }
  if (roles.includes("teacher")) {
    return "/teacher/dashboard";
  }
  if (roles.includes("student")) {
    return "/student/dashboard";
  }
  // 默认跳转到404页面
  return "/404";
}

/**
 * 设置页面标题
 * @param to 目标路由
 */
function setDocumentTitle(to: RouteLocationNormalized): void {
  document.title = to.meta?.title
    ? `${to.meta.title} - AI智能作业批改系统`
    : "AI智能作业批改系统";
}

/**
 * 检查是否为白名单路由
 * @param path 路由路径
 * @param meta 路由元数据
 * @returns 是否为白名单路由
 */
function isWhiteListRoute(path: string, meta?: any): boolean {
  return whiteList.includes(path) || meta?.requiresAuth === false;
}

/**
 * 加载动态路由
 * @param to 目标路由
 * @param next 导航函数
 */
async function loadDynamicRoutes(
  to: RouteLocationNormalized,
  next: NavigationGuardNext
): Promise<void> {
  // 如果已经在加载路由，等待前一个加载完成

  try {
    // 重置路由，避免重复添加
    resetRouter();

    const token = store.getters["user/getToken"];
    // 如果token不存在，不再继续加载
    if (!token) {
      throw new Error("Token不存在，无法加载路由");
    }

    // 获取用户菜单和权限
    await store.dispatch("auth/initMenuRole");

    // 获取菜单数据
    const userMenus = store.getters["auth/userMenus"];

    if (!userMenus || userMenus.length === 0) {
      throw new Error("获取菜单数据失败");
    }

    // 从auth模块获取路由配置
    const routes = generateMenuRoutes(userMenus);

    if (!routes || routes.length === 0) {
      throw new Error("生成路由配置失败");
    }

    // 添加路由
    routes.forEach((route) => {
      router.addRoute(route);
    });

    // 添加404路由兜底
    router.addRoute({
      path: "/:pathMatch(.*)*",
      redirect: "/404",
      meta: { hidden: true },
    });

    // 重新导航到目标页面（替换浏览器历史记录）
    next({ ...to, replace: true });
  } catch (error) {
    console.error("生成动态路由失败:", error);
    // 出错时清除token
    localStorage.removeItem("token");
  } finally {
    NProgress.done();
  }
}

// 路由前置守卫
router.beforeEach(
  async (
    to: RouteLocationNormalized,
    from: RouteLocationNormalized,
    next: NavigationGuardNext
  ) => {
    // 开始进度条
    NProgress.start();
    // 设置页面标题
    setDocumentTitle(to);
    // 判断用户是否已登录
    const token = store.getters["user/getToken"];
    // 白名单路由直接放行
    if (isWhiteListRoute(to.path, to.meta)) {
      next();
      return;
    }

    // 如果token不存在，则重定向到登录页
    if (!token) {
      // 跳转登录页，保留重定向地址
      next(`/login?redirect=${encodeURIComponent(to.fullPath)}`);
      NProgress.done();
      return;
    }

    // 检查是否需要强制修改密码
    const mustChangePassword = store.getters["user/mustChangePassword"];

    // 如果需要强制修改密码且不是强制修改密码页面，则重定向
    if (
      mustChangePassword &&
      to.path !== "/force-change-password" &&
      !to.meta?.skipPasswordCheck
    ) {
      next(
        `/force-change-password?redirect=${encodeURIComponent(to.fullPath)}`
      );
      NProgress.done();
      return;
    }

    // 根据store中的菜单长度判断
    if (store.getters["auth/userMenus"].length === 0) {
      // 动态路由未生成，尝试加载
      try {
        await loadDynamicRoutes(to, next);
      } catch (error) {
        // 加载失败时直接跳转登录页
        next();
        NProgress.done();
      }
    } else {
      // 如果访问的是 /dashboard，根据角色重定向到对应的控制台
      if (to.path === "/dashboard") {
        const userRoles = store.getters["auth/userRoles"];

        if (userRoles && userRoles.length > 0) {
          const roleCodes = userRoles.map((role) => role.code || role);
          const dashboardPath = getRoleDashboardPath(roleCodes);

          next(dashboardPath);
          return;
        }
      }

      // 动态路由已生成，直接放行
      next();
    }
  }
);

// 预加载所有可能的组件模块
const componentModules = import.meta.glob("../views/**/*.vue");

/**
 * 动态加载组件
 * @param componentPath 组件路径
 */
function loadComponent(componentPath: string) {
  return async () => {
    // 处理组件路径，去掉开头的斜杠（如果有的话）
    let cleanComponentPath = componentPath.startsWith('/')
      ? componentPath.slice(1)
      : componentPath;

    // 种子数据中的路径可能已包含 "views/" 前缀，去掉避免双重拼接
    if (cleanComponentPath.startsWith('views/')) {
      cleanComponentPath = cleanComponentPath.slice(6);
    }

    try {
      // 构建完整的模块路径
      const modulePath = `../views/${cleanComponentPath}.vue`;

      // 检查模块是否存在
      if (componentModules[modulePath]) {
        const module = await componentModules[modulePath]();
        return module;
      } else {
        console.error(`组件不存在: ${componentPath} -> ${cleanComponentPath}`);

        // 如果组件不存在，尝试加载NotFound页面
        if (componentModules["../views/NotFound.vue"]) {
          const notFoundModule = await componentModules[
            "../views/NotFound.vue"
          ]();
          return notFoundModule;
        } else {
          // 如果连NotFound都不存在，返回一个简单的错误组件
          return {
            template: `
              <div style="text-align: center; padding: 50px; font-family: Arial, sans-serif;">
                <h3 style="color: #f56c6c;">页面未找到</h3>
                <p style="color: #909399;">组件路径: ${componentPath} -> ${cleanComponentPath}</p>
                <p style="color: #909399;">请检查路由配置或联系管理员</p>
                <el-button type="primary" @click="$router.push('/')">返回首页</el-button>
              </div>
            `,
          };
        }
      }
    } catch (error) {
      console.error(`组件加载失败: ${componentPath} -> ${cleanComponentPath}`, error);

      // 加载失败时的备用方案
      return {
        template: `
          <div style="text-align: center; padding: 50px; font-family: Arial, sans-serif;">
            <h3 style="color: #f56c6c;">组件加载失败</h3>
            <p style="color: #909399;">组件路径: ${componentPath} -> ${cleanComponentPath}</p>
            <p style="color: #909399;">错误信息: ${error.message}</p>
            <el-button type="primary" @click="$router.push('/')">返回首页</el-button>
            <el-button @click="location.reload()">刷新页面</el-button>
          </div>
        `,
      };
    }
  };
}

/**
 * 根据菜单数据生成路由配置
 * @param menus 菜单数据
 */
function generateMenuRoutes(menus) {
  // 检查菜单数据
  if (!menus || menus.length === 0) {
    console.warn("菜单数据为空，无法生成路由");
    return [];
  }

  /**
   * 递归将菜单转换为路由配置
   * @param menuItems 菜单项数组
   */
  function convertMenuToRoutes(menuItems) {
    const routes = [];
    // 递归收集所有菜单为扁平路由列表
    function flatten(items) {
      items.forEach((item) => {
        if (item.type === "button") return;
        if (item.component && item.type === "menu") {
          routes.push({
            path: item.path,
            name: item.code || item.name,
            component: loadComponent(item.component),
            meta: {
              title: item.meta?.title || item.name,
              icon: item.icon || '',
              requiresAuth: item.meta?.requireAuth !== false,
              keepAlive: item.meta?.keepAlive || false,
            },
          });
        }
        // 无组件但有子菜单：创建重定向
        if (!item.component && item.children && item.children.length > 0) {
          const firstWithComponent = item.children.find(c => c.component && c.type === "menu");
          if (firstWithComponent) {
            routes.push({
              path: item.path,
              name: item.code || item.name,
              redirect: firstWithComponent.path,
              meta: { title: item.meta?.title || item.name, icon: item.icon || '', hidden: true },
            });
          }
        }
        // 递归处理子菜单
        if (item.children && item.children.length > 0) {
          flatten(item.children);
        }
      });
    }
    flatten(menuItems);
    return routes;
  }

  // 生成路由配置
  const routes = convertMenuToRoutes(menus);

  const rootRoute = {
    path: "/",
    name: "Layout",
    component: AppLayout,
    children: routes,
    redirect: routes[0].path,
    meta: {
      title: "首页",
      icon: "HomeFilled",
    },
  };
  // 如果没有生成任何路由，返回空数组
  if (routes.length === 0) {
    console.warn("未生成任何路由");
    return [];
  }

  return [rootRoute];
}
// 路由后置守卫
router.afterEach(() => {
  // 结束进度条
  NProgress.done();
});
