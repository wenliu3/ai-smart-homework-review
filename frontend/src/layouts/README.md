# 布局系统说明

## 概述

本项目实现了基于用户角色的动态布局系统，提供两种不同的布局方式：

1. **AppLayout（侧边栏布局）** - 适用于管理员角色
2. **TopNavLayout（顶部菜单布局）** - 适用于其他角色

## 布局结构

```
src/layouts/
├── index.vue              # 布局入口文件，根据角色自动选择布局
├── AppLayout.vue          # 侧边栏布局（管理员专用）
├── TopNavLayout.vue       # 顶部菜单布局（其他角色）
├── components/
│   ├── AppHeader.vue      # 页面头部组件
│   ├── AppSidebar.vue     # 侧边栏组件
│   ├── AppTopNavbar.vue   # 顶部导航栏组件
│   ├── Breadcrumb.vue     # 面包屑导航组件
│   └── menu/
│       ├── SideMenuItem.vue   # 侧边栏菜单项组件
│       └── TopNavItem.vue     # 顶部菜单项组件
└── README.md              # 本说明文档
```

## 使用方式

### 1. 布局入口文件（index.vue）

布局入口文件会自动根据用户角色选择合适的布局：

```typescript
// 角色判断逻辑
if (
  userRole === "admin" ||
  userRole === "administrator" ||
  userRole === "super_admin"
) {
  return "AppLayout"; // 侧边栏布局
} else {
  return "TopNavLayout"; // 顶部菜单布局
}
```

### 2. 路由配置

在路由配置中使用布局入口文件：

```typescript
import LayoutIndex from '@/layouts/index.vue'

{
  path: '/',
  component: LayoutIndex, // 自动根据角色选择布局
  children: [
    // 子路由配置
  ]
}
```

### 3. 布局特性

#### AppLayout（侧边栏布局）

- 左侧可收缩的侧边栏菜单
- 顶部操作栏
- 响应式设计，移动端侧边栏可切换
- 适合管理员进行复杂的后台管理操作

#### TopNavLayout（顶部菜单布局）

- 顶部水平菜单导航
- 简洁的页面结构
- 更适合内容展示和简单操作
- 节省屏幕垂直空间

## 自定义配置

### 修改角色判断逻辑

如需调整角色与布局的对应关系，请修改 `src/layouts/index.vue` 中的 `currentLayout` 计算属性：

```typescript
const currentLayout = computed(() => {
  const userInfo = store.getters["user/getUserInfo"];
  const userRole = userInfo?.role;

  // 自定义角色判断逻辑
  if (yourCustomRoleCheck(userRole)) {
    return "AppLayout";
  } else {
    return "TopNavLayout";
  }
});
```

### 添加新的布局

1. 在 `src/layouts/` 目录下创建新的布局文件
2. 在 `src/layouts/index.vue` 中导入并注册组件
3. 修改角色判断逻辑以支持新布局

## 技术特性

- **Vue 3 Composition API** - 使用最新的 Vue 3 语法
- **TypeScript 支持** - 完整的类型定义
- **Element Plus** - 基于 Element Plus 组件库
- **Tailwind CSS** - 使用 Tailwind CSS 进行样式设计
- **响应式设计** - 支持移动端和桌面端
- **Vuex 状态管理** - 集成 Vuex 管理应用状态

## 注意事项

1. 确保 Vuex 中正确配置了用户角色信息
2. 菜单数据需要在 `store.getters['auth/leftMenus']` 中正确配置
3. 布局切换是基于用户角色的响应式变化，角色变更时会自动切换布局
