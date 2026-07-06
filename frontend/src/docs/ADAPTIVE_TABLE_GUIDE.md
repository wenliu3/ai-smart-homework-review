# 自适应表格组件使用指南

## 概述

自适应表格组件 `AdaptiveTableContainer` 是一个专门为解决表格页面布局问题而设计的公共组件。它确保：

1. **搜索条件始终可见** - 搜索表单固定在页面顶部
2. **分页组件始终可见** - 分页控件固定在页面底部
3. **表格自适应高度** - 表格内容区域自动计算高度并启用滚动
4. **响应式布局** - 适配不同屏幕尺寸和设备类型

## 核心特性

### 1. 自动高度计算

- 根据视窗高度、搜索区域高度、分页区域高度自动计算表格最佳高度
- 支持窗口大小变化时重新计算
- 防抖优化，避免频繁计算

### 2. 固定布局

- 搜索表单固定在顶部，不随表格滚动而隐藏
- 分页组件固定在底部，用户无需滚动即可看到
- 只有表格内容区域支持滚动

### 3. 响应式设计

- 支持移动端、平板端、桌面端不同布局
- 自动适配不同屏幕尺寸
- 优化的触摸交互体验

## 使用方法

### 1. 基本用法

```vue
<template>
  <adaptive-table-container
    :loading="loading"
    loading-text="加载中..."
    :recalculate-trigger="recalculateTrigger"
    ref="adaptiveTableRef"
  >
    <!-- 搜索区域 -->
    <template #search>
      <el-form :inline="true" :model="searchForm">
        <!-- 搜索表单内容 -->
      </el-form>
    </template>

    <!-- 表格区域 -->
    <template #table="{ tableHeight }">
      <your-table-component :data="tableData" :max-height="tableHeight" />
    </template>

    <!-- 分页区域 -->
    <template #pagination>
      <el-pagination
        :current-page="pagination.page"
        :page-size="pagination.limit"
        :total="pagination.total"
        @size-change="handleSizeChange"
        @current-change="handleCurrentChange"
      />
    </template>

    <!-- 其他组件（对话框、表单等） -->
    <template #extra>
      <your-dialog-component />
    </template>
  </adaptive-table-container>
</template>

<script setup lang="ts">
import { ref } from "vue";
import AdaptiveTableContainer from "@/components/AdaptiveTableContainer.vue";

// 数据状态
const loading = ref(false);
const tableData = ref([]);
const searchForm = ref({});
const pagination = ref({ page: 1, limit: 10, total: 0 });

// 触发重新计算的计数器
const recalculateTrigger = ref(0);

// 组件引用
const adaptiveTableRef = ref(null);

// 数据加载完成后触发重新计算
const loadData = async () => {
  loading.value = true;
  try {
    // 加载数据逻辑
    // ...

    // 触发表格高度重新计算
    recalculateTrigger.value++;
  } finally {
    loading.value = false;
  }
};
</script>
```

### 2. 表格组件适配

你的表格组件需要支持 `maxHeight` 属性：

```vue
<!-- YourTableComponent.vue -->
<template>
  <el-table :data="data" :max-height="maxHeight" stripe border>
    <!-- 表格列定义 -->
  </el-table>
</template>

<script setup lang="ts">
defineProps({
  data: {
    type: Array,
    required: true,
  },
  maxHeight: {
    type: String,
    default: "600px",
  },
});
</script>
```

## 组件 API

### Props

| 属性名               | 类型               | 默认值        | 说明                               |
| -------------------- | ------------------ | ------------- | ---------------------------------- |
| `loading`            | `boolean`          | `false`       | 是否显示加载状态                   |
| `loadingText`        | `string`           | `'加载中...'` | 加载提示文本                       |
| `bottomOffset`       | `number`           | `20`          | 额外的底部偏移量(px)               |
| `debug`              | `boolean`          | `false`       | 是否启用调试模式                   |
| `recalculateTrigger` | `number \| string` | `0`           | 重新计算触发器，变化时重新计算高度 |

### Slots

| 插槽名       | 说明                 | 作用域插槽参数            |
| ------------ | -------------------- | ------------------------- |
| `search`     | 搜索区域内容         | -                         |
| `header`     | 卡片头部内容         | -                         |
| `table`      | 表格区域内容         | `{ tableHeight: string }` |
| `pagination` | 分页区域内容         | -                         |
| `extra`      | 其他内容（对话框等） | -                         |

### 暴露的方法

| 方法名          | 说明                     |
| --------------- | ------------------------ |
| `recalculate()` | 手动触发重新计算表格高度 |

### 事件

无特定事件，依赖子组件事件。

## 最佳实践

### 1. 数据变化时重新计算

```typescript
// 方式一：使用 recalculateTrigger
const recalculateTrigger = ref(0);

const loadData = async () => {
  // 加载数据...
  recalculateTrigger.value++; // 触发重新计算
};

// 方式二：直接调用方法
const adaptiveTableRef = ref(null);

const loadData = async () => {
  // 加载数据...
  await nextTick();
  adaptiveTableRef.value?.recalculate();
};
```

### 2. 搜索表单布局

```vue
<template #search>
  <el-form
    :inline="true"
    :model="searchForm"
    class="flex flex-wrap items-center"
  >
    <el-form-item label="关键词">
      <el-input v-model="searchForm.keyword" style="width: 200px;" />
    </el-form-item>
    <el-form-item class="mb-0 flex-shrink-0">
      <el-button type="primary" @click="handleSearch">搜索</el-button>
      <el-button @click="resetSearch">重置</el-button>
    </el-form-item>
  </el-form>
</template>
```

### 3. 响应式分页

```vue
<template #pagination>
  <el-pagination
    :current-page="pagination.page"
    :page-size="pagination.limit"
    :page-sizes="[10, 20, 50, 100]"
    :background="true"
    layout="total, sizes, prev, pager, next, jumper"
    :total="pagination.total"
    @size-change="handleSizeChange"
    @current-change="handleCurrentChange"
  />
</template>
```

## 样式定制

### 1. CSS 变量

组件使用 Element Plus 的设计令牌，可以通过 CSS 变量进行定制：

```css
:root {
  --el-table-border-color: #ebeef5;
  --el-table-row-hover-bg-color: #f5f7fa;
  /* 更多变量... */
}
```

### 2. 自定义样式类

可以使用提供的工具类进行样式定制：

```css
/* 表格工具类 */
.table-full-height {
  height: 100% !important;
}
.table-scroll-y {
  overflow-y: auto !important;
}
.table-scroll-x {
  overflow-x: auto !important;
}
.table-no-scroll {
  overflow: hidden !important;
}

/* 操作按钮组 */
.table-actions {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
  align-items: center;
  justify-content: center;
}
```

## 迁移指南

### 从传统布局迁移

**迁移前：**

```vue
<template>
  <div>
    <!-- 搜索表单 -->
    <el-form>...</el-form>

    <!-- 表格卡片 -->
    <el-card v-loading="loading">
      <el-table :data="data" />
      <div class="pagination">
        <el-pagination />
      </div>
    </el-card>
  </div>
</template>
```

**迁移后：**

```vue
<template>
  <adaptive-table-container :loading="loading">
    <template #search>
      <el-form>...</el-form>
    </template>

    <template #table="{ tableHeight }">
      <el-table :data="data" :max-height="tableHeight" />
    </template>

    <template #pagination>
      <el-pagination />
    </template>
  </adaptive-table-container>
</template>
```

### 需要修改的地方

1. **表格组件**：添加 `maxHeight` 属性支持
2. **数据加载**：在数据变化后触发重新计算
3. **样式调整**：移除自定义的高度和滚动样式
4. **布局结构**：使用插槽重新组织内容

## 常见问题

### Q: 表格高度计算不准确怎么办？

A: 可以尝试以下方法：

1. 检查是否在数据加载完成后触发了重新计算
2. 调整 `bottomOffset` 参数
3. 启用 `debug` 模式查看计算过程
4. 手动调用 `recalculate()` 方法

### Q: 移动端显示效果不佳？

A: 组件已经内置了移动端适配，包括：

- 响应式分页布局
- 触摸友好的滚动
- 自适应的最小高度
- 优化的间距设置

### Q: 如何在表格数据变化时自动调整高度？

A: 有两种方式：

1. 使用 `recalculateTrigger` 属性（推荐）
2. 直接调用组件的 `recalculate()` 方法

### Q: 可以不显示某个区域吗？

A: 可以的，所有插槽都是可选的：

- 不提供 `search` 插槽 = 无搜索区域
- 不提供 `pagination` 插槽 = 无分页区域
- 不提供 `header` 插槽 = 无卡片头部

## 实际应用示例

项目中已经应用的页面：

1. **用户管理页面** - `/src/views/system/users/index.vue`
2. **日志管理页面** - `/src/views/system/logs/index.vue`

可以参考这些页面的实现方式来了解具体用法。
