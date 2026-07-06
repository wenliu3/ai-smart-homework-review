<template>
  <div style="height: 100%">
    <el-table
      :data="submissionData"
      :style="{ width: '100%', height: maxHeight }"
      border
      :max-height="maxHeight"
      stripe
    >
      <!-- 索引 -->
      <el-table-column type="index" label="序号" width="50" />
      <!-- 学生信息 -->
      <el-table-column label="学生信息" min-width="150">
        <template #default="{ row }">
          <div class="flex items-center">
            <el-avatar :size="32" class="mr-2">
              {{ row.studentName?.charAt(0) }}
            </el-avatar>
            <div>
              <div class="font-medium">{{ row.studentName }}</div>
              <div class="text-xs text-gray-500">{{ row.studentNumber }}</div>
            </div>
          </div>
        </template>
      </el-table-column>

      <!-- 班级 -->
      <el-table-column label="班级" prop="className" width="120" />

      <!-- 作业名称 -->
      <el-table-column
        label="作业名称"
        prop="assignmentTitle"
        min-width="200"
        show-overflow-tooltip
      />

      <!-- 提交状态 -->
      <el-table-column label="提交状态" width="100" align="center">
        <template #default="{ row }">
          <el-tag :type="getSubmissionStatusType(row.status)" size="small">
            {{ getSubmissionStatusText(row.status) }}
          </el-tag>
        </template>
      </el-table-column>

      <!-- 提交时间 -->
      <el-table-column label="提交时间" width="150">
        <template #default="{ row }">
          <div v-if="row.submittedAt" class="text-sm">
            {{ formatDateTime(row.submittedAt) }}
          </div>
          <span v-else class="text-gray-400">-</span>
        </template>
      </el-table-column>

      <!-- 批改状态 -->
      <el-table-column label="批改状态" width="100" align="center">
        <template #default="{ row }">
          <el-tag :type="getGradingStatusType(row.status)" size="small">
            {{ getGradingStatusText(row.status) }}
          </el-tag>
        </template>
      </el-table-column>

      <!-- 教师评分 -->
      <el-table-column label="教师评分" width="80" align="center">
        <template #default="{ row }">
          <div
            v-if="row.teacherScore !== null && row.teacherScore !== undefined"
          >
            <span class="font-medium">{{ row.teacherScore }}</span>
            <span class="text-gray-400 text-xs">分</span>
          </div>
          <span v-else class="text-gray-400">-</span>
        </template>
      </el-table-column>

      <!-- AI评分 -->
      <el-table-column label="AI评分" width="80" align="center">
        <template #default="{ row }">
          <div v-if="row.aiScore !== null && row.aiScore !== undefined">
            <span class="font-medium text-blue-600">{{ row.aiScore }}</span>
            <span class="text-gray-400 text-xs">分</span>
          </div>
          <span v-else class="text-gray-400">-</span>
        </template>
      </el-table-column>

      <!-- 批改时间 -->
      <el-table-column label="批改时间" width="150">
        <template #default="{ row }">
          <div v-if="row.teacherReviewedAt" class="text-sm">
            {{ formatDateTime(row.teacherReviewedAt) }}
          </div>
          <span v-else class="text-gray-400">-</span>
        </template>
      </el-table-column>

      <!-- 操作 -->
      <el-table-column label="操作" width="150" fixed="right">
        <template #default="{ row }">
          <div class="flex gap-2">
            <!-- 查看作业 -->
            <el-button
              link
              type="primary"
              size="small"
              @click="handleViewSubmission(row)"
            >
              查看详情
            </el-button>

            <!-- 批改作业 -->
            <el-button
              v-if="row.status === 'submitted' || row.status === 'ai_reviewed'"
              link
              type="success"
              size="small"
              @click="handleGradeSubmission(row)"
            >
              {{ row.status === "teacher_reviewed" ? "重新批改" : "批改" }}
            </el-button>
          </div>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script lang="ts" setup>
import { useRouter } from "vue-router";
import type { SubmissionRecord } from "@/api/correcting";

// Props
interface Props {
  submissionData: SubmissionRecord[];
  maxHeight?: string;
}

defineProps<Props>();

// Router
const router = useRouter();

// 查看作业提交详情 → 跳转到作业详情页
const handleViewSubmission = (row: SubmissionRecord) => {
  router.push({
    path: "/teacher/assignments/detail",
    query: { id: row.assignmentId },
  });
};

// 批改作业
const handleGradeSubmission = (row: SubmissionRecord) => {
  router.push({
    path: "/teacher/correcting/grading",
    query: {
      submissionId: row._id,
      assignmentId: row.assignmentId,
    },
  });
};

// 获取提交状态类型
const getSubmissionStatusType = (status: string) => {
  const types = {
    draft: "warning",
    submitted: "success",
    ai_reviewed: "primary",
    teacher_reviewed: "success",
  };
  return types[status] || "info";
};

// 获取提交状态文本
const getSubmissionStatusText = (status: string) => {
  const texts: Record<string, string> = {
    draft: "草稿",
    submitted: "已提交",
    ai_reviewed: "AI已评",
    teacher_reviewed: "已批改",
  };
  return texts[status] || "未知";
};

// 获取批改状态类型
const getGradingStatusType = (status: string) => {
  const types = {
    teacher_reviewed: "success",
    ai_reviewed: "primary",
    submitted: "warning",
    draft: "info",
  };
  return types[status] || "info";
};

// 获取批改状态文本
const getGradingStatusText = (status: string) => {
  const texts: Record<string, string> = {
    teacher_reviewed: "已批改",
    ai_reviewed: "AI已评",
    submitted: "待批改",
    draft: "草稿",
  };
  return texts[status] || "未知";
};

// 格式化日期时间
const formatDateTime = (dateStr: string) => {
  if (!dateStr) return "-";
  const date = new Date(dateStr);
  return date.toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
};
</script>

<style scoped>
/* 使用 Tailwind CSS 类名，如果项目没有配置 Tailwind，需要添加对应的 CSS */
</style>
