# 表格组件更新指南

## 概述

为了支持自适应表格容器，需要为所有表格组件添加 `maxHeight` 属性支持。

## 需要更新的组件

1. `MenuTable.vue` - 菜单表格组件
2. `RoleTable.vue` - 角色表格组件
3. `AiRuleTable.vue` - AI 规则表格组件
4. 其他表格组件

## 更新方式

### 1. 添加 maxHeight 属性到 el-table

```vue
<template>
  <el-table :data="tableData" :max-height="maxHeight" <!-- 其他属性 -->
    >
    <!-- 表格列定义 -->
  </el-table>
</template>
```

### 2. 在 props 中定义 maxHeight

```vue
<script setup lang="ts">
const props = defineProps({
  // 现有属性...
  maxHeight: {
    type: String,
    default: "600px",
  },
});
</script>
```

## 快速更新脚本

可以使用以下方式快速为表格组件添加 maxHeight 支持：

### UserTable.vue ✅ 已完成

- 已添加 maxHeight 属性
- 已在 el-table 中使用

### LogTable.vue ✅ 已完成

- 已添加 maxHeight 属性
- 已在 el-table 中使用

### MenuTable.vue 🔄 需要手动更新

1. 在 el-table 中添加 `:max-height="maxHeight"`
2. 在 props 中添加 maxHeight 定义

### RoleTable.vue 🔄 需要手动更新

1. 在 el-table 中添加 `:max-height="maxHeight"`
2. 在 props 中添加 maxHeight 定义

### AiRuleTable.vue 🔄 需要手动更新

1. 在 el-table 中添加 `:max-height="maxHeight"`
2. 在 props 中添加 maxHeight 定义

## 验证方式

更新完成后，可以通过以下方式验证：

1. 打开对应的管理页面
2. 缩放浏览器窗口
3. 确认搜索条件始终可见
4. 确认分页组件始终可见
5. 确认只有表格内容区域滚动

## 注意事项

1. 对于树形表格（如菜单管理），确保展开/折叠功能正常
2. 对于有固定列的表格，确保固定列滚动正常
3. 移动端适配要保持良好体验
