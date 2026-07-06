import { ref } from "vue";

// 自适应表格的CSS类名
export const ADAPTIVE_TABLE_CLASSES = {
  container: "adaptive-table-container",
  searchSection: "adaptive-table-search",
  tableSection: "adaptive-table-table",
  paginationSection: "adaptive-table-pagination",
};

/**
 * 简化的自适应表格组合式函数
 * 利用 CSS Flexbox 自动处理高度，无需 JavaScript 计算
 */
export function useAdaptiveTable() {
  const containerRef = ref<HTMLElement | null>(null);

  return {
    containerRef,
    // 保留这些属性以兼容现有代码
    tableHeight: ref(500), // 默认 500px 高度，避免塌缩
    calculateTableHeight: () => {}, // 空函数，保持接口兼容
    recalculate: () => {}, // 空函数，保持接口兼容
  };
}
