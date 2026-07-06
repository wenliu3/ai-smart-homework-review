<template>
  <div class="assignment-header">
    <div class="header-main">
      <div class="header-info">
        <div class="title-row">
          <h1 class="assignment-title">{{ assignmentDetail?.title }}</h1>
          <el-tag
            :type="getStatusType(assignmentDetail?.status)"
            size="large"
            class="status-tag"
          >
            {{ getStatusText(assignmentDetail?.status) }}
          </el-tag>
        </div>

        <div class="meta-info">
          <div class="meta-item">
            <el-icon class="meta-icon"><Calendar /></el-icon>
            <span class="meta-label">开始时间：</span>
            <span class="meta-value">{{
              formatDateTime(assignmentDetail?.startDate)
            }}</span>
          </div>

          <div class="meta-item">
            <el-icon class="meta-icon"><Timer /></el-icon>
            <span class="meta-label">截止时间：</span>
            <span class="meta-value" :class="{ expired: isExpired }">
              {{ formatDateTime(assignmentDetail?.endDate) }}
            </span>
            <el-tag
              v-if="isExpired"
              type="danger"
              size="small"
              class="expired-tag"
            >
              已过期
            </el-tag>
            <el-tag
              v-else-if="isNearDeadline"
              type="warning"
              size="small"
              class="warning-tag"
            >
              即将到期
            </el-tag>
          </div>
        </div>
      </div>

      <div class="header-actions">
        <el-button @click="goBack" :icon="ArrowLeft" size="large">
          返回列表
        </el-button>

        <el-dropdown v-if="canOperate" trigger="click">
          <el-button type="primary" size="large">
            操作 <el-icon class="el-icon--right"><ArrowDown /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item
                v-if="assignmentDetail?.status === 'draft'"
                @click="handlePublish"
              >
                <el-icon><Upload /></el-icon>
                发布作业
              </el-dropdown-item>
              <el-dropdown-item
                v-if="assignmentDetail?.status === 'published'"
                @click="handleTerminate"
              >
                <el-icon><CircleClose /></el-icon>
                终止作业
              </el-dropdown-item>
              <el-dropdown-item @click="handleEdit">
                <el-icon><Edit /></el-icon>
                编辑作业
              </el-dropdown-item>
              <el-dropdown-item divided @click="handleExport">
                <el-icon><Download /></el-icon>
                导出数据
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import {
  ArrowLeft,
  Calendar,
  Timer,
  ArrowDown,
  Upload,
  CircleClose,
  Edit,
  Download,
} from "@element-plus/icons-vue";
import moment from "moment";
import type { AssignmentDetail, AssignmentStatus } from "@/api/assignments";

interface Props {
  assignmentDetail: AssignmentDetail | null;
}

interface Emits {
  (e: "goBack"): void;
  (e: "publish"): void;
  (e: "terminate"): void;
  (e: "edit"): void;
  (e: "export"): void;
}

const props = defineProps<Props>();
const emit = defineEmits<Emits>();

// 格式化日期时间
const formatDateTime = (dateTime?: string) => {
  if (!dateTime) return "-";
  return moment(dateTime).format("YYYY年MM月DD日 HH:mm");
};

// 获取状态类型
const getStatusType = (status?: string) => {
  switch (status) {
    case "draft":
      return "info";
    case "published":
      return "success";
    case "terminated":
      return "warning";
    default:
      return "info";
  }
};

// 获取状态文本
const getStatusText = (status?: string) => {
  switch (status) {
    case "draft":
      return "草稿";
    case "published":
      return "已发布";
    case "terminated":
      return "已终止";
    default:
      return "未知";
  }
};

// 是否过期
const isExpired = computed(() => {
  if (!props.assignmentDetail?.endDate) return false;
  return moment().isAfter(moment(props.assignmentDetail.endDate));
});

// 是否即将到期（24小时内）
const isNearDeadline = computed(() => {
  if (!props.assignmentDetail?.endDate || isExpired.value) return false;
  const now = moment();
  const endTime = moment(props.assignmentDetail.endDate);
  return endTime.diff(now, "hours") <= 24;
});

// 是否可以操作
const canOperate = computed(() => {
  return props.assignmentDetail?.status !== "terminated";
});

// 事件处理
const goBack = () => emit("goBack");
const handlePublish = () => emit("publish");
const handleTerminate = () => emit("terminate");
const handleEdit = () => emit("edit");
const handleExport = () => emit("export");

defineOptions({
  name: "AssignmentHeader",
});
</script>

<style scoped>
.assignment-header {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border-radius: 12px;
  padding: 20px 24px;
  margin-bottom: 16px;
  position: relative;
  overflow: hidden;
}

.assignment-header::before {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><defs><pattern id="grain" width="100" height="100" patternUnits="userSpaceOnUse"><circle cx="25" cy="25" r="1" fill="white" opacity="0.1"/><circle cx="75" cy="75" r="1" fill="white" opacity="0.1"/></pattern></defs><rect width="100" height="100" fill="url(%23grain)"/></svg>');
  opacity: 0.1;
}

.header-main {
  position: relative;
  z-index: 1;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 24px;
}

.header-info {
  flex: 1;
  min-width: 0;
}

.title-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.assignment-title {
  font-size: 24px;
  font-weight: 700;
  margin: 0;
  line-height: 1.2;
  flex: 1;
  min-width: 0;
}

.status-tag {
  flex-shrink: 0;
  font-weight: 600;
  border: 2px solid rgba(255, 255, 255, 0.3);
}

.meta-info {
  display: flex;
  flex-wrap: wrap;
  gap: 24px;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
}

.meta-icon {
  font-size: 16px;
  opacity: 0.9;
}

.meta-label {
  font-weight: 500;
  opacity: 0.9;
}

.meta-value {
  font-weight: 600;
}

.meta-value.highlight {
  color: #fbbf24;
  font-size: 16px;
}

.meta-value.expired {
  color: #fca5a5;
}

.class-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.class-tag {
  background: rgba(255, 255, 255, 0.2);
  color: white;
  border: 1px solid rgba(255, 255, 255, 0.3);
}

.expired-tag,
.warning-tag {
  margin-left: 8px;
}

.header-actions {
  display: flex;
  flex-direction: row;
  align-items: flex-start;
  gap: 12px;
  flex-shrink: 0;
}

.header-actions .el-button {
  border: 2px solid rgba(255, 255, 255, 0.3);
  background: rgba(255, 255, 255, 0.1);
  color: white;
  backdrop-filter: blur(10px);
  font-weight: 600;
}

.header-actions .el-button:hover {
  background: rgba(255, 255, 255, 0.2);
  border-color: rgba(255, 255, 255, 0.5);
}

.header-actions .el-button--primary {
  background: rgba(255, 255, 255, 0.2);
  border-color: rgba(255, 255, 255, 0.4);
}

.header-actions .el-button--primary:hover {
  background: rgba(255, 255, 255, 0.3);
}

/* 响应式设计 */
@media (max-width: 768px) {
  .assignment-header {
    padding: 24px 20px;
  }

  .header-main {
    flex-direction: column;
    gap: 24px;
  }

  .assignment-title {
    font-size: 24px;
  }

  .meta-info {
    grid-template-columns: 1fr;
    gap: 12px;
  }

  .header-actions {
    flex-direction: column;
    align-self: stretch;
  }

  .header-actions .el-button {
    flex: 1;
  }
}
</style>
