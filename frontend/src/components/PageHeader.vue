<template>
  <div class="page-header">
    <div class="header-left">
      <h2 class="page-title">{{ title }}</h2>
      <p v-if="description" class="page-desc">{{ description }}</p>
    </div>
    <div class="header-right">
      <slot name="actions" />
    </div>
  </div>
</template>

<script setup lang="ts">
interface Props {
  /** 页面标题 */
  title: string;
  /** 页面描述 */
  description?: string;
}

defineProps<Props>();

// 组件名称
defineOptions({
  name: "PageHeader",
});
</script>

<script lang="ts">
// 添加默认导出以支持常规导入
import { defineComponent } from "vue";

export default defineComponent({
  name: "PageHeader",
});
</script>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
  padding: 20px 24px;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.header-left {
  flex: 1;
}

.page-title {
  margin: 0 0 4px 0;
  font-size: 20px;
  font-weight: 600;
  color: #303133;
}

.page-desc {
  margin: 0;
  color: #909399;
  font-size: 13px;
}

.header-right {
  flex-shrink: 0;
}

/* 响应式适配 */
@media (max-width: 768px) {
  .page-header {
    flex-direction: column;
    gap: 16px;
    padding: 16px 20px;
  }

  .header-left {
    flex: none;
  }

  .header-right {
    flex: none;
    align-self: stretch;
  }

  .page-title {
    font-size: 18px;
  }
}
</style>
