<template>
  <div class="flex flex-col h-full">
    <!-- Logo容器 -->
    <div class="logo-container">
      <div v-if="!isCollapse" class="logo-full">
        <img
          src="@/assets/image/mini_logo.jpeg"
          alt="AI智能作业批改系统"
          class="logo-image"
        />
        <span class="logo-text">AI智能作业批改系统</span>
      </div>
      <div v-else class="logo-collapsed">
        <img
          src="@/assets/image/mini_logo.jpeg"
          alt="AI智能作业批改系统"
          class="logo-image-small"
        />
      </div>
    </div>

    <el-scrollbar class="flex-1">
      <el-menu
        :default-active="activeMenu"
        :collapse="isCollapse"
        active-text-color="#409EFF"
        :router="false"
        unique-opened
        class="border-r-0"
      >
        <!-- 使用递归组件渲染菜单 -->
        <side-menu-item
          v-for="menu in leftMenus"
          :key="menu._id"
          :menu="menu"
          @menu-click="handleMenuClick"
        />
      </el-menu>
    </el-scrollbar>
  </div>
</template>

<script lang="ts">
import { ref, computed, onMounted, defineComponent } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useStore } from "vuex";
import SideMenuItem from "./menu/SideMenuItem.vue";

export default defineComponent({
  name: "AppSidebar",
  components: {
    SideMenuItem,
  },
  setup() {
    const route = useRoute();
    const router = useRouter();
    const store = useStore();

    // 计算当前激活菜单
    const activeMenu = computed(() => {
      const { meta, path } = route;
      if (meta.activeMenu) {
        return meta.activeMenu;
      }
      return path;
    });

    // 侧边栏收起状态
    const isCollapse = computed(() => {
      return !store.getters["app/sidebarOpened"];
    });

    // 从Vuex获取用户菜单数据
    const leftMenus = computed(() => {
      return store.getters["auth/leftMenus"] || [];
    });

    // 处理菜单点击事件
    const handleMenuClick = (path) => {
      console.log("菜单点击:", path);

      // 移动端关闭侧边栏
      if (store.getters["app/isMobile"]) {
        store.dispatch("app/closeSidebar", { withoutAnimation: false });
      }

      // 空路径不处理
      if (!path) return;

      // 确保路径格式正确
      const normalizedPath = path.startsWith("/") ? path : `/${path}`;

      // 导航到对应路由
      router.push(normalizedPath);
    };

    // 组件加载时获取菜单数据
    onMounted(async () => {});

    return {
      activeMenu,
      isCollapse,
      leftMenus,
      handleMenuClick,
    };
  },
});
</script>

<style scoped>
.sidebar {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.logo-container {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 8px 16px;
  border-bottom: 1px solid #e5e7eb;
  background: #fafafa;
  overflow: hidden;
  transition: all 0.3s;
}

.logo-full {
  display: flex;
  align-items: center;
  gap: 12px;
  transition: all 0.3s;
}

.logo-collapsed {
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.3s;
}

.logo-image {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  object-fit: cover;
  flex-shrink: 0;
  transition: all 0.3s;
}

.logo-image-small {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  object-fit: cover;
  transition: all 0.3s;
}

.logo-text {
  font-size: 16px;
  font-weight: 600;
  color: #1f2937;
  margin: 0;
  white-space: nowrap;
  transition: all 0.3s;
}

.el-menu-vertical {
  border-right: none;
}
</style>
