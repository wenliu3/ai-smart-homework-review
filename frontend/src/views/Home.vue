<template>
  <div class="home-container">
    <el-row justify="center" align="middle">
      <el-col :span="16">
        <div class="welcome-section">
          <h1>AI智能作业批改系统</h1>

          <div class="action-buttons">
            <el-button type="primary" @click="$router.push('/login')"
              >登录</el-button
            >
            <el-button @click="handleEnterSystem">进入系统</el-button>
          </div>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from "vue-router";
import { useStore } from "vuex";

const router = useRouter();
const store = useStore();

// 处理进入系统按钮点击
const handleEnterSystem = () => {
  // 如果已登录，跳转到dashboard，否则跳转到登录页
  if (store.getters["auth/isAuthenticated"]) {
    router.push("/dashboard");
  } else {
    router.push("/login");
  }
};
</script>

<style scoped>
.home-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  background-color: #f5f7fa;
}

.welcome-section {
  text-align: center;
  padding: 2rem;
  background-color: white;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

h1 {
  font-size: 2.5rem;
  margin-bottom: 2rem;
  color: #409eff;
}

.action-buttons {
  margin-bottom: 1rem;
}

.action-buttons .el-button {
  margin: 0 0.5rem;
  padding: 12px 24px;
}
</style>
