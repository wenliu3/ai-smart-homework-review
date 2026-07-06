<template>
  <div class="assignment-detail">
    <div class="detail-header">
      <div class="header-content">
        <h2 class="assignment-title">{{ assignment.title }}</h2>
        <div class="header-meta">
          <el-tag :type="getStatusType(assignment.status)" size="large">
            {{ getStatusText(assignment.status) }}
          </el-tag>
          <el-tag
            v-if="assignment.isExpired"
            type="danger"
            size="large"
            class="ml-2"
          >
            已过期
          </el-tag>
        </div>
      </div>
      <div class="header-actions">
        <el-button type="primary" @click="handleEdit" :icon="Edit">
          编辑作业
        </el-button>
        <el-button @click="handleClose" :icon="Close"> 关闭 </el-button>
      </div>
    </div>

    <div class="detail-content">
      <!-- 基本信息 -->
      <el-card class="info-card" shadow="never">
        <template #header>
          <div class="card-header">
            <span class="card-title">基本信息</span>
          </div>
        </template>

        <div class="info-grid">
          <div class="info-item">
            <label class="info-label">作业标题：</label>
            <span class="info-value">{{ assignment.title }}</span>
          </div>

          <div class="info-item">
            <label class="info-label">创建教师：</label>
            <span class="info-value">{{ assignment.teacherName }}</span>
          </div>

          <div class="info-item">
            <label class="info-label">AI规则：</label>
            <span class="info-value">{{ assignment.aiRuleName }}</span>
          </div>

          <div class="info-item">
            <label class="info-label">允许附件：</label>
            <el-tag
              :type="assignment.allowAttachments ? 'success' : 'info'"
              size="small"
            >
              {{ assignment.allowAttachments ? "是" : "否" }}
            </el-tag>
          </div>

          <div class="info-item">
            <label class="info-label">开始时间：</label>
            <span class="info-value">{{
              formatDateTime(assignment.startDate)
            }}</span>
          </div>

          <div class="info-item">
            <label class="info-label">截止时间：</label>
            <span
              class="info-value"
              :class="{ 'text-danger': assignment.isExpired }"
            >
              {{ formatDateTime(assignment.endDate) }}
            </span>
          </div>

          <div class="info-item">
            <label class="info-label">创建时间：</label>
            <span class="info-value">{{
              formatDateTime(assignment.createdAt)
            }}</span>
          </div>

          <div class="info-item">
            <label class="info-label">更新时间：</label>
            <span class="info-value">{{
              formatDateTime(assignment.updatedAt)
            }}</span>
          </div>
        </div>
      </el-card>

      <!-- 关联班级 -->
      <el-card class="info-card" shadow="never">
        <template #header>
          <div class="card-header">
            <span class="card-title">关联班级</span>
            <span class="class-count"
              >共 {{ assignment.classes.length }} 个班级</span
            >
          </div>
        </template>

        <div class="class-list">
          <el-tag
            v-for="cls in assignment.classes"
            :key="cls.id"
            size="default"
            class="class-tag"
          >
            {{ cls.name }}
          </el-tag>
        </div>
      </el-card>

      <!-- 提交统计 -->
      <el-card class="info-card" shadow="never">
        <template #header>
          <div class="card-header">
            <span class="card-title">提交统计</span>
          </div>
        </template>

        <div class="stats-grid">
          <div class="stat-item">
            <div class="stat-number">
              {{ assignment.submissionStats.total }}
            </div>
            <div class="stat-label">总学生数</div>
          </div>
          <div class="stat-item">
            <div class="stat-number submitted">
              {{ assignment.submissionStats.submitted }}
            </div>
            <div class="stat-label">已提交</div>
          </div>
          <div class="stat-item">
            <div class="stat-number ai-reviewed">
              {{ assignment.submissionStats.aiReviewed }}
            </div>
            <div class="stat-label">AI已批改</div>
          </div>
          <div class="stat-item">
            <div class="stat-number teacher-reviewed">
              {{ assignment.submissionStats.teacherReviewed }}
            </div>
            <div class="stat-label">教师已批改</div>
          </div>
        </div>

        <div class="progress-section">
          <div class="progress-item">
            <div class="progress-header">
              <span>提交进度</span>
              <span
                >{{
                  getSubmissionPercentage(assignment.submissionStats)
                }}%</span
              >
            </div>
            <el-progress
              :percentage="getSubmissionPercentage(assignment.submissionStats)"
              :stroke-width="8"
              color="#67c23a"
            />
          </div>

          <div class="progress-item">
            <div class="progress-header">
              <span>AI批改进度</span>
              <span
                >{{ getAiReviewPercentage(assignment.submissionStats) }}%</span
              >
            </div>
            <el-progress
              :percentage="getAiReviewPercentage(assignment.submissionStats)"
              :stroke-width="8"
              color="#409eff"
            />
          </div>

          <div class="progress-item">
            <div class="progress-header">
              <span>教师批改进度</span>
              <span
                >{{
                  getTeacherReviewPercentage(assignment.submissionStats)
                }}%</span
              >
            </div>
            <el-progress
              :percentage="
                getTeacherReviewPercentage(assignment.submissionStats)
              "
              :stroke-width="8"
              color="#e6a23c"
            />
          </div>
        </div>
      </el-card>

      <!-- 作业描述 -->
      <el-card class="info-card" shadow="never">
        <template #header>
          <div class="card-header">
            <span class="card-title">作业描述</span>
          </div>
        </template>
        git
        <div
          class="description-content editor-content-view"
          v-html="assignment.description"
        ></div>
      </el-card>

      <!-- 终止原因（如果有） -->
      <el-card
        v-if="
          assignment.status === AssignmentStatus.TERMINATED &&
          assignment.terminatedReason
        "
        class="info-card"
        shadow="never"
      >
        <template #header>
          <div class="card-header">
            <span class="card-title">终止原因</span>
          </div>
        </template>

        <div class="terminated-reason">
          {{ assignment.terminatedReason }}
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Edit, Close } from "@element-plus/icons-vue";
import { AssignmentStatus } from "@/api/assignments";
import type { Assignment } from "@/types/assignments";

interface Props {
  assignment: Assignment;
}

interface Emits {
  (e: "edit"): void;
  (e: "close"): void;
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

// 格式化日期时间
const formatDateTime = (dateString: string) => {
  const date = new Date(dateString);
  return date.toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
};

// 计算提交百分比
const getSubmissionPercentage = (stats: Assignment["submissionStats"]) => {
  if (stats.total === 0) return 0;
  return Math.round((stats.submitted / stats.total) * 100);
};

// 计算AI批改百分比
const getAiReviewPercentage = (stats: Assignment["submissionStats"]) => {
  if (stats.submitted === 0) return 0;
  return Math.round((stats.aiReviewed / stats.submitted) * 100);
};

// 计算教师批改百分比
const getTeacherReviewPercentage = (stats: Assignment["submissionStats"]) => {
  if (stats.submitted === 0) return 0;
  return Math.round((stats.teacherReviewed / stats.submitted) * 100);
};

// 编辑作业
const handleEdit = () => {
  emit("edit");
};

// 关闭详情
const handleClose = () => {
  emit("close");
};

// 添加默认导出
defineOptions({
  name: "AssignmentDetail",
});
</script>

<script lang="ts">
// 添加默认导出以支持常规导入
import { defineComponent } from "vue";

export default defineComponent({
  name: "AssignmentDetail",
});
</script>

<style scoped>
.assignment-detail {
  padding: 20px;
  max-height: calc(100vh - 120px);
  overflow-y: auto;
}

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 24px;
  padding-bottom: 16px;
  border-bottom: 1px solid #ebeef5;
}

.header-content {
  flex: 1;
}

.assignment-title {
  margin: 0 0 12px 0;
  font-size: 24px;
  font-weight: 600;
  color: #303133;
  line-height: 1.4;
}

.header-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

.header-actions {
  flex-shrink: 0;
  display: flex;
  gap: 12px;
}

.detail-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.info-card {
  border: 1px solid #ebeef5;
  border-radius: 8px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.class-count {
  font-size: 14px;
  color: #909399;
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 16px;
}

.info-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.info-label {
  font-weight: 500;
  color: #606266;
  min-width: 80px;
  flex-shrink: 0;
}

.info-value {
  color: #303133;
  flex: 1;
}

.text-danger {
  color: #f56c6c;
}

.class-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.class-tag {
  margin: 0;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 20px;
  margin-bottom: 24px;
}

.stat-item {
  text-align: center;
  padding: 16px;
  background: #f8f9fa;
  border-radius: 8px;
}

.stat-number {
  font-size: 28px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 4px;
}

.stat-number.submitted {
  color: #67c23a;
}

.stat-number.ai-reviewed {
  color: #409eff;
}

.stat-number.teacher-reviewed {
  color: #e6a23c;
}

.stat-label {
  font-size: 14px;
  color: #909399;
}

.progress-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.progress-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 14px;
  color: #606266;
}

.description-content {
  /* line-height: 1.6; */
  color: #303133;
}

.description-content :deep(img) {
  max-width: 100%;
  height: auto;
}

.description-content :deep(pre) {
  background: #f5f5f5;
  padding: 12px;
  border-radius: 4px;
  overflow-x: auto;
}

.terminated-reason {
  padding: 16px;
  background: #fef0f0;
  border: 1px solid #fbc4c4;
  border-radius: 4px;
  color: #f56c6c;
  line-height: 1.6;
}

.ml-2 {
  margin-left: 8px;
}
</style>
