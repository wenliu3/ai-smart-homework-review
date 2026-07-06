<template>
  <div class="w-full h-full">
    <el-table
      size="default"
      :data="userData"
      stripe
      border
      @selection-change="handleSelectionChange"
      ref="tableRef"
    >
      <!--序號 -->

      <!-- 多选列 -->
      <el-table-column type="selection" width="55" :selectable="isSelectable" />

      <el-table-column
        prop="username"
        label="用户名"
        min-width="120"
        show-overflow-tooltip
      />
      <el-table-column
        prop="name"
        label="姓名"
        min-width="120"
        show-overflow-tooltip
      />

      <!-- 学号列 -->
      <el-table-column
        prop="studentId"
        label="学号"
        min-width="120"
        show-overflow-tooltip
      >
        <template #default="{ row }">
          {{ row.studentId || (row.role === "student" ? "-" : "N/A") }}
        </template>
      </el-table-column>

      <el-table-column
        prop="email"
        label="邮箱"
        min-width="150"
        show-overflow-tooltip
      />

      <!-- 手机号 -->
      <el-table-column
        prop="phone"
        label="手机号"
        min-width="120"
        v-if="!isMobile"
      >
        <template #default="{ row }">
          {{ row.phone || "-" }}
        </template>
      </el-table-column>

      <!-- 用户角色 -->
      <el-table-column label="角色" width="110" align="center">
        <template #default="{ row }">
          <el-tag :type="getRoleTagType(row.role)" size="small" effect="light">
            {{ getRoleName(row.role) }}
          </el-tag>
        </template>
      </el-table-column>

      <!-- 用户状态 -->
      <el-table-column label="状态" width="90" align="center">
        <template #default="{ row }">
          <el-switch
            v-model="row.status"
            :active-value="'active'"
            :inactive-value="'inactive'"
            @change="(val) => handleStatusChange(row, val)"
            :disabled="row.role === 'superadmin'"
          />
        </template>
      </el-table-column>

      <!-- 最后登录时间 -->
      <el-table-column
        label="最后登录"
        min-width="150"
        align="center"
        v-if="!isMobile"
      >
        <template #default="{ row }">
          {{ formatDate(row.lastLogin) }}
        </template>
      </el-table-column>

      <!-- 操作栏 -->
      <el-table-column
        label="操作"
        fixed="right"
        align="center"
        :width="isMobile ? 100 : 180"
      >
        <template #default="{ row }">
          <!-- 移动端下拉菜单操作 -->
          <el-dropdown v-if="isMobile">
            <el-button type="primary" link>
              操作<el-icon class="el-icon--right"><arrow-down /></el-icon>
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="handleEditUser(row)">
                  <el-icon><Edit /></el-icon>修改
                </el-dropdown-item>
                <el-dropdown-item @click="handleResetPassword(row)">
                  <el-icon><Key /></el-icon>重置密码
                </el-dropdown-item>
                <el-dropdown-item
                  @click="handleDeleteUser(row)"
                  :disabled="row.role === 'superadmin'"
                >
                  <el-icon><Delete /></el-icon>删除
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>

          <!-- 桌面端按钮操作 -->
          <el-space wrap v-else>
            <el-button
              link
              type="primary"
              size="small"
              @click="handleEditUser(row)"
            >
              <el-icon><Edit /></el-icon>修改
            </el-button>
            <el-button
              link
              type="warning"
              size="small"
              @click="handleResetPassword(row)"
            >
              <el-icon><Key /></el-icon>重置
            </el-button>
            <el-button
              link
              type="danger"
              size="small"
              @click="handleDeleteUser(row)"
              :disabled="row.role === 'superadmin'"
            >
              <el-icon><Delete /></el-icon>删除
            </el-button>
          </el-space>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { ArrowDown, Edit, Delete, Key } from "@element-plus/icons-vue";
import type { User, UserStatus } from "../../../../types/user";

const props = defineProps({
  userData: {
    type: Array as () => User[],
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

const emit = defineEmits([
  "edit",
  "delete",
  "change-status",
  "reset-password",
  "selection-change",
]);

// 表格引用
const tableRef = ref();

// 角色名称映射
const getRoleName = (role: string): string => {
  const roleMap: Record<string, string> = {
    superadmin: "超级管理员",
    teacher: "教师",
    student: "学生",
  };
  return roleMap[role] || role;
};

// 角色标签类型映射
const getRoleTagType = (role: string) => {
  const typeMap: Record<
    string,
    "danger" | "success" | "info" | "warning" | "primary"
  > = {
    superadmin: "danger",
    teacher: "success",
    student: "info",
  };
  return typeMap[role] || "info";
};

// 格式化日期
const formatDate = (date: string | Date | undefined): string => {
  if (!date) return "-";
  try {
    return new Date(date).toLocaleString();
  } catch (e) {
    return "-";
  }
};

// 修改用户状态
const handleStatusChange = (user: User, status: string | number | boolean) => {
  emit("change-status", user, status as UserStatus);
};

// 编辑用户
const handleEditUser = (row: User) => {
  emit("edit", row);
};

// 删除用户
const handleDeleteUser = (row: User) => {
  if (row.role === "superadmin") return;
  emit("delete", row);
};

// 重置密码
const handleResetPassword = (row: User) => {
  emit("reset-password", row);
};

// 处理选择变化
const handleSelectionChange = (selected: User[]) => {
  emit("selection-change", selected);
};

// 判断是否可选择（超级管理员不可选择）
const isSelectable = (row: User) => {
  return row.role !== "superadmin";
};

// 暴露清空选择的方法
const clearSelection = () => {
  tableRef.value?.clearSelection();
};

// 暴露给父组件的方法
defineExpose({
  clearSelection,
});
</script>

<style scoped></style>
