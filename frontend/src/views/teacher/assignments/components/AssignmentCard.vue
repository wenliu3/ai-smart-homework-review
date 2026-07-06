<template>
  <el-card class="assignment-card" shadow="hover" @click="handleCardClick">
    <!-- 卡片头部 -->
    <div class="card-header">
      <div class="header-content">
        <div class="title-section">
          <h3 class="assignment-title">{{ assignment.title }}</h3>
          <div class="status-badges">
            <el-tag
              :type="getStatusType(assignment.status)"
              size="small"
              effect="light"
            >
              {{ getStatusText(assignment.status) }}
            </el-tag>
            <el-tag
              v-if="assignment.isExpired"
              type="danger"
              size="small"
              effect="light"
            >
              已过期
            </el-tag>
          </div>
        </div>
        <div class="header-actions" @click.stop>
          <el-dropdown
            @command="handleCommand"
            trigger="click"
            placement="bottom-end"
          >
            <el-button link :icon="MoreFilled" class="action-btn" />
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="view" :icon="View"
                  >查看详情</el-dropdown-item
                >
                <el-dropdown-item command="edit" :icon="Edit"
                  >编辑作业</el-dropdown-item
                >
                <el-dropdown-item
                  v-if="assignment.status === AssignmentStatus.DRAFT"
                  command="publish"
                  :icon="VideoPlay"
                >
                  发布作业
                </el-dropdown-item>
                <el-dropdown-item
                  v-if="assignment.status === AssignmentStatus.PUBLISHED"
                  command="terminate"
                  :icon="VideoPause"
                >
                  终止作业
                </el-dropdown-item>
                <el-dropdown-item
                  v-if="assignment.status === AssignmentStatus.TERMINATED"
                  command="republish"
                  :icon="VideoPlay"
                >
                  重新发布
                </el-dropdown-item>
                <el-dropdown-item command="delete" :icon="Delete" divided
                  >删除作业</el-dropdown-item
                >
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </div>
    </div>

    <!-- 卡片内容 -->
    <div class="card-body-1">
      <!-- 创建人信息 -->
      <div class="info-row">
        <div class="info-label">
          <el-icon class="label-icon"><User /></el-icon>
          创建老师
        </div>
        <div class="teacher-info">
          <span class="teacher-name">{{
            assignment.teacherName || "未知"
          }}</span>
        </div>
      </div>

      <!-- 班级信息 -->
      <div class="info-row">
        <div class="info-label">
          <el-icon class="label-icon"><School /></el-icon>
          关联班级
        </div>
        <div class="class-tags">
          <el-tag
            v-for="cls in assignment.classes.slice(0, 2)"
            :key="cls.id"
            size="small"
            effect="plain"
            class="class-tag"
          >
            {{ cls.name }}
          </el-tag>
          <el-tag
            v-if="assignment.classes.length > 2"
            size="small"
            type="info"
            effect="plain"
          >
            +{{ assignment.classes.length - 2 }}
          </el-tag>
        </div>
      </div>

      <!-- 时间信息 -->
      <div class="info-row">
        <div class="info-label">
          <el-icon class="label-icon"><Clock /></el-icon>
          时间安排
        </div>
        <div class="time-range">
          <span class="time-text">{{
            formatDateRange(assignment.startDate, assignment.endDate)
          }}</span>
        </div>
      </div>

      <!-- 提交统计 -->
      <div class="stats-section">
        <div class="stats-header">
          <span class="stats-label">提交进度</span>
          <span class="stats-number"
            >{{ assignment.submissionCount }}/{{
              assignment.totalStudents
            }}</span
          >
        </div>
        <div class="progress-wrapper">
          <el-progress
            :percentage="getSubmissionPercentage(assignment)"
            :stroke-width="8"
            :show-text="false"
            :color="getProgressColor(assignment)"
          />
        </div>
      </div>
    </div>

    <!-- 卡片底部操作 -->
    <div class="card-footer">
      <el-button size="small" @click.stop="handleView" :icon="View">
        查看详情
      </el-button>
      <el-button
        size="small"
        type="primary"
        @click.stop="handleEdit"
        :icon="Edit"
      >
        编辑
      </el-button>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import {
  MoreFilled,
  View,
  Edit,
  Delete,
  Clock,
  VideoPlay,
  VideoPause,
  School,
  User,
} from "@element-plus/icons-vue";
import { AssignmentStatus } from "@/api/assignments";
import type { AssignmentListItem } from "@/types/assignments";
import moment from "moment";

interface Props {
  assignment: AssignmentListItem;
}

interface Emits {
  (e: "view", assignment: AssignmentListItem): void;
  (e: "edit", assignment: AssignmentListItem): void;
  (e: "delete", assignment: AssignmentListItem): void;
  (e: "publish", assignment: AssignmentListItem): void;
  (e: "terminate", assignment: AssignmentListItem): void;
  (e: "republish", assignment: AssignmentListItem): void;
}

const props = defineProps<Props>();
const emit = defineEmits<Emits>();

// 获取状态类型
const getStatusType = (status: AssignmentStatus) => {
  switch (status) {
    case AssignmentStatus.DRAFT:
      return "info";
    case AssignmentStatus.PUBLISHED:
      return "success";
    case AssignmentStatus.TERMINATED:
      return "warning";
    default:
      return "info";
  }
};

// 获取状态文本
const getStatusText = (status: AssignmentStatus) => {
  switch (status) {
    case AssignmentStatus.DRAFT:
      return "草稿";
    case AssignmentStatus.PUBLISHED:
      return "已发布";
    case AssignmentStatus.TERMINATED:
      return "已终止";
    default:
      return "未知";
  }
};

// 计算提交百分比
const getSubmissionPercentage = (assignment: AssignmentListItem) => {
  if (assignment.totalStudents === 0) return 0;
  return Math.round(
    (assignment.submissionCount / assignment.totalStudents) * 100
  );
};

// 获取进度条颜色
const getProgressColor = (assignment: AssignmentListItem) => {
  const percentage = getSubmissionPercentage(assignment);
  if (percentage >= 80) return "#67c23a";
  if (percentage >= 50) return "#e6a23c";
  return "#f56c6c";
};

// 格式化时间范围
const formatDateRange = (startDate: string, endDate: string) => {
  const start = moment(startDate);
  const end = moment(endDate);

  // 格式化为：2024/05/25 14:42 ~ 2024/06/01 13:42
  const formatDate = (date: any) => {
    return date.format("YYYY/MM/DD HH:mm");
  };

  return `${formatDate(start)} ~ ${formatDate(end)}`;
};

// 处理卡片点击
const handleCardClick = () => {
  emit("view", props.assignment);
};

// 处理查看
const handleView = () => {
  emit("view", props.assignment);
};

// 处理编辑
const handleEdit = () => {
  emit("edit", props.assignment);
};

// 处理下拉菜单命令
const handleCommand = (command: string) => {
  switch (command) {
    case "view":
      emit("view", props.assignment);
      break;
    case "edit":
      emit("edit", props.assignment);
      break;
    case "delete":
      emit("delete", props.assignment);
      break;
    case "publish":
      emit("publish", props.assignment);
      break;
    case "terminate":
      emit("terminate", props.assignment);
      break;
    case "republish":
      emit("republish", props.assignment);
      break;
  }
};

// 添加默认导出
defineOptions({
  name: "AssignmentCard",
});
</script>

<script lang="ts">
// 添加默认导出以支持常规导入
import { defineComponent } from "vue";

export default defineComponent({
  name: "AssignmentCard",
});
</script>

<style scoped>
.assignment-card {
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  height: 100%;
  border: 1px solid #e4e7ed;
  border-radius: 12px;
  overflow: hidden;
  background: #fff;
  position: relative;
}

.assignment-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.12);
  border-color: #409eff;
}

.card-header {
  padding: 16px 16px 12px 16px;
  border-bottom: 1px solid #f0f2f5;
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 8px;
}

.title-section {
  flex: 1;
  min-width: 0;
}

.assignment-title {
  font-size: 16px;
  font-weight: 600;
  color: #1f2937;
  margin: 0 0 6px 0;
  line-height: 1.3;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  transition: color 0.2s ease;
}

.assignment-card:hover .assignment-title {
  color: #409eff;
}

.status-badges {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.header-actions {
  flex-shrink: 0;
}

.action-btn {
  color: #6b7280;
  transition: all 0.2s ease;
  padding: 8px;
  border-radius: 6px;
}

.action-btn:hover {
  color: #409eff;
  background-color: #f0f9ff;
}

.card-body {
  padding: 16px;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.card-body-1 {
  padding-top: 12px;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.info-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}

.info-label {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  font-weight: 500;
  color: #6b7280;
  min-width: 70px;
  flex-shrink: 0;
}

.label-icon {
  font-size: 16px;
  color: #9ca3af;
}

.class-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  flex: 1;
}

.class-tag {
  border-radius: 6px;
  font-weight: 500;
}

.teacher-info {
  flex: 1;
}

.teacher-name {
  font-size: 13px;
  color: #667eea;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  display: inline-block;
}

.time-range {
  flex: 1;
}

.time-text {
  font-size: 12px;
  color: #374151;
  font-weight: 500;
  font-family: "SF Mono", "Monaco", "Inconsolata", "Roboto Mono", monospace;
}

.stats-section {
  background: #f8fafc;
  border-radius: 6px;
  padding: 12px;
  border: 1px solid #e2e8f0;
}

.stats-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.stats-label {
  font-size: 14px;
  font-weight: 500;
  color: #6b7280;
}

.stats-number {
  font-size: 16px;
  font-weight: 600;
  color: #1f2937;
}

.progress-wrapper {
  margin-top: 6px;
}

.card-footer {
  padding: 10px 16px;
  border-top: 1px solid #f0f2f5;
  background: transparent;
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}

.card-footer .el-button {
  border-radius: 6px;
  font-weight: 500;
  transition: all 0.2s ease;
}

.card-footer .el-button:hover {
  transform: translateY(-1px);
}

/* 状态标签样式优化 */
:deep(.el-tag) {
  border-radius: 6px;
  font-weight: 500;
  border: none;
}

:deep(.el-tag--info) {
  background-color: #f0f9ff;
  color: #0369a1;
}

:deep(.el-tag--success) {
  background-color: #f0fdf4;
  color: #166534;
}

:deep(.el-tag--warning) {
  background-color: #fffbeb;
  color: #d97706;
}

:deep(.el-tag--danger) {
  background-color: #fef2f2;
  color: #dc2626;
}

/* 进度条样式优化 */
:deep(.el-progress-bar__outer) {
  border-radius: 6px;
  background-color: #e5e7eb;
}

:deep(.el-progress-bar__inner) {
  border-radius: 6px;
  transition: all 0.3s ease;
}

/* 下拉菜单样式优化 */
:deep(.el-dropdown-menu) {
  border-radius: 8px;
  box-shadow: 0 10px 25px rgba(0, 0, 0, 0.1);
  border: 1px solid #e5e7eb;
}

:deep(.el-dropdown-menu__item) {
  padding: 10px 16px;
  font-size: 14px;
  transition: all 0.2s ease;
}

:deep(.el-dropdown-menu__item:hover) {
  background-color: #f8fafc;
  color: #409eff;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .card-header {
    padding: 14px;
  }

  .card-body {
    padding: 14px;
    gap: 10px;
  }

  .card-footer {
    padding: 8px 14px;
  }

  .assignment-title {
    font-size: 15px;
  }

  .info-row {
    flex-direction: column;
    gap: 6px;
  }

  .info-label {
    min-width: auto;
    font-size: 12px;
  }

  .stats-section {
    padding: 10px;
  }
}

/* 加载状态动画 */
@keyframes shimmer {
  0% {
    background-position: -200px 0;
  }
  100% {
    background-position: calc(200px + 100%) 0;
  }
}

.assignment-card.loading {
  background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
  background-size: 200px 100%;
  animation: shimmer 1.5s infinite;
}
</style>
