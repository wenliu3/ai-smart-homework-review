<template>
  <component :is="currentLayout" />
</template>

<script lang="ts">
import { defineComponent, computed } from "vue";
import { useStore } from "vuex";
import AppLayout from "./AppLayout.vue";
import TopNavLayout from "./TopNavLayout.vue";

export default defineComponent({
  name: "LayoutIndex",
  components: {
    AppLayout,
    TopNavLayout,
  },
  setup() {
    const store = useStore();

    // 根据用户角色选择布局
    const currentLayout = computed(() => {
      // 从Vuex获取用户信息
      const userInfo = store.getters["user/getUserInfo"];
      const userRole = userInfo?.role;

      // 判断用户角色
      // 如果是管理员，使用侧边栏布局(AppLayout)
      // 其他角色使用顶部菜单布局(TopNavLayout)
      if (
        userRole === "admin" ||
        userRole === "administrator" ||
        userRole === "superadmin"
      ) {
        return "AppLayout";
      } else {
        return "AppLayout";
      }
    });

    return {
      currentLayout,
    };
  },
});
</script>

<style scoped>
/* 布局入口样式 */
</style>
