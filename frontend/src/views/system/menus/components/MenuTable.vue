<template>
  <div class="w-full">
    <el-table
      v-if="isShow"
      v-loading="loading"
      element-loading-text="加载中..."
      size="default"
      :data="menuData"
      stripe
      row-key="_id"
      border
      :max-height="maxHeight"
      :tree-props="{ children: 'children', hasChildren: 'hasChildren' }"
      :default-expand-all="isExpandAll"
    >
      <template #empty>
        <!-- 加载中 -->
        <!-- 暂无数据 -->
        <el-empty
          v-if="menuData.length === 0 && !loading"
          description="暂无数据"
        />
      </template>

      <el-table-column prop="name" label="菜单名称" min-width="180" />
      <el-table-column label="图标" width="70" align="center">
        <template #default="{ row }">
          <el-icon v-if="row.icon" class="text-lg">
            <component :is="row.icon"></component>
          </el-icon>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column label="类型" width="80" align="center">
        <template #default="{ row }">
          <el-tag :type="row.type === 'menu' ? 'primary' : 'info'" size="small">
            {{ row.type === "menu" ? "菜单" : "按钮" }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column
        prop="path"
        label="路径"
        min-width="120"
        v-if="!isMobile"
      />

      <!-- 权限编码 -->
      <el-table-column prop="code" label="权限编码" min-width="140" />

      <el-table-column
        prop="component"
        label="组件路径"
        min-width="140"
        v-if="!isMobile"
      />
      <el-table-column
        prop="sort"
        label="排序"
        width="80"
        align="center"
        v-if="!isMobile"
      />
      <el-table-column label="状态" width="100" align="center">
        <template #default="{ row }">
          <el-tag
            :type="row.status === 'active' ? 'success' : 'danger'"
            size="small"
            effect="light"
          >
            {{ row.status === "active" ? "正常" : "禁用" }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="隐藏" width="80" align="center" v-if="!isMobile">
        <template #default="{ row }">
          <el-tag
            :type="row.hidden ? 'danger' : 'success'"
            size="small"
            effect="light"
          >
            {{ row.hidden ? "是" : "否" }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column
        label="创建时间"
        min-width="150"
        align="center"
        v-if="!isMobile"
      >
        <template #default="{ row }">
          {{ row.createdAt ? new Date(row.createdAt).toLocaleString() : "-" }}
        </template>
      </el-table-column>
      <el-table-column
        label="操作"
        min-width="160"
        fixed="right"
        align="center"
      >
        <template #default="{ row }">
          <el-dropdown v-if="isMobile">
            <el-button type="primary" link>
              操作<el-icon class="el-icon--right"><arrow-down /></el-icon>
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item
                  v-if="row.type === 'menu'"
                  @click="handleAddSubmenu(row)"
                >
                  <el-icon><DocumentAdd /></el-icon>子菜单
                </el-dropdown-item>
                <el-dropdown-item @click="handleEditMenu(row)">
                  <el-icon><Edit /></el-icon>修改
                </el-dropdown-item>
                <el-dropdown-item @click="handleDeleteMenu(row)">
                  <el-icon><Delete /></el-icon>删除
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>

          <el-space wrap v-else>
            <el-button
              v-if="row.type === 'menu'"
              link
              type="primary"
              size="small"
              @click="handleAddSubmenu(row)"
            >
              <el-icon><DocumentAdd /></el-icon>子菜单
            </el-button>
            <el-button
              link
              type="primary"
              size="small"
              @click="handleEditMenu(row)"
            >
              <el-icon><Edit /></el-icon>修改
            </el-button>
            <el-button
              link
              type="danger"
              size="small"
              @click="handleDeleteMenu(row)"
            >
              <el-icon><Delete /></el-icon>删除
            </el-button>
          </el-space>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script lang="ts" setup>
import { ref, nextTick } from "vue";
import type { Menu } from "@/types/menu";

const props = defineProps({
  menuData: {
    type: Array as () => Menu[],
    required: true,
  },
  maxHeight: {
    type: String,
    default: "600px",
  },
  loading: {
    type: Boolean,
    default: true,
  },
  defaultExpandAll: {
    type: Boolean,
    default: false,
  },
  isMobile: {
    type: Boolean,
    default: false,
  },
});

const emit = defineEmits(["add-submenu", "edit", "delete"]);

// 控制表格显示状态
const isShow = ref(true);
// 控制表格展开状态
const isExpandAll = ref(props.defaultExpandAll);

// 添加子菜单
const handleAddSubmenu = (row: Menu) => {
  emit("add-submenu", row._id);
};

// 编辑菜单
const handleEditMenu = (row: Menu) => {
  emit("edit", row);
};

// 删除菜单
const handleDeleteMenu = (row: Menu) => {
  emit("delete", row);
};

// 展开所有节点
const expandAll = async () => {
  isShow.value = false;
  await nextTick();
  isExpandAll.value = true;
  isShow.value = true;
};

// 折叠所有节点
const collapseAll = async () => {
  isShow.value = false;
  isExpandAll.value = false;
  await nextTick();
  isShow.value = true;
};

// 对外暴露方法
defineExpose({
  expandAll,
  collapseAll,
});
</script>

<style scoped></style>
