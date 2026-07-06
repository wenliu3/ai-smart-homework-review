<template>
  <div class="flex justify-between items-center h-full w-full">
    <!-- 左侧Logo和导航菜单 -->
    <div class="flex items-center">
      <!-- Logo -->
      <div class="logo-container mr-8">
        <img
          src="@/assets/image/mini_logo.jpeg"
          alt="AI智能作业批改系统"
          class="logo-image"
        />
        <span class="logo-text">AI智能作业批改系统</span>
      </div>

      <!-- 顶部导航菜单 -->
      <el-menu
        :default-active="activeMenu"
        mode="horizontal"
        :router="false"
        class="border-b-0 flex-1"
        background-color="transparent"
        text-color="#606266"
        active-text-color="#409EFF"
      >
        <top-nav-item
          v-for="menu in topMenus"
          :key="menu._id"
          :menu="menu"
          @menu-click="handleMenuClick"
        />
      </el-menu>
    </div>

    <!-- 右侧用户区域 -->
    <div class="flex items-center">
      <!-- 面包屑导航 -->
      <Breadcrumb class="mr-4" />

      <el-divider direction="vertical" class="hidden sm:block" />

      <!-- 用户下拉菜单 -->
      <el-dropdown trigger="click" @command="handleCommand">
        <div
          class="flex items-center cursor-pointer px-3 py-1 rounded transition-colors hover:bg-gray-100"
        >
          <el-avatar :size="32" :src="userAvatar">{{ userInitials }}</el-avatar>
          <span class="mx-2 text-sm text-gray-800 hidden sm:block">{{
            username
          }}</span>
          <el-icon class="hidden sm:block"><ArrowDown /></el-icon>
        </div>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="change-password">
              <div class="flex items-center">
                <el-icon class="mr-2"><Lock /></el-icon>修改密码
              </div>
            </el-dropdown-item>
            <el-dropdown-item divided command="logout">
              <div class="flex items-center">
                <el-icon class="mr-2"><SwitchButton /></el-icon>退出登录
              </div>
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>

    <!-- 修改密码弹窗 -->
    <ChangePasswordDialog
      v-model="showChangePasswordDialog"
      @success="handlePasswordChangeSuccess"
    />
  </div>
</template>

<script lang="ts">
import { computed, defineComponent, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useStore } from "vuex";
import { ArrowDown, SwitchButton, Lock } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";
import Breadcrumb from "./Breadcrumb.vue";
import TopNavItem from "./menu/TopNavItem.vue";
import ChangePasswordDialog from "./ChangePasswordDialog.vue";

export default defineComponent({
  name: "AppTopNavbar",
  components: {
    Breadcrumb,
    TopNavItem,
    ChangePasswordDialog,
  },
  setup() {
    const route = useRoute();
    const router = useRouter();
    const store = useStore();

    // 修改密码弹窗控制
    const showChangePasswordDialog = ref(false);

    // 计算当前激活菜单
    const activeMenu = computed(() => {
      const { meta, path } = route;
      if (meta.activeMenu) {
        return meta.activeMenu;
      }
      return path;
    });

    // 从Vuex获取用户菜单数据，转换为顶部菜单格式
    const topMenus = computed(() => {
      return store.getters["auth/leftMenus"] || [];
    });

    // 用户信息相关
    const username = computed(() => {
      return store.getters["user/getUserInfo"]?.name || "用户";
    });

    const userAvatar = computed(() => {
      return store.getters["auth/currentUser"]?.avatar || "";
    });

    const userInitials = computed(() => {
      const name = username.value;
      return name ? name.charAt(0).toUpperCase() : "U";
    });

    // 处理菜单点击事件
    const handleMenuClick = (path: string) => {
      console.log("顶部菜单点击:", path);

      // 空路径不处理
      if (!path) return;

      // 确保路径格式正确
      const normalizedPath = path.startsWith("/") ? path : `/${path}`;

      // 导航到对应路由
      router.push(normalizedPath);
    };

    // 处理下拉菜单命令
    const handleCommand = (command: string) => {
      if (command === "logout") {
        store.dispatch("user/logout");
      } else if (command === "profile") {
        router.push("/profile");
      } else if (command === "settings") {
        router.push("/settings");
      } else if (command === "change-password") {
        showChangePasswordDialog.value = true;
      }
    };

    // 处理密码修改成功
    const handlePasswordChangeSuccess = () => {
      ElMessage.success("密码修改成功！为了您的账户安全，请重新登录");
      // 可选择：修改密码成功后强制用户重新登录
      // setTimeout(() => {
      //   store.dispatch('user/logout')
      // }, 2000)
    };

    // 组件加载时获取菜单数据
    onMounted(async () => {});

    return {
      activeMenu,
      topMenus,
      username,
      userAvatar,
      userInitials,
      handleMenuClick,
      handleCommand,
      handlePasswordChangeSuccess,
      showChangePasswordDialog,
      ArrowDown,
      SwitchButton,
      Lock,
    };
  },
});
</script>

<style scoped>
.logo-container {
  display: flex;
  align-items: center;
  gap: 12px;
}

.logo-image {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  object-fit: cover;
  flex-shrink: 0;
}

.logo-text {
  font-size: 18px;
  font-weight: bold;
  color: #409eff;
  white-space: nowrap;
}

:deep(.el-menu--horizontal) {
  border-bottom: none !important;
}

:deep(.el-menu--horizontal > .el-menu-item) {
  height: 60px;
  line-height: 60px;
}

:deep(.el-menu--horizontal > .el-sub-menu) {
  height: 60px;
  line-height: 60px;
}

:deep(.el-menu--horizontal > .el-sub-menu .el-sub-menu__title) {
  height: 60px;
  line-height: 60px;
}
</style>
