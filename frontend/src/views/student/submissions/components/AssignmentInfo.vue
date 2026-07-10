<template>
  <div class="assignment-info-card">
    <div class="card-header">
      <span class="card-title">
        <el-icon :size="18"><Document /></el-icon>
        作业详情
      </span>
    </div>
    <div class="card-body">
      <div class="space-y-4">
        <div>
          <div
            ref="descriptionRef"
            class="prose max-w-none text-gray-700 description-content"
            v-html="assignment.description"
          ></div>
        </div>

        <div class="info-bar">
          <div class="flex items-center gap-2">
            <el-icon><User /></el-icon>
            <span>教师：{{ assignment.teacherName }}</span>
          </div>
          <div class="flex items-center gap-2">
            <el-icon><Clock /></el-icon>
            <span>截止时间：{{ formatDate(assignment.dueDate) }}</span>
          </div>
          <div class="flex items-center gap-2">
            <el-icon><Star /></el-icon>
            <span>满分：{{ assignment.maxScore }}分</span>
          </div>
          <div
            v-if="isOverdue"
            class="flex items-center gap-2 text-red-600 font-medium"
          >
            <el-icon><Warning /></el-icon>
            <span>已过期</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import {
  Clock,
  Star,
  Warning,
  User,
  Document,
} from "@element-plus/icons-vue";
import type { Assignment, Submission } from "../../../../api/submissions";
import { useSubmissionUtils } from "../composables";

interface Props {
  assignment: Assignment;
  submission?: Submission | null;
  statusTagType: "success" | "warning" | "info" | "primary" | "danger";
  statusText: string;
  isOverdue: boolean;
}

const props = defineProps<Props>();

const { formatDate } = useSubmissionUtils();

const descriptionRef = ref();

defineOptions({
  name: "AssignmentInfo",
});
</script>

<style scoped>
.assignment-info-card {
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}

.card-header {
  padding: 0.875rem 1.25rem;
  background: #f9fafb;
  border-bottom: 1px solid #f0f0f0;
}

.card-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 14px;
  font-weight: 600;
  color: #1f2937;
}

.card-body {
  padding: 1.25rem;
}

.info-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 1.5rem;
  padding-top: 1rem;
  border-top: 1px solid #f0f0f0;
  font-size: 13px;
  color: #6b7280;
}

.description-content {
  line-height: 1.8;
}

.description-content :deep(img) {
  max-width: 100%;
  border-radius: 6px;
}

.prose {
  max-width: none;
}
</style>
