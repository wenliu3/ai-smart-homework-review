<template>
  <div class="assignment-detail-container">
    <div v-loading="loading" class="bg-white rounded-lg shadow-sm">
      <!-- 作业标题区域 -->
      <div class="border-b border-gray-200 px-6 py-4">
        <div class="flex items-start justify-between">
          <div class="flex-1">
            <h1 class="text-2xl font-bold text-gray-900 mb-2">
              {{ assignment?.title }}
            </h1>
            <div class="flex items-center space-x-4 text-sm text-gray-500">
              <span>{{ assignment?.subject }}</span>
              <span>总分：{{ assignment?.totalPoints }}分</span>
              <span>截止时间：{{ formatDate(assignment?.deadline) }}</span>
            </div>
          </div>
          <el-tag :type="getStatusType(assignment?.status)" size="large">
            {{ getStatusText(assignment?.status) }}
          </el-tag>
        </div>
      </div>

      <!-- 作业内容 -->
      <div class="p-6">
        <div class="prose max-w-none">
          <h3 class="text-lg font-medium text-gray-900 mb-3">作业要求</h3>
          <div class="text-gray-700 whitespace-pre-wrap">
            {{ assignment?.description }}
          </div>
        </div>

        <!-- 附件列表 -->
        <div v-if="assignment?.attachments?.length" class="mt-6">
          <h3 class="text-lg font-medium text-gray-900 mb-3">作业附件</h3>
          <div class="space-y-2">
            <div
              v-for="attachment in assignment.attachments"
              :key="attachment.url"
              class="flex items-center p-3 bg-gray-50 rounded-lg"
            >
              <el-icon class="text-blue-500 mr-2"><Document /></el-icon>
              <span class="flex-1">{{ attachment.name }}</span>
              <el-button
                type="primary"
                size="small"
                @click="downloadFile(attachment)"
              >
                下载
              </el-button>
            </div>
          </div>
        </div>

        <!-- 提交状态信息 -->
        <div class="mt-6 p-4 bg-gray-50 rounded-lg">
          <h3 class="text-lg font-medium text-gray-900 mb-3">提交状态</h3>
          <div class="grid grid-cols-1 md:grid-cols-4 gap-4 text-sm">
            <div>
              <span class="text-gray-500">提交状态：</span>
              <el-tag :type="getSubmissionStatusType()" size="small">
                {{ getSubmissionStatusText() }}
              </el-tag>
            </div>
            <div v-if="assignment?.hasSubmitted">
              <span class="text-gray-500">批改状态：</span>
              <el-tag :type="getReviewStatusType()" size="small">
                {{ getReviewStatusText() }}
              </el-tag>
            </div>
            <div>
              <span class="text-gray-500">作业状态：</span>
              <el-tag
                :type="assignment?.isExpired ? 'danger' : 'success'"
                size="small"
              >
                {{ assignment?.isExpired ? "已过期" : "进行中" }}
              </el-tag>
            </div>
            <div v-if="assignment?.terminatedReason">
              <span class="text-gray-500">终止原因：</span>
              <span class="text-red-600">{{
                assignment.terminatedReason
              }}</span>
            </div>
          </div>
        </div>

        <!-- 操作按钮 -->
        <div class="mt-6 flex justify-end space-x-3">
          <el-button @click="goBack">返回</el-button>
          <el-button
            v-if="assignment?.hasSubmitted || assignment?.hasDraft"
            type="primary"
            @click="viewSubmission"
          >
            {{ assignment?.hasSubmitted ? "查看提交" : "继续编辑" }}
          </el-button>
          <el-button
            v-else-if="
              !assignment?.isExpired && assignment?.status !== 'terminated'
            "
            type="primary"
            @click="startSubmission"
          >
            开始作业
          </el-button>
          <el-tag v-else-if="assignment?.isExpired" type="danger" size="large">
            作业已过期
          </el-tag>
          <el-tag
            v-else-if="assignment?.status === 'terminated'"
            type="warning"
            size="large"
          >
            作业已终止
          </el-tag>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { Document } from "@element-plus/icons-vue";
import { getStudentAssignment } from "../../../api/assignments";

const route = useRoute();
const router = useRouter();

const loading = ref(false);
const assignment = ref(null);

// 加载作业详情
const loadAssignment = async () => {
  loading.value = true;
  try {
    const assignmentId = route.params.id as string;
    const classId = route.query.classId as string;
    assignment.value = await getStudentAssignment(assignmentId, classId);
  } catch (error) {
    console.error("加载作业详情失败:", error);
    ElMessage.error("加载作业详情失败");
  } finally {
    loading.value = false;
  }
};

// 格式化日期
const formatDate = (date) => {
  if (!date) return "-";
  return new Date(date).toLocaleString("zh-CN");
};

// 获取状态类型
const getStatusType = (status) => {
  const statusMap = {
    pending: "warning",
    in_progress: "primary",
    completed: "success",
    overdue: "danger",
  };
  return statusMap[status] || "info";
};

// 获取状态文本
const getStatusText = (status) => {
  const statusMap = {
    pending: "待完成",
    in_progress: "进行中",
    completed: "已完成",
    overdue: "已逾期",
  };
  return statusMap[status] || "未知";
};

// 获取提交状态类型
const getSubmissionStatusType = () => {
  if (!assignment.value) return "info";
  if (assignment.value.hasDraft && !assignment.value.hasSubmitted)
    return "warning";
  if (assignment.value.hasSubmitted) return "success";
  if (assignment.value.isExpired) return "danger";
  return "info";
};

// 获取提交状态文本
const getSubmissionStatusText = () => {
  if (!assignment.value) return "未知";
  if (assignment.value.hasDraft && !assignment.value.hasSubmitted)
    return "草稿";
  if (assignment.value.hasSubmitted) return "已提交";
  if (assignment.value.isExpired) return "未提交";
  return "待提交";
};

// 获取批改状态类型
const getReviewStatusType = () => {
  if (!assignment.value?.submissionStatus) return "info";
  switch (assignment.value.submissionStatus) {
    case "teacher_reviewed":
      return "success";
    case "ai_reviewed":
      return "warning";
    case "submitted":
      return "info";
    default:
      return "info";
  }
};

// 获取批改状态文本
const getReviewStatusText = () => {
  if (!assignment.value?.submissionStatus) return "待批改";
  switch (assignment.value.submissionStatus) {
    case "teacher_reviewed":
      return "已批改";
    case "ai_reviewed":
      return "AI已评";
    case "submitted":
      return "待批改";
    default:
      return "待批改";
  }
};

// 下载附件
const downloadFile = (attachment) => {
  window.open(attachment.url, "_blank");
};

// 返回
const goBack = () => {
  router.back();
};

// 开始作业
const startSubmission = () => {
  // 跳转到提交页面
  router.push({
    path: "/student/submissions",
    query: {
      assignmentId: route.params.id,
      classId: route.query.classId || "", // 从路由查询参数中获取classId
    },
  });
};

// 查看提交
const viewSubmission = () => {
  // 跳转到提交页面
  router.push({
    path: "/student/submissions",
    query: {
      assignmentId: route.params.id,
      classId: route.query.classId || "", // 从路由查询参数中获取classId
    },
  });
};

onMounted(() => {
  loadAssignment();
});
</script>

<style scoped>
.assignment-detail-container {
  max-width: 800px;
  margin: 0 auto;
  padding: 20px;
}

.prose {
  line-height: 1.6;
}
</style>
