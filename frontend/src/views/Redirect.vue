<template>
  <div class="redirect-container">
    <div class="loading-wrapper">
      <el-icon class="is-loading"><Loading /></el-icon>
      <p>{{ redirectText }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { Loading } from "@element-plus/icons-vue";

const route = useRoute();
const router = useRouter();
const redirectText = ref("页面重定向中...");

/**
 * 处理重定向逻辑
 * 支持以下参数：
 * - path: 重定向的目标路径
 * - replace: 是否使用replace方式导航 (默认true)
 * - delay: 延迟时间(毫秒) (默认0)
 */
onMounted(() => {
  // 获取重定向参数
  const { params, query } = route;
  const path = (params.path as string) || "/";
  const replace = query.replace !== "false";
  // 使用ref创建可变的延迟时间
  const redirectDelay = ref(parseInt(query.delay as string) || 0);

  // 构建完整路径
  const redirectPath = path.startsWith("/") ? path : `/${path}`;

  // 添加查询参数（排除重定向相关参数）
  const { replace: _, delay: __, ...otherQuery } = query;

  // 如果配置了延迟，显示提示信息和倒计时
  if (redirectDelay.value > 0) {
    redirectText.value = `${redirectDelay.value / 1000}秒后跳转到新页面...`;

    // 显示倒计时
    const countDown = setInterval(() => {
      redirectDelay.value -= 1000;
      const remainingSeconds = Math.max(0, redirectDelay.value / 1000);
      redirectText.value = `${remainingSeconds}秒后跳转到新页面...`;

      if (redirectDelay.value <= 0) {
        clearInterval(countDown);
        performRedirect();
      }
    }, 1000);
  } else {
    // 立即重定向
    performRedirect();
  }

  // 执行重定向
  function performRedirect() {
    try {
      if (replace) {
        router.replace({ path: redirectPath, query: otherQuery });
      } else {
        router.push({ path: redirectPath, query: otherQuery });
      }
    } catch (error) {
      console.error("重定向失败:", error);
      redirectText.value = "重定向失败，请返回首页";
    }
  }
});
</script>

<style scoped>
.redirect-container {
  @apply flex items-center justify-center min-h-screen bg-gray-50;
}

.loading-wrapper {
  @apply flex flex-col items-center justify-center p-8 bg-white rounded-lg shadow-md;
}

.loading-wrapper .el-icon {
  @apply text-4xl text-primary mb-4;
}

.loading-wrapper p {
  @apply text-gray-600 text-lg;
}
</style>
