<template>
  <el-breadcrumb class="inline-block text-sm ml-2">
    <!-- 当没有面包屑项时显示默认项 -->
    <template v-if="breadcrumbItems.length > 0">
      <el-breadcrumb-item
        v-for="(item, index) in breadcrumbItems"
        :key="item.path"
      >
        <router-link
          v-if="index !== breadcrumbItems.length - 1"
          :to="item.path"
        >
          {{ item.meta?.title }}
        </router-link>

        <span v-else class="text-gray-800">{{ item.meta?.title }}</span>
      </el-breadcrumb-item>
    </template>
    <template v-else>
      <el-breadcrumb-item>
        <span class="text-gray-800">{{ currentPageTitle }}</span>
      </el-breadcrumb-item>
    </template>
  </el-breadcrumb>
</template>

<script lang="ts">
import { ref, computed, watch, defineComponent } from "vue";
import { useRoute } from "vue-router";
import type { RouteLocationMatched } from "vue-router";

export default defineComponent({
  name: "Breadcrumb",
  setup() {
    const route = useRoute();

    // 需要排除的路由（改为空数组，不再排除dashboard）
    const excludeRoutes = ref<string[]>([]);

    // 面包屑导航项
    const breadcrumbItems = computed(() => {
      // 过滤掉需要排除的路由和没有meta.title的路由
      const items = route.matched.filter((item: RouteLocationMatched) => {
        if (excludeRoutes.value.includes(item.name as string)) {
          return false;
        }
        return item.meta && item.meta.title;
      });

      console.log("当前路由matched:", route.matched);
      console.log("面包屑项目:", items);

      return items;
    });

    // 当前页面标题（兜底显示）
    const currentPageTitle = computed(() => {
      // 首先尝试获取当前路由的标题
      if (route.meta?.title) {
        return route.meta.title;
      }

      // 其次尝试获取最后一个matched路由的标题
      if (route.matched.length > 0) {
        const lastMatched = route.matched[route.matched.length - 1];
        if (lastMatched.meta?.title) {
          return lastMatched.meta.title;
        }
      }

      // 最后使用路由名称或路径
      return route.name || route.path.split("/").pop() || "当前页面";
    });

    // 监听路由变化，更新breadcrumbs
    watch(
      () => route.path,
      () => {
        // 这里可以添加其他逻辑
      }
    );

    return {
      breadcrumbItems,
      currentPageTitle,
    };
  },
});
</script>

<style scoped>
.app-breadcrumb {
  display: inline-block;
  font-size: 120px;
  line-height: 60px;
  margin-left: 10px;
}
</style>
