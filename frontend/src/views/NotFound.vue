<template>
  <div class="not-found-container">
    <div class="not-found-content">
      <h1 class="error-code">404</h1>
      <h2 class="error-message">页面不存在</h2>
      <p class="error-description">抱歉，您访问的页面不存在或已被移除</p>
      <el-button type="primary" @click="goHome">返回首页</el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from "vue-router";

const router = useRouter();

const goHome = () => {
  router.push("/");
};
</script>

<style scoped>
.not-found-container {
  height: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
  background-color: #f5f7fa;
}

.not-found-content {
  text-align: center;
  padding: 2rem;
}

.error-code {
  font-size: 6rem;
  margin: 0;
  color: #409eff;
}

.error-message {
  font-size: 2rem;
  margin: 1rem 0;
  color: #606266;
}

.error-description {
  margin-bottom: 2rem;
  color: #909399;
}
</style>
