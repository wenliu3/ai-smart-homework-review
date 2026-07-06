<template>
  <div
    ref="containerRef"
    :class="ADAPTIVE_TABLE_CLASSES.container"
    v-loading="loading"
    :element-loading-text="loadingText"
  >
    <!-- 搜索区域 -->
    <div :class="ADAPTIVE_TABLE_CLASSES.searchSection">
      <slot name="search" />
    </div>

    <!-- 表格区域 -->
    <div :class="ADAPTIVE_TABLE_CLASSES.tableSection">
      <slot name="table" :tableHeight="tableHeight" />
    </div>

    <!-- 分页区域 -->
    <div :class="ADAPTIVE_TABLE_CLASSES.paginationSection">
      <slot name="pagination" />
    </div>

    <!-- 其他组件区域 -->
    <slot name="extra" />
  </div>
</template>

<script setup lang="ts">
import {
  useAdaptiveTable,
  ADAPTIVE_TABLE_CLASSES,
} from "@/hooks/useAdaptiveTable";

interface Props {
  /** 是否显示加载状态 */
  loading?: boolean;
  /** 加载提示文本 */
  loadingText?: string;
}

const props = withDefaults(defineProps<Props>(), {
  loading: false,
  loadingText: "加载中...",
});

// 使用自适应表格 hook（简化版，主要用于提供 CSS 类名）
const { tableHeight, containerRef } = useAdaptiveTable();
</script>
