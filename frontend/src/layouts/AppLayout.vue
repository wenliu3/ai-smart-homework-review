<template>
  <div class="h-screen flex overflow-hidden relative">
    <!-- 左侧侧边栏区域 - 移动端时使用fixed定位覆盖 -->
    <!-- 设置下右侧边框颜色 -->
    <el-aside
      :width="sidebarWidth"
      v-if="!isMobile || sidebarOpened"
      :class="[
        'h-screen border-r border-gray-300 transition-all duration-300 ease-in-out overflow-y-auto',
        isMobile
          ? 'fixed bg-[#ffffff] left-0 top-0 bottom-0 z-30 '
          : 'relative',
      ]"
    >
      <AppSidebar />
      <!-- 移动端关闭按钮 -->
      <div
        v-if="isMobile"
        class="absolute top-4 right-4 cursor-pointer text-black p-2 rounded-full hover:bg-gray-700"
        @click="toggleSidebar"
      >
        <el-icon class="text-xl"><Close /></el-icon>
      </div>
    </el-aside>

    <!-- 移动端遮罩层 - 当侧边栏打开时显示 -->
    <div
      v-if="isMobile && sidebarOpened"
      class="fixed inset-0 bg-black bg-opacity-50 z-20"
      @click="toggleSidebar"
    ></div>

    <!-- 右侧内容区域 - 包含Header、Main和Footer -->
    <div class="flex-1 flex flex-col overflow-hidden">
      <!-- Header区域 -->
      <el-header
        height="60px"
        class="bg-white shadow z-10 px-4 flex items-center flex-shrink-0"
      >
        <div class="flex items-center justify-between w-full">
          <AppHeader />
        </div>
      </el-header>

      <!-- Main内容区域 - flex布局，仅 router-view 滚动，避免双重滚动条 -->
      <div
        class="bg-gray-100 p-4 md:p-4 flex-1 min-h-0 flex flex-col overflow-hidden"
      >
        <!-- 使用router-view作为内容区域 -->
        <router-view class="flex-1 min-h-0 overflow-auto" />
      </div>

      <!-- Footer区域 - 固定高度，不随内容伸缩 -->
      <el-footer
        height="50px"
        class="bg-white text-gray-600 text-center flex items-center justify-center border-t border-gray-200 flex-shrink-0"
      >
        © {{ new Date().getFullYear() }} AI智能作业批改系统 - 版权所有
      </el-footer>
    </div>

    <!-- AI教学助手悬浮组件 — 仅教师/管理员可见 -->
    <template v-if="showAssistant">
      <FloatingAssistantButton
        :visible="!panelVisible"
        @toggle="panelVisible = !panelVisible"
      />
      <AssistantPanel
        :visible="panelVisible"
        @close="panelVisible = false"
      />
    </template>
  </div>
</template>

<script lang="ts">
import {
  defineComponent,
  ref,
  computed,
  onMounted,
  onUnmounted,
  watch,
} from "vue";
import { Menu, Close } from "@element-plus/icons-vue";
// 导入组件
import AppSidebar from "./components/AppSidebar.vue";
import AppHeader from "./components/AppHeader.vue";
import FloatingAssistantButton from "@/components/FloatingAssistantButton.vue";
import AssistantPanel from "@/components/AssistantPanel.vue";
import { useStore } from "vuex";

export default defineComponent({
  name: "AppLayout",
  components: {
    AppSidebar,
    AppHeader,
    FloatingAssistantButton,
    AssistantPanel,
    Menu,
    Close,
  },
  setup() {
    const store = useStore();
    const screenWidth = ref(window.innerWidth);

    // 从Vuex获取侧边栏状态
    const sidebar = computed(() => store.getters["app/sidebar"]);
    const sidebarOpened = computed(() => store.getters["app/sidebarOpened"]);

    // 从Vuex获取设备类型
    const device = computed(() => store.getters["app/device"]);

    // 判断是否为移动设备
    const isMobile = computed(() => device.value === "mobile");

    // 侧边栏宽度 - 响应式计算
    const sidebarWidth = computed(() => {
      // 大屏幕根据收起状态设置宽度，小屏幕(移动设备)更宽以方便触摸
      if (!isMobile.value) {
        return sidebarOpened.value ? "200px" : "64px";
      } else {
        return "200px";
      }
    });

    // 切换侧边栏
    const toggleSidebar = () => {
      store.dispatch("app/toggleSidebar");
    };

    // AI教学助手面板
    const panelVisible = ref(false);

    // 仅教师/管理员显示助手
    const userInfo = computed(() => store.getters["user/getUserInfo"]);
    const showAssistant = computed(
      () => userInfo.value?.role === "teacher" || userInfo.value?.role === "superadmin"
    );

    // 窗口尺寸变化处理
    const handleResize = () => {
      screenWidth.value = window.innerWidth;

      // 根据屏幕尺寸设置设备类型
      if (screenWidth.value < 768) {
        store.dispatch("app/setDevice", "mobile");
        // 在移动设备上自动关闭侧边栏
        store.dispatch("app/closeSidebar", { withoutAnimation: true });
      } else if (screenWidth.value >= 768 && screenWidth.value < 992) {
        store.dispatch("app/setDevice", "tablet");
      } else {
        store.dispatch("app/setDevice", "desktop");
      }
    };

    // 组件挂载时设置侧边栏初始状态和添加窗口尺寸监听
    onMounted(() => {
      handleResize();
      window.addEventListener("resize", handleResize);
    });

    // 组件卸载时移除监听器
    onUnmounted(() => {
      window.removeEventListener("resize", handleResize);
    });

    return {
      sidebar,
      device,
      isMobile,
      sidebarWidth,
      toggleSidebar,
      sidebarOpened,
      panelVisible,
      showAssistant,
    };
  },
});
</script>

<style scoped>
/* 布局相关样式 */
:deep(.el-menu) {
  border-right: none !important;
}

:deep(.el-aside) {
  display: flex;
  flex-direction: column;
}

/* 确保滚动区域只在内容超出时显示滚动条 */
:deep(.el-main) {
  box-sizing: border-box;
  padding: 16px;
}

/* 移动端侧边栏样式 */
@media (max-width: 768px) {
  :deep(.el-aside) {
    width: 250px !important; /* 移动端下强制宽度 */
  }
}
</style>
