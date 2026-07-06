# Vuex 状态管理说明

## 重构思路

我们采用了精简的 Vuex 状态管理策略，遵循以下原则：

1. **只在 Vuex 中保存全局必要状态**：包括认证信息、用户权限、全局 UI 配置等
2. **组件内部状态使用 Vue 的响应式系统**：使用 ref, reactive 等 Composition API
3. **避免在 Vuex 中处理大量业务逻辑**：业务逻辑移至相关组件和服务层
4. **减少状态拆分**：相关状态聚合在一起，减少管理复杂度

## 模块职责划分

### 1. auth 模块 - 权限和路由管理

- **职责**：只负责权限控制、菜单和动态路由
- **包含数据**：
  - permissions - 用户权限列表
  - menus - 用户菜单结构
  - routes - 动态路由配置
- **不包含**：用户信息和认证

### 2. user 模块 - 用户和认证管理

- **职责**：管理用户认证、登录、注册和偏好设置
- **包含数据**：
  - userInfo - 用户完整信息（包含认证信息和个人资料）
  - preferences - 用户偏好设置
- **简化设计**：
  - 将所有用户相关信息整合到单一的 userInfo 对象中
  - token、userId 等认证信息作为 userInfo 的属性
  - 减少状态分散，更易维护

### 3. app 模块 - 全局 UI 状态

- **职责**：管理全局界面状态
- **包含数据**：
  - sidebar - 侧边栏状态
  - device - 设备类型（响应式设计）
- **不包含**：业务数据

## 模块协作流程

1. **登录流程**：

   - user 模块处理登录请求，在 userInfo 中保存 token 和用户基础信息
   - user 模块获取并更新 userInfo 的完整用户信息
   - user 模块通知 auth 模块初始化权限数据
   - auth 模块获取权限和菜单数据，生成动态路由

2. **权限控制**：

   - 路由导航守卫使用 auth 模块的 hasPermission 方法检查权限
   - 动态路由使用 auth 模块的 routes 数据

3. **用户信息展示与编辑**：

   - 使用 user 模块的 userInfo 数据展示个人信息
   - 用户修改个人信息时更新 userInfo 对象

4. **令牌刷新**：
   - user 模块负责检测和刷新令牌，更新 userInfo 中的 token 信息

## 页面与组件中的使用方法

### 在组件中使用 auth 模块：

```typescript
import { useStore } from "vuex";
import { computed } from "vue";

export default {
  setup() {
    const store = useStore();

    // 获取权限和菜单数据
    const permissions = computed(() => store.getters["auth/userPermissions"]);
    const menus = computed(() => store.getters["auth/userMenus"]);
    const routes = computed(() => store.getters["auth/dynamicRoutes"]);

    // 检查权限
    const hasPermission = (permission) =>
      store.getters["auth/hasPermission"](permission);

    return { permissions, menus, routes, hasPermission };
  },
};
```

### 在组件中使用 user 模块：

```typescript
import { useStore } from "vuex";
import { computed, reactive } from "vue";

export default {
  setup() {
    const store = useStore();

    // 登录表单数据
    const loginForm = reactive({
      username: "",
      password: "",
      rememberMe: false,
    });

    // 用户认证状态和信息
    const isAuthenticated = computed(
      () => store.getters["user/isAuthenticated"]
    );
    const userInfo = computed(() => store.getters["user/getUserInfo"]);
    const userRole = computed(() => store.getters["user/userRole"]);

    // 登录和登出方法
    const handleLogin = async () => {
      try {
        await store.dispatch("user/login", loginForm);
        // 登录成功后的处理
      } catch (error) {
        // 错误处理
      }
    };

    const handleLogout = () => {
      store.dispatch("user/logout");
    };

    return {
      loginForm,
      isAuthenticated,
      userInfo,
      userRole,
      handleLogin,
      handleLogout,
    };
  },
};
```

## 优化的关键点

1. **状态聚合**：

   - 将分散的状态（token, userId 等）聚合到 userInfo 对象中
   - 减少状态管理的复杂度，更易于理解和维护

2. **职责清晰**：

   - auth 模块专注于权限控制和路由管理
   - user 模块负责用户信息和认证
   - app 模块管理 UI 状态

3. **数据存储简化**：

   - localStorage 中只需要存储 userInfo、权限和偏好设置
   - 减少了多个存储项的同步复杂度

4. **API 调用封装**：
   - API 调用应在服务层（api 目录）中封装
   - Vuex actions 只负责调用服务并更新状态

## 模块结构

### 核心模块

1. **auth 模块**：

   - 用户权限管理
   - 菜单数据管理
   - 动态路由生成

2. **user 模块**：

   - 用户认证（token 管理）
   - 用户信息管理
   - 用户登录/注册
   - 用户首选项

3. **app 模块**：
   - 全局 UI 状态
   - 设备类型

### 移除的冗余模块

1. **role 模块**：角色管理功能移至相应的业务组件中
2. **menu 模块**：菜单管理功能移至相应的业务组件中

## 使用规范

1. **何时使用 Vuex**：

   - 多个不相关组件需要同一状态
   - 需要持久化的全局状态
   - 跨路由/视图的状态

2. **何时使用组件状态**：

   - 仅在单个组件中使用的状态
   - 父子组件间可通过 props/emit 传递的状态
   - 兄弟组件可通过共同父组件协调的状态

3. **API 调用封装**：
   - API 调用应在服务层（api 目录）中封装
   - Vuex actions 只负责调用服务并更新状态

## 与业务组件的集成

对于原本依赖 Vuex 管理的业务数据（如角色列表、菜单项等），应改为：

1. 在组件中直接调用 API 服务
2. 使用组件内部状态管理数据
3. 使用 provide/inject 在必要时共享非全局状态

示例：

```typescript
// 在组件中使用
import { ref, onMounted } from "vue";
import { getRoleList } from "@/api/role";

export default {
  setup() {
    const roles = ref([]);
    const loading = ref(false);

    const fetchRoles = async () => {
      loading.value = true;
      try {
        roles.value = await getRoleList();
      } catch (error) {
        console.error("获取角色列表失败", error);
      } finally {
        loading.value = false;
      }
    };

    onMounted(fetchRoles);

    return { roles, loading, fetchRoles };
  },
};
```
