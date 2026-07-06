<template>
  <!-- 调试信息 -->
  <div v-if="!menu.hidden" style="display: contents">
    <!-- 有子菜单的情况 - 渲染为el-sub-menu -->
    <el-sub-menu
      v-if="hasChildren && menu.type === 'menu'"
      :index="menu.path || `menu-${menu._id}`"
    >
      <template #title>
        <el-icon>
          <component :is="iconComponent" />
        </el-icon>
        <span>{{ menu.meta?.title || menu.name }}</span>
      </template>

      <!-- 递归渲染子菜单 -->
      <top-nav-item
        v-for="child in menu.children"
        :key="child._id"
        :menu="child"
        @menu-click="handleMenuClick"
      />
    </el-sub-menu>

    <!-- 没有子菜单的情况 - 渲染为el-menu-item -->
    <el-menu-item
      v-else-if="menu.type !== 'button'"
      :index="menu.path || `menu-${menu._id}`"
      @click="handleMenuClick(menu.path)"
      class="flex items-center"
    >
      <el-icon class="mr-1">
        <component :is="iconComponent" />
      </el-icon>
      <span>{{ menu.meta?.title || menu.name }}</span>
    </el-menu-item>
  </div>
</template>

<script lang="ts">
import { computed, defineComponent } from "vue";
import * as ElementPlusIcons from "@element-plus/icons-vue";

export default defineComponent({
  name: "TopNavItem",
  props: {
    menu: {
      type: Object,
      required: true,
    },
  },
  emits: ["menu-click"],
  setup(props, { emit }) {
    // 调试信息
    console.log("TopNavItem渲染菜单:", props.menu);

    // 计算是否有子菜单
    const hasChildren = computed(() => {
      const hasKids = props.menu.children && props.menu.children.length > 0;
      console.log(`菜单 ${props.menu.name} 是否有子菜单:`, hasKids);
      return hasKids;
    });

    // 处理图标
    const iconComponent = computed(() => {
      const icon = props.menu.icon;

      // 如果没有指定图标，返回默认图标
      if (!icon) return "Menu";

      // 转换图标名称为Pascal命名法
      const iconName = icon.charAt(0).toUpperCase() + icon.slice(1);

      // 检查图标是否存在
      return ElementPlusIcons[iconName] ? iconName : "Menu";
    });

    // 处理菜单点击
    const handleMenuClick = (path) => {
      console.log("TopNavItem菜单点击:", path);
      emit("menu-click", path);
    };

    return {
      hasChildren,
      iconComponent,
      handleMenuClick,
    };
  },
});
</script>

<style scoped>
/* 顶部菜单项样式调整 */
:deep(.el-menu-item) {
  border-bottom: none !important;
}

:deep(.el-sub-menu__title) {
  border-bottom: none !important;
}
</style>
