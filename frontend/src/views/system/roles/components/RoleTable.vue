<template>
  <div class="w-full h-full">
    <el-table
      size="default"
      :data="roleData"
      stripe
      border
      :max-height="maxHeight"
    >
      <el-table-column prop="name" label="角色名称" min-width="120" />
      <el-table-column prop="code" label="角色编码" min-width="120" />
      <el-table-column
        prop="description"
        label="描述"
        min-width="200"
        show-overflow-tooltip
      />

      <!-- 角色状态 -->
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

      <!-- 系统角色标识 -->
      <el-table-column label="系统角色" width="100" align="center">
        <template #default="{ row }">
          <el-tag v-if="row.isSystem" type="warning" size="small" effect="light"
            >是</el-tag
          >
          <el-tag v-else type="info" size="small" effect="light">否</el-tag>
        </template>
      </el-table-column>

      <!-- 菜单权限数量 -->
      <el-table-column label="菜单数量" width="100" align="center">
        <template #default="{ row }">
          <el-tag type="info" size="small" effect="light">
            {{ row.menuIds?.length || 0 }}
          </el-tag>
        </template>
      </el-table-column>

      <!-- 权限数量 -->
      <el-table-column
        label="权限数量"
        width="100"
        align="center"
        v-if="!isMobile"
      >
        <template #default="{ row }">
          <el-tag type="info" size="small" effect="light">
            {{ row.permissions?.length || 0 }}
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
        min-width="200"
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
                <el-dropdown-item @click="handleEditRole(row)">
                  <el-icon><Edit /></el-icon>修改
                </el-dropdown-item>
                <el-dropdown-item
                  @click="handleDeleteRole(row)"
                  :disabled="row.isSystem"
                >
                  <el-icon><Delete /></el-icon>删除
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>

          <el-space wrap v-else>
            <el-button
              link
              type="primary"
              size="small"
              @click="handleEditRole(row)"
            >
              <el-icon><Edit /></el-icon>修改
            </el-button>
            <el-button
              link
              type="danger"
              size="small"
              @click="handleDeleteRole(row)"
              :disabled="row.isSystem"
            >
              <el-icon><Delete /></el-icon>删除
            </el-button>
          </el-space>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup>
import { ArrowDown, Edit, Delete } from "@element-plus/icons-vue";

const props = defineProps({
  roleData: {
    type: Array,
    required: true,
  },
  maxHeight: {
    type: String,
    default: "600px",
  },
  isMobile: {
    type: Boolean,
    default: false,
  },
});

const emit = defineEmits(["edit", "delete"]);

// 编辑角色
const handleEditRole = (row) => {
  emit("edit", row);
};

// 删除角色
const handleDeleteRole = (row) => {
  if (row.isSystem) return;
  emit("delete", row);
};
</script>

<style scoped></style>
