<template>
  <div class="layout-container">
    <!-- 顶部导航栏区域 -->
    <el-header height="60px" class="layout-header">
      <div class="flex items-center justify-between w-full">
        <AppTopNavbar />
      </div>
    </el-header>

    <!-- 主要内容区域 - 精确计算高度 -->
    <div class="layout-main">
      <el-main class="content-main">
        <!-- 使用router-view作为内容区域 -->
        <router-view
          style="height: calc(100vh - 60px - 50px - 32px); overflow: auto"
        />
      </el-main>
    </div>

    <!-- Footer区域 - 固定高度 -->
    <el-footer height="50px" class="layout-footer">
      © {{ new Date().getFullYear() }} AI智能作业批改系统 - 版权所有
    </el-footer>
  </div>
</template>

<script lang="ts">
import { defineComponent, onMounted, onUnmounted } from "vue";
import AppTopNavbar from "./components/AppTopNavbar.vue";
import { useStore } from "vuex";

export default defineComponent({
  name: "TopNavLayout",
  components: {
    AppTopNavbar,
  },
  setup() {
    const store = useStore();

    // 窗口尺寸变化处理
    const handleResize = () => {
      const screenWidth = window.innerWidth;

      // 根据屏幕尺寸设置设备类型
      if (screenWidth < 768) {
        store.dispatch("app/setDevice", "mobile");
      } else if (screenWidth >= 768 && screenWidth < 992) {
        store.dispatch("app/setDevice", "tablet");
      } else {
        store.dispatch("app/setDevice", "desktop");
      }
    };

    // 组件挂载时设置初始状态和添加窗口尺寸监听
    onMounted(() => {
      handleResize();
      window.addEventListener("resize", handleResize);
    });

    // 组件卸载时移除监听器
    onUnmounted(() => {
      window.removeEventListener("resize", handleResize);
    });

    return {};
  },
});
</script>

<style scoped>
/* 布局容器 - 全屏高度 */
.layout-container {
  height: 100vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* 头部导航栏样式 */
.layout-header {
  height: 60px;
  background-color: white;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  z-index: 10;
  padding: 0 16px;
  display: flex;
  align-items: center;
  border-bottom: 1px solid #e5e7eb;
  flex-shrink: 0; /* 防止头部被压缩 */
}

/* 主内容区域 - 精确计算高度 */
.layout-main {
  height: calc(100vh - 60px - 50px); /* 总高度减去头部60px和底部50px */
  background-color: #f5f5f5;
  overflow: hidden;
  flex: 1;
}

/* 内容主体样式 */
.content-main {
  height: 100%;
  padding: 16px 24px;
  box-sizing: border-box;
  overflow-y: auto;
  overflow-x: hidden;
}

/* 底部样式 */
.layout-footer {
  height: 50px;
  background-color: white;
  color: #6b7280;
  text-align: center;
  display: flex;
  align-items: center;
  justify-content: center;
  border-top: 1px solid #e5e7eb;
  flex-shrink: 0; /* 防止底部被压缩 */
}

/* Element Plus 组件样式覆盖 */
:deep(.el-header) {
  padding: 0 16px;
  display: flex;
  align-items: center;
}

:deep(.el-main) {
  padding: 16px 24px;
  box-sizing: border-box;
}

:deep(.el-footer) {
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* 移动端样式调整 */
@media (max-width: 768px) {
  .layout-header {
    padding: 0 12px;
  }

  .content-main {
    padding: 12px 16px;
  }

  :deep(.el-header) {
    padding: 0 12px;
  }

  :deep(.el-main) {
    padding: 12px 16px;
  }
}

/* 平板样式调整 */
@media (min-width: 769px) and (max-width: 1024px) {
  .content-main {
    padding: 16px 20px;
  }

  :deep(.el-main) {
    padding: 16px 20px;
  }
}
</style>
