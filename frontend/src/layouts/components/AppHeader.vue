<template>
  <div class="flex justify-between items-center h-full w-full">
    <!-- 左侧区域 -->
    <div class="flex items-center">
      <!-- 在AppLayout中已经添加了移动版的侧边栏切换按钮，这里隐藏重复按钮 -->
      <!-- "text-2xl cursor-pointer mr-5 text-gray-700" 什麽意思 -->
      <!-- 2xl 表示字体大小为2倍，cursor-pointer 表示鼠标悬停时变成手型，mr-5 表示右边距为5，text-gray-700 表示字体颜色为灰色 -->
      <el-icon
        size="20"
        class="text-1xl cursor-pointer mr-5 text-gray-700"
        @click="toggleSidebar"
      >
        <Fold v-if="sidebarOpened" />
        <Expand v-else />
      </el-icon>

      <Breadcrumb />
    </div>

    <!-- 右侧区域 -->
    <div class="flex items-center">
      <!-- 顶部导航按钮 - 响应式隐藏非关键按钮 -->
      <div class="flex mr-2">
        <el-tooltip content="首页" placement="bottom">
          <el-button
            :icon="HomeFilled"
            link
            @click="$router.push('/')"
            class="!flex items-center justify-center"
          />
        </el-tooltip>
      </div>

      <el-divider direction="vertical" class="hidden sm:block" />

      <!-- 用户下拉菜单 - 响应式调整 -->
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
import { computed, ref } from "vue";
import { useStore } from "vuex";
import { useRouter } from "vue-router";
import { defineComponent } from "vue";
import { ElMessage } from "element-plus";
import {
  HomeFilled,
  Bell,
  ArrowDown,
  User,
  Setting,
  SwitchButton,
  Menu,
  Fold,
  Expand,
  Lock,
} from "@element-plus/icons-vue";
import Breadcrumb from "./Breadcrumb.vue";
import ChangePasswordDialog from "./ChangePasswordDialog.vue";

export default defineComponent({
  name: "AppHeader",
  components: {
    Breadcrumb,
    Fold,
    Expand,
    ChangePasswordDialog,
  },
  setup() {
    const store = useStore();
    const router = useRouter();

    // 获取侧边栏状态
    const sidebarOpened = computed(() => store.getters["app/sidebarOpened"]);

    // 修改密码弹窗控制
    const showChangePasswordDialog = ref(false);

    // 用户名
    const username = computed(() => {
      return store.getters["user/getUserInfo"]?.name || "用户";
    });

    // 用户头像
    const userAvatar = computed(() => {
      return store.getters["auth/currentUser"]?.avatar || "";
    });

    // 如果没有头像，显示用户名首字母
    const userInitials = computed(() => {
      const name = username.value;
      return name ? name.charAt(0).toUpperCase() : "U";
    });

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

    // 切换侧边栏
    const toggleSidebar = () => {
      store.dispatch("app/toggleSidebar");
    };

    return {
      username,
      userAvatar,
      userInitials,
      handleCommand,
      handlePasswordChangeSuccess,
      toggleSidebar,
      sidebarOpened,
      showChangePasswordDialog,
      HomeFilled,
      Bell,
      ArrowDown,
      User,
      Setting,
      SwitchButton,
      Menu,
      Lock,
    };
  },
});
</script>

<style scoped></style>
