<template>
  <!-- 网格模式 -->
  <div
    v-if="viewMode === 'grid'"
    class="class-card bg-white rounded-xl shadow-sm border border-gray-200 hover:shadow-lg transition-all duration-300 overflow-hidden"
  >
    <!-- 卡片头部 -->
    <div class="p-6 pb-4">
      <!-- 状态标签 -->
      <div class="flex justify-between items-start mb-4">
        <el-tag :type="statusTagType" size="small" class="font-medium">
          {{ statusText }}
        </el-tag>
        <el-dropdown trigger="click" @command="handleCommand">
          <el-button
            :icon="MoreFilled"
            text
            size="small"
            class="text-gray-400 hover:text-gray-600"
          />
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="view" :icon="View">
                查看详情
              </el-dropdown-item>
              <el-dropdown-item command="edit" :icon="Edit">
                编辑班级
              </el-dropdown-item>
              <el-dropdown-item command="regenerate-code" :icon="RefreshRight">
                刷新邀请码
              </el-dropdown-item>
              <el-dropdown-item
                command="disband"
                :icon="Delete"
                divided
                class="text-red-600"
                v-if="classData.status !== 'disbanded'"
              >
                解散班级
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>

      <!-- 班级名称 -->
      <h3 class="text-xl font-bold text-gray-900 mb-2 line-clamp-2">
        {{ classData.name }}
      </h3>

      <!-- 班级描述 -->
      <p
        v-if="classData.description"
        class="text-gray-600 text-sm line-clamp-2 mb-4"
      >
        {{ classData.description }}
      </p>
      <div v-else class="mb-4">
        <span class="text-gray-400 text-sm italic">暂无描述</span>
      </div>

      <!-- 班级信息 -->
      <div class="space-y-3">
        <!-- 老师信息 -->
        <div class="flex items-center justify-between">
          <div class="flex items-center text-sm text-gray-500">
            <el-icon class="mr-2 text-blue-500"><User /></el-icon>
            <span>授课老师:</span>
          </div>
          <span class="text-sm font-medium text-gray-900">
            {{ classData.teacherName || "未知老师" }}
          </span>
        </div>

        <!-- 邀请码 -->
        <div class="flex items-center justify-between">
          <div class="flex items-center text-sm text-gray-500">
            <el-icon class="mr-2 text-green-500"><Key /></el-icon>
            <span>邀请码:</span>
          </div>
          <div class="flex items-center space-x-2">
            <code
              class="bg-gray-100 px-2 py-1 rounded text-sm font-mono text-blue-600"
            >
              {{ classData.code }}
            </code>
            <el-button
              :icon="CopyDocument"
              size="small"
              text
              @click="copyCode"
              class="text-gray-400 hover:text-blue-500"
              title="复制邀请码"
            />
          </div>
        </div>

        <!-- 学生数量 -->
        <div class="flex items-center justify-between">
          <div class="flex items-center text-sm text-gray-500">
            <el-icon class="mr-2 text-purple-500"><UserFilled /></el-icon>
            <span>学生数量:</span>
          </div>
          <span class="text-sm font-medium text-gray-900">
            {{ classData.studentCount }} / {{ classData.maxStudents }} 人
          </span>
        </div>

        <!-- 创建时间 -->
        <div class="flex items-center justify-between">
          <div class="flex items-center text-sm text-gray-500">
            <el-icon class="mr-2 text-orange-500"><Calendar /></el-icon>
            <span>创建时间:</span>
          </div>
          <span class="text-sm text-gray-900">
            {{ formatDate(classData.createdAt) }}
          </span>
        </div>
      </div>
    </div>

    <!-- 卡片底部操作区 -->
    <div class="px-6 py-4 bg-gray-50 border-t border-gray-100">
      <div class="flex justify-between items-center">
        <el-button
          type="primary"
          size="small"
          @click="handleCommand('view')"
          class="flex-1 mr-2"
        >
          <el-icon class="mr-1"><View /></el-icon>
          查看详情
        </el-button>
        <el-button size="small" @click="handleCommand('edit')" class="flex-1">
          <el-icon class="mr-1"><Edit /></el-icon>
          编辑
        </el-button>
      </div>
    </div>
  </div>

  <!-- 列表模式 -->
  <el-card
    v-else
    class="teacher-class-card-list"
    shadow="hover"
    :body-style="{ padding: '0' }"
  >
    <div class="list-row">
      <!-- 状态指示器 -->
      <div class="status-indicator">
        <el-tag :type="statusTagType" size="small" effect="light">
          {{ statusText }}
        </el-tag>
      </div>

      <!-- 主要信息区域 -->
      <div class="main-content">
        <!-- 班级标题行 -->
        <div class="class-header">
          <h3 class="class-name">{{ classData.name }}</h3>
        </div>

        <!-- 班级描述 -->
        <div class="class-description" v-if="classData.description">
          {{ classData.description }}
        </div>

        <!-- 元数据信息 -->
        <div class="class-meta">
          <span class="meta-item">
            <el-icon class="meta-icon"><User /></el-icon>
            {{ classData.teacherName || "未知教师" }}
          </span>
          <span class="meta-divider">•</span>
          <span class="meta-item">
            <el-icon class="meta-icon"><UserFilled /></el-icon>
            {{ classData.studentCount }}/{{ classData.maxStudents }}人
          </span>
          <span class="meta-divider">•</span>
          <span class="meta-item">
            <el-icon class="meta-icon"><Key /></el-icon>
            {{ classData.code }}
          </span>
          <span class="meta-divider">•</span>
          <span class="meta-item">
            <el-icon class="meta-icon"><Calendar /></el-icon>
            {{ formatDate(classData.createdAt) }}
          </span>
        </div>
      </div>

      <!-- 操作按钮区 -->
      <div class="actions-area">
        <el-button
          type="primary"
          size="small"
          @click="handleCommand('view')"
          class="enter-btn"
        >
          <el-icon class="mr-1"><View /></el-icon>
          查看详情
        </el-button>

        <div class="secondary-actions">
          <el-button
            size="small"
            text
            @click="copyCode"
            class="copy-btn-compact"
            title="复制邀请码"
          >
            <el-icon><CopyDocument /></el-icon>
          </el-button>

          <el-dropdown
            trigger="click"
            @command="handleCommand"
            placement="bottom-end"
          >
            <el-button
              :icon="MoreFilled"
              text
              size="small"
              class="more-btn-compact"
            />
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="view" :icon="View">
                  查看详情
                </el-dropdown-item>
                <el-dropdown-item command="edit" :icon="Edit">
                  编辑班级
                </el-dropdown-item>
                <el-dropdown-item
                  command="regenerate-code"
                  :icon="RefreshRight"
                >
                  刷新邀请码
                </el-dropdown-item>
                <el-dropdown-item
                  command="disband"
                  :icon="Delete"
                  divided
                  class="text-red-600"
                  v-if="classData.status !== 'disbanded'"
                >
                  解散班级
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </div>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { ElMessage } from "element-plus";
import moment from "moment";
import {
  MoreFilled,
  View,
  Edit,
  RefreshRight,
  Delete,
  CopyDocument,
  User,
  Key,
  UserFilled,
  Calendar,
} from "@element-plus/icons-vue";

// 本地定义类型，避免导入问题
interface Class {
  _id: string;
  name: string;
  code: string;
  teacherId: string;
  teacherName?: string;
  status: "active" | "inactive" | "disbanded";
  studentCount: number;
  maxStudents: number;
  description?: string;
  createdAt: string;
  updatedAt: string;
}

interface Props {
  classData: Class;
  viewMode?: "grid" | "list";
}

interface Emits {
  (e: "view", classData: Class): void;
  (e: "edit", classData: Class): void;
  (e: "disband", classData: Class): void;
  (e: "regenerate-code", classData: Class): void;
}

const props = withDefaults(defineProps<Props>(), {
  viewMode: "grid",
});
const emit = defineEmits<Emits>();

// 状态标签类型
const statusTagType = computed(() => {
  switch (props.classData.status) {
    case "active":
      return "success";
    case "inactive":
      return "warning";
    case "disbanded":
      return "danger";
    default:
      return "info";
  }
});

// 状态文本
const statusText = computed(() => {
  switch (props.classData.status) {
    case "active":
      return "活跃";
    case "inactive":
      return "暂停";
    case "disbanded":
      return "已解散";
    default:
      return "未知";
  }
});

// 格式化日期
const formatDate = (dateStr: string) => {
  return moment(dateStr).format("YYYY-MM-DD");
};

// 复制邀请码
const copyCode = async () => {
  try {
    await navigator.clipboard.writeText(props.classData.code);
    ElMessage.success("邀请码已复制到剪贴板");
  } catch (error) {
    console.error("复制失败:", error);
    ElMessage.error("复制失败");
  }
};

// 处理命令
const handleCommand = (command: string) => {
  switch (command) {
    case "view":
      emit("view", props.classData);
      break;
    case "edit":
      emit("edit", props.classData);
      break;
    case "disband":
      emit("disband", props.classData);
      break;
    case "regenerate-code":
      emit("regenerate-code", props.classData);
      break;
  }
};
</script>

<script lang="ts">
// 添加默认导出以支持常规导入
import { defineComponent } from "vue";

export default defineComponent({
  name: "ClassCard",
});
</script>

<style scoped>
/* 网格模式样式 */
.class-card {
  @apply cursor-pointer;
}

.class-card:hover {
  @apply border-blue-300;
}

.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* 列表模式样式 */
.teacher-class-card-list {
  transition: all 0.3s ease;
  border: 1px solid var(--el-border-color-light);
}

.teacher-class-card-list:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  border-color: var(--el-color-primary-light-7);
}

.list-row {
  display: flex;
  align-items: center;
  padding: 12px 16px;
  gap: 16px;
  min-height: 56px;
}

.status-indicator {
  flex-shrink: 0;
}

.main-content {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.class-header {
  display: flex;
  align-items: center;
}

.class-name {
  font-size: 16px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
}

.class-description {
  font-size: 13px;
  color: var(--el-text-color-regular);
  line-height: 1.4;
  margin: 2px 0;
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.class-meta {
  font-size: 12px;
  color: var(--el-text-color-regular);
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 4px;
  color: var(--el-text-color-regular);
}

.meta-icon {
  font-size: 12px;
  color: var(--el-color-primary);
}

.meta-divider {
  color: var(--el-text-color-placeholder);
}

.actions-area {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 8px;
  flex-shrink: 0;
  min-width: 120px;
}

.enter-btn {
  font-size: 12px;
  padding: 4px 12px;
  height: 28px;
}

.enter-btn:disabled {
  opacity: 0.6;
}

.secondary-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}

.copy-btn-compact,
.more-btn-compact {
  color: var(--el-text-color-placeholder);
  width: 24px;
  height: 24px;
  padding: 0;
}

.copy-btn-compact:hover,
.more-btn-compact:hover {
  color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
}

/* 响应式优化 */
@media (max-width: 768px) {
  .list-row {
    flex-direction: column;
    align-items: flex-start;
    padding: 12px;
    gap: 8px;
    min-height: auto;
  }

  .status-indicator {
    align-self: flex-start;
  }

  .main-content {
    width: 100%;
    gap: 6px;
  }

  .class-name {
    font-size: 15px;
    max-width: none;
  }

  .class-description {
    font-size: 12px;
  }

  .class-meta {
    font-size: 11px;
  }

  .meta-icon {
    font-size: 11px;
  }

  .actions-area {
    width: 100%;
    flex-direction: row;
    justify-content: space-between;
    align-items: center;
    padding-top: 8px;
    border-top: 1px solid var(--el-border-color-lighter);
    min-width: auto;
  }

  .enter-btn {
    font-size: 12px;
    height: 28px;
    padding: 0 12px;
  }

  .secondary-actions {
    gap: 8px;
  }

  .copy-btn-compact,
  .more-btn-compact {
    width: 28px;
    height: 28px;
  }
}
</style>
