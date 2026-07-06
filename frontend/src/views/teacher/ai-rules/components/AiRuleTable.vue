<template>
  <div class="w-full">
    <el-table
      size="default"
      :data="ruleData"
      stripe
      border
      :max-height="maxHeight"
      v-loading="loading"
    >
      <el-table-column
        prop="name"
        label="规则名称"
        min-width="150"
        show-overflow-tooltip
      >
        <template #default="{ row }">
          <div class="flex items-center">
            <span>{{ row.name }}</span>
            <!-- 系统规则标识 -->
            <el-tag
              v-if="isSystemRule(row)"
              type="warning"
              size="small"
              effect="light"
              class="ml-2"
            >
              系统
            </el-tag>
            <!-- 管理员公开规则标识 -->
            <el-tag
              v-else-if="isAdminPublicRule(row)"
              type="success"
              size="small"
              effect="light"
              class="ml-2"
            >
              全局
            </el-tag>
          </div>
        </template>
      </el-table-column>

      <el-table-column
        prop="description"
        label="描述"
        min-width="200"
        show-overflow-tooltip
      />

      <!-- 模型类型 -->
      <el-table-column label="模型类型" width="120" align="center">
        <template #default="{ row }">
          <el-tag
            :type="getModelTypeColor(row.modelType)"
            size="small"
            effect="light"
          >
            {{ getModelTypeName(row.modelType) }}
          </el-tag>
        </template>
      </el-table-column>

      <!-- 规则状态 -->
      <el-table-column label="状态" width="100" align="center">
        <template #default="{ row }">
          <el-tag
            :type="row.status === 'active' ? 'success' : 'danger'"
            size="small"
            effect="light"
          >
            {{ row.status === "active" ? "启用" : "禁用" }}
          </el-tag>
        </template>
      </el-table-column>

      <!-- 可见性 -->
      <el-table-column label="可见性" width="100" align="center">
        <template #default="{ row }">
          <el-tag
            :type="getVisibilityColor(row.visibility)"
            size="small"
            effect="light"
          >
            {{ getVisibilityName(row.visibility) }}
          </el-tag>
        </template>
      </el-table-column>

      <!-- 标签 -->
      <el-table-column label="标签" min-width="150" v-if="!isMobile">
        <template #default="{ row }">
          <div class="flex flex-wrap gap-1">
            <el-tag
              v-for="tag in row.tags?.slice(0, 3)"
              :key="tag"
              size="small"
              effect="plain"
              class="mr-1 mb-1"
            >
              {{ tag }}
            </el-tag>
            <el-tag
              v-if="row.tags?.length > 3"
              size="small"
              type="info"
              effect="plain"
            >
              +{{ row.tags.length - 3 }}
            </el-tag>
          </div>
        </template>
      </el-table-column>

      <!-- 创建者 -->
      <el-table-column
        label="创建者"
        width="120"
        align="center"
        v-if="!isMobile"
      >
        <template #default="{ row }">
          {{ row.createdBy?.name || "-" }}
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
        min-width="220"
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
                <el-dropdown-item @click="handleViewRule(row)">
                  <el-icon><View /></el-icon>查看
                </el-dropdown-item>
                <el-dropdown-item
                  @click="handleEditRule(row)"
                  :disabled="!canEditRule(row)"
                >
                  <el-icon><Edit /></el-icon>修改
                </el-dropdown-item>
                <el-dropdown-item @click="handleCopyRule(row)">
                  <el-icon><CopyDocument /></el-icon>复制
                </el-dropdown-item>
                <el-dropdown-item
                  @click="handleDeleteRule(row)"
                  :disabled="!canDeleteRule(row)"
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
              @click="handleViewRule(row)"
            >
              <el-icon><View /></el-icon>查看
            </el-button>
            <el-button
              link
              type="primary"
              size="small"
              @click="handleEditRule(row)"
              :disabled="!canEditRule(row)"
            >
              <el-icon><Edit /></el-icon>修改
            </el-button>
            <el-button
              link
              type="success"
              size="small"
              @click="handleCopyRule(row)"
            >
              <el-icon><CopyDocument /></el-icon>复制
            </el-button>
            <el-button
              link
              type="danger"
              size="small"
              @click="handleDeleteRule(row)"
              :disabled="!canDeleteRule(row)"
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
import {
  ArrowDown,
  Edit,
  Delete,
  View,
  CopyDocument,
} from "@element-plus/icons-vue";

const props = defineProps({
  ruleData: {
    type: Array,
    required: true,
  },
  maxHeight: {
    type: String,
    default: "600px",
  },
  loading: {
    type: Boolean,
    default: false,
  },
  isMobile: {
    type: Boolean,
    default: false,
  },
  currentUser: {
    type: Object,
    default: null,
  },
});

const emit = defineEmits(["edit", "delete", "copy", "view"]);

// 获取模型类型显示名称
const getModelTypeName = (modelType) => {
  const typeMap = {
    deepseek: "DeepSeek",
  };
  return typeMap[modelType] || modelType;
};

// 获取模型类型颜色
const getModelTypeColor = (modelType) => {
  const colorMap = {
    deepseek: "primary",
  };
  return colorMap[modelType] || "primary";
};

// 获取可见性显示名称
const getVisibilityName = (visibility) => {
  const nameMap = {
    private: "私有",
    public: "公开",
    system: "系统",
  };
  return nameMap[visibility] || visibility;
};

// 获取可见性颜色
const getVisibilityColor = (visibility) => {
  const colorMap = {
    private: "info",
    public: "success",
    system: "warning",
  };
  return colorMap[visibility] || "default";
};

// 查看规则
const handleViewRule = (row) => {
  emit("view", row);
};

// 编辑规则
const handleEditRule = (row) => {
  emit("edit", row);
};

// 复制规则
const handleCopyRule = (row) => {
  emit("copy", row);
};

// 删除规则
const handleDeleteRule = (row) => {
  if (!canDeleteRule(row)) {
    console.log("无权限删除规则:", {
      rule: row.name,
      visibility: row.visibility,
      createdBy: row.createdBy,
      currentUser: props.currentUser,
      canDelete: canDeleteRule(row),
    });
    return;
  }
  emit("delete", row);
};

// 判断是否为系统规则
const isSystemRule = (row) => {
  return row.visibility === "system";
};

// 判断是否为管理员公开规则
const isAdminPublicRule = (row) => {
  return (
    row.visibility === "public" &&
    (row.createdBy?.role === "superadmin" || row.createdBy?.role === "admin")
  );
};

// 判断是否有权限编辑规则
const canEditRule = (row) => {
  // 系统规则不可编辑
  if (row.visibility === "system") {
    return false;
  }

  // 如果没有当前用户信息，不允许编辑
  if (!props.currentUser) {
    return false;
  }

  // 超级管理员可以编辑所有规则
  if (props.currentUser.role === "superadmin") {
    return true;
  }

  // 只有创建者可以编辑自己的规则
  return (
    row.createdBy?._id === props.currentUser._id ||
    row.createdBy?.id === props.currentUser._id
  );
};

// 判断是否有权限删除规则
const canDeleteRule = (row) => {
  // 系统规则不可删除
  if (row.visibility === "system") {
    return false;
  }

  // 如果没有当前用户信息，不允许删除
  if (!props.currentUser) {
    return false;
  }

  // 超级管理员可以删除所有规则
  if (props.currentUser.role === "superadmin") {
    return true;
  }

  // 只有创建者可以删除自己的规则
  return (
    row.createdBy?._id === props.currentUser._id ||
    row.createdBy?.id === props.currentUser._id
  );
};
</script>

<style scoped>
.flex {
  display: flex;
}

.flex-wrap {
  flex-wrap: wrap;
}

.gap-1 {
  gap: 0.25rem;
}

.mr-1 {
  margin-right: 0.25rem;
}

.mb-1 {
  margin-bottom: 0.25rem;
}

.ml-2 {
  margin-left: 0.5rem;
}

.items-center {
  align-items: center;
}
</style>
