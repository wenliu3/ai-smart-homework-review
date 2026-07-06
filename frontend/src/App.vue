<template>
  <div class="h-screen w-full">
    <router-view />
  </div>
</template>

<script setup lang="ts">
// 应用根组件，无需额外逻辑
</script>

<style>
/* 引入  assets/main.css*/
@import "./assets/main.css";
/* 全局样式 */
@layer base {
  html,
  body {
    @apply m-0 p-0 h-full w-full font-sans text-gray-800;
  }
}

/* 自定义Tailwind优先级 */
.tw-override * {
  @apply font-sans;
}

/* Element Plus与Tailwind的兼容性调整 */
.el-button {
  @apply flex items-center justify-center;
}

/* 响应式容器调整 */
.container-fluid {
  @apply w-full px-4 md:px-6 lg:px-8;
}
</style>
