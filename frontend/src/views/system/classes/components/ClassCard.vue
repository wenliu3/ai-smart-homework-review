<template>
  <!-- 网格模式 -->
  <el-card
    v-if="viewMode === 'grid'"
    class="class-card"
    shadow="hover"
    :body-style="{ padding: '16px' }"
  >
    <!-- 卡片头部 -->
    <template #header>
      <div class="card-header">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2">
            <el-tag
              :type="getStatusTagType(classData.status)"
              size="small"
              effect="light"
            >
              {{ getStatusText(classData.status) }}
            </el-tag>
            <el-tag size="small" type="info" effect="plain">
              {{ classData.code }}
            </el-tag>
          </div>
          <el-dropdown trigger="click" @command="handleCommand">
            <el-button :icon="MoreFilled" text size="small" class="more-btn" />
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="view" :icon="View">
                  查看详情
                </el-dropdown-item>
                <el-dropdown-item command="leave" :icon="Close" divided>
                  退出班级
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
        <h3 class="class-title">{{ classData.name }}</h3>
        <p class="class-desc">{{ classData.description || "暂无课程描述" }}</p>
      </div>
    </template>

    <!-- 卡片内容 -->
    <div class="class-info">
      <div class="info-item">
        <el-icon class="info-icon"><User /></el-icon>
        <span class="info-label">教师:</span>
        <span class="info-value">{{ classData.teacherName || "未知" }}</span>
      </div>
      <div class="info-item">
        <el-icon class="info-icon"><UserFilled /></el-icon>
        <span class="info-label">人数:</span>
        <span class="info-value"
          >{{ classData.studentCount }}/{{ classData.maxStudents }}</span
        >
      </div>
      <div class="info-item">
        <el-icon class="info-icon"><Calendar /></el-icon>
        <span class="info-label">加入:</span>
        <span class="info-value">{{ formatDate(classData.createdAt) }}</span>
      </div>
    </div>

    <!-- 操作按钮 -->
    <div class="class-actions">
      <el-button
        type="primary"
        size="default"
        @click="handleView"
        class="w-full"
        :disabled="classData.status !== 'active'"
      >
        <el-icon class="mr-1"><View /></el-icon>
        进入班级
      </el-button>
      <el-button size="small" text @click="copyCode" class="copy-btn">
        <el-icon class="mr-1"><CopyDocument /></el-icon>
        复制班级码
      </el-button>
    </div>
  </el-card>

  <!-- 列表模式 -->
  <el-card
    v-else
    class="class-card-list"
    shadow="hover"
    :body-style="{ padding: '0' }"
  >
    <div class="list-row">
      <!-- 状态指示器 -->
      <div class="status-indicator">
        <el-tag
          :type="getStatusTagType(classData.status)"
          size="small"
          effect="light"
        >
          {{ getStatusText(classData.status) }}
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
            <el-icon class="meta-icon"><Calendar /></el-icon>
            {{ formatListDate(classData.createdAt) }}
          </span>
        </div>
      </div>

      <!-- 操作按钮区 -->
      <div class="actions-area">
        <el-button
          type="primary"
          size="small"
          @click="handleView"
          :disabled="classData.status !== 'active'"
          class="enter-btn"
        >
          <el-icon class="mr-1"><View /></el-icon>
          进入班级
        </el-button>

        <div class="secondary-actions">
          <el-button
            size="small"
            text
            @click="copyCode"
            class="copy-btn-compact"
            title="复制班级码"
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
                <el-dropdown-item command="leave" :icon="Close" divided>
                  退出班级
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
import { ElMessage } from "element-plus";
import {
  MoreFilled,
  View,
  Close,
  User,
  UserFilled,
  Calendar,
  CopyDocument,
} from "@element-plus/icons-vue";
import moment from "moment";
import type { Class } from "@/types/classes";

interface Props {
  classData: Class;
  viewMode?: "grid" | "list";
}

interface Emits {
  (e: "view", classData: Class): void;
  (e: "leave", classData: Class): void;
}

const props = withDefaults(defineProps<Props>(), {
  viewMode: "grid",
});
const emit = defineEmits<Emits>();

// 状态标签类型
const getStatusTagType = (status: string) => {
  switch (status) {
    case "active":
      return "success";
    case "inactive":
      return "warning";
    case "disbanded":
      return "danger";
    default:
      return "info";
  }
};

// 状态文本
const getStatusText = (status: string) => {
  switch (status) {
    case "active":
      return "活跃";
    case "inactive":
      return "暂停";
    case "disbanded":
      return "已解散";
    default:
      return "未知";
  }
};

// 格式化日期
const formatDate = (dateStr: string) => {
  return moment(dateStr).format("MM/DD");
};

// 格式化列表日期
const formatListDate = (dateStr: string) => {
  return moment(dateStr).format("MM/DD");
};

// 复制班级码
const copyCode = async () => {
  try {
    await navigator.clipboard.writeText(props.classData.code);
    ElMessage.success("班级码已复制");
  } catch (error) {
    console.error("复制失败:", error);
    ElMessage.error("复制失败");
  }
};

// 处理查看
const handleView = () => {
  emit("view", props.classData);
};

// 处理下拉菜单命令
const handleCommand = (command: string) => {
  switch (command) {
    case "view":
      emit("view", props.classData);
      break;
    case "leave":
      emit("leave", props.classData);
      break;
  }
};
</script>

<style scoped>
/* 网格模式样式 */
.class-card {
  height: 100%;
  transition: all 0.3s ease;
}

.class-card:hover {
  transform: translateY(-2px);
}

.card-header {
  padding: 0;
}

.class-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin: 8px 0 4px 0;
  line-height: 1.4;
}

.class-desc {
  font-size: 13px;
  color: var(--el-text-color-regular);
  margin: 0;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.class-info {
  margin: 16px 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.info-item {
  display: flex;
  align-items: center;
  font-size: 13px;
}

.info-icon {
  color: var(--el-color-primary);
  margin-right: 6px;
  font-size: 14px;
}

.info-label {
  color: var(--el-text-color-regular);
  margin-right: 4px;
  min-width: 32px;
}

.info-value {
  color: var(--el-text-color-primary);
  font-weight: 500;
}

.class-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 16px;
}

/* 列表模式样式 */
.class-card-list {
  transition: all 0.3s ease;
  border: 1px solid var(--el-border-color-light);
}

.class-card-list:hover {
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

/* 通用样式 */
.copy-btn {
  color: var(--el-text-color-regular);
}

.copy-btn:hover {
  color: var(--el-color-primary);
}

.more-btn {
  opacity: 0.6;
}

.more-btn:hover {
  opacity: 1;
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

/* 网格模式在移动端的优化 */
@media (max-width: 768px) {
  .class-title {
    font-size: 14px;
  }

  .class-desc {
    font-size: 12px;
  }

  .info-item {
    font-size: 12px;
  }
}
</style>
