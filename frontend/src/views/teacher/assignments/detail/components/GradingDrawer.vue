<template>
  <el-drawer
    v-model="visible"
    title="批改作业"
    direction="rtl"
    size="60%"
    :before-close="handleClose"
    class="grading-drawer"
  >
    <div v-if="loading" class="loading-container">
      <el-skeleton :rows="8" animated />
    </div>

    <div v-else-if="submissionData" class="drawer-content">
      <!-- 学生信息头部 -->
      <div class="student-header">
        <div class="student-info">
          <el-avatar :size="50" class="student-avatar">
            {{ submissionData.studentName?.charAt(0) || "?" }}
          </el-avatar>
          <div class="student-details">
            <h3 class="student-name">
              {{ submissionData.studentName || "未知学生" }}
            </h3>
            <p class="student-meta">
              <span class="student-number"
                >学号：{{ submissionData.studentNumber || "无" }}</span
              >
              <span class="student-class"
                >班级：{{ submissionData.className || "无" }}</span
              >
            </p>
          </div>
        </div>
        <div class="submission-meta">
          <el-tag
            :type="getSubmissionStatusType(submissionData.status)"
            size="large"
            effect="light"
          >
            {{ getSubmissionStatusText(submissionData.status) }}
          </el-tag>
          <p v-if="submissionData.submittedAt" class="submit-time">
            提交时间：{{ formatDateTime(submissionData.submittedAt) }}
          </p>
        </div>
      </div>

      <!-- 折叠面板 -->
      <el-collapse v-model="activeCollapse" class="grading-collapse">
        <!-- 作业要求 -->
        <el-collapse-item name="assignment" class="assignment-section">
          <template #title>
            <div class="collapse-title">
              <div class="collapse-title-left">
                <el-icon><Document /></el-icon>
                <span>作业要求</span>
              </div>
            </div>
          </template>
          <div class="collapse-content">
            <div
              class="assignment-content"
              v-html="assignmentData?.content || '暂无作业要求'"
            ></div>
            <div class="assignment-meta">
              <span class="deadline"
                >截止时间：{{ formatDateTime(assignmentData?.endDate) }}</span
              >
              <span class="word-limit" v-if="assignmentData?.wordLimit">
                词数要求：{{ assignmentData.wordLimit }}词
              </span>
            </div>
          </div>
        </el-collapse-item>

        <!-- 学生提交内容 -->
        <el-collapse-item name="submission" class="submission-section">
          <template #title>
            <div class="collapse-title">
              <div class="collapse-title-left">
                <el-icon><EditPen /></el-icon>
                <span>学生提交</span>
              </div>
              <div class="collapse-title-right">
                <el-tag
                  type="info"
                  effect="plain"
                  size="small"
                  class="word-count-tag"
                >
                  {{ getWordCount() }}词
                </el-tag>
              </div>
            </div>
          </template>
          <div class="collapse-content">
            <!-- 附件列表 -->
            <div v-if="submissionData?.attachments && submissionData.attachments.length > 0" class="attachment-section">
              <div class="text-sm font-medium mb-2 flex items-center gap-1">
                <el-icon :size="14" color="#f59e0b"><Paperclip /></el-icon>
                作业附件（{{ submissionData.attachments.length }}个）
              </div>
              <div class="attachment-list">
                <div v-for="(att, i) in submissionData.attachments" :key="i" 
                  class="flex items-center justify-between p-2 mb-1 bg-amber-50 rounded border border-amber-200">
                  <div class="flex items-center gap-2 overflow-hidden">
                    <el-icon :size="14" :color="att.fileType?.startsWith('image/') ? '#16a34a' : '#2563eb'">
                      <PictureFilled v-if="att.fileType?.startsWith('image/')" />
                      <Document v-else />
                    </el-icon>
                    <span class="text-xs truncate max-w-[180px]" :title="att.fileName">{{ att.fileName }}</span>
                    <span class="text-xs text-gray-400 shrink-0">{{ formatFileSize(att.fileSize) }}</span>
                  </div>
                  <div class="flex gap-1 shrink-0">
                    <el-button size="small" text type="primary" @click="handlePreviewAttachment(att)">预览</el-button>
                    <el-button size="small" text type="success" @click="handleDownloadAttachment(att)">下载</el-button>
                  </div>
                </div>
              </div>
            </div>
            <div v-else class="no-content">
              <el-empty description="学生尚未上传附件" :image-size="80" />
            </div>
          </div>
        </el-collapse-item>

        <!-- AI评价 -->
        <el-collapse-item
          v-if="shouldShowAiSection"
          name="ai"
          class="ai-section"
          :class="{ 'ai-error-section': hasAiError }"
        >
          <template #title>
            <div class="collapse-title">
              <div class="collapse-title-left">
                <el-icon><Cpu /></el-icon>
                <span>AI评价</span>
                <el-tag
                  v-if="submissionData?.aiScore && !hasAiError"
                  type="danger"
                  size="default"
                  class="ai-score-tag"
                >
                  {{ submissionData.aiScore }}分
                </el-tag>
                <el-tag
                  v-if="hasAiError"
                  type="danger"
                  size="default"
                  class="ai-error-tag"
                >
                  评价失败
                </el-tag>
              </div>
            </div>
          </template>
          <div class="collapse-content">
            <!-- AI评价错误状态 -->
            <div v-if="hasAiError" class="ai-error-content">
              <div class="error-message">
                <el-icon class="error-icon"><Warning /></el-icon>
                <div class="error-details">
                  <h4>AI评价失败</h4>
                  <p class="error-text">{{ aiErrorMessage }}</p>
                  <div class="error-meta">
                    <span>使用模型：{{ aiModelUsed }}</span>
                    <span v-if="aiErrorTime"
                      >错误时间：{{ formatDateTime(aiErrorTime) }}</span
                    >
                  </div>
                </div>
              </div>
            </div>

            <!-- AI评价正常状态 -->
            <div v-else class="ai-content">
              <div
                v-if="submissionData.aiReviewContent"
                v-html="formatReviewContent(submissionData.aiReviewContent)"
              ></div>
              <div v-else>暂无AI评价内容</div>

              <!-- AI评价元数据 -->
              <div v-if="aiMetadata && !hasAiError" class="ai-metadata">
                <div class="metadata-item">
                  <span class="label">使用模型：</span>
                  <span class="value">{{
                    aiMetadata.modelUsed || "未知"
                  }}</span>
                </div>
                <div class="metadata-item" v-if="aiMetadata.processingTime">
                  <span class="label">处理耗时：</span>
                  <span class="value">{{
                    formatProcessingTime(aiMetadata.processingTime)
                  }}</span>
                </div>
                <div class="metadata-item" v-if="aiMetadata.tokenUsage?.total">
                  <span class="label">Token消耗：</span>
                  <span class="value">{{ aiMetadata.tokenUsage.total }}</span>
                </div>
                <div class="metadata-item" v-if="submissionData?.aiReviewedAt">
                  <span class="label">评价时间：</span>
                  <span class="value">{{
                    formatDateTime(submissionData.aiReviewedAt)
                  }}</span>
                </div>
              </div>
            </div>
          </div>
        </el-collapse-item>
      </el-collapse>

      <!-- 教师批改 -->
      <div class="section teacher-section">
        <div class="section-header">
          <h4>
            <el-icon><User /></el-icon>教师批改
          </h4>
          <div v-if="submissionData.teacherScore" class="teacher-score">
            当前评分：<span class="score">{{
              submissionData.teacherScore
            }}</span
            >分
          </div>
        </div>
        <div class="section-content">
          <!-- 评分输入 -->
          <div class="grading-form">
            <el-form
              :model="gradingForm"
              :rules="gradingRules"
              ref="gradingFormRef"
              label-width="80px"
            >
              <el-form-item label="教师评分" prop="score">
                <el-input-number
                  v-model="gradingForm.score"
                  :min="0"
                  :max="100"
                  :precision="1"
                  placeholder="请输入评分（0-100）"
                  style="width: 200px"
                />
                <span class="score-unit">分</span>
              </el-form-item>

              <el-form-item label="评价内容" prop="reviewContent">
                <el-input
                  v-model="gradingForm.reviewContent"
                  type="textarea"
                  :rows="4"
                  placeholder="请输入对学生作业的评价和建议..."
                  maxlength="1000"
                  show-word-limit
                />
              </el-form-item>
            </el-form>
          </div>

          <!-- 当前批改记录 -->
          <div
            v-if="
              submissionData.teacherReviewContent || submissionData.teacherScore
            "
            class="current-review"
          >
            <h5>当前批改记录</h5>
            <div class="current-content">
              <div class="current-score">
                评分：{{ submissionData.teacherScore || "无" }}分
              </div>
              <div class="current-comment">
                评价：{{ submissionData.teacherReviewContent || "无评价" }}
              </div>
              <div v-if="submissionData.teacherReviewedAt" class="current-time">
                批改时间：{{ formatDateTime(submissionData.teacherReviewedAt) }}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 底部操作按钮 -->
    <template #footer>
      <div class="drawer-footer">
        <el-button @click="handleClose">取消</el-button>
        <el-button
          v-if="submissionData?.status !== 'not_submitted'"
          type="primary"
          @click="handleSubmitGrading"
          :loading="submitting"
          :disabled="!gradingForm.score"
        >
          {{ submissionData?.teacherScore ? "更新批改" : "提交批改" }}
        </el-button>
      </div>
    </template>
  </el-drawer>

  <!-- 文件预览对话框 -->
  <FilePreviewDialog ref="filePreviewRef" />
</template>

<script lang="ts" setup>
import { ref, reactive, watch, nextTick, computed } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { Document, EditPen, Cpu, User, Warning, Paperclip, PictureFilled } from "@element-plus/icons-vue";
import type { FormInstance, FormRules } from "element-plus";
import { getSubmissionDetail, submitTeacherReview } from "@/api/correcting";
import { getAssignmentDetail } from "@/api/assignments";
import { marked } from "marked";
import FilePreviewDialog from "@/components/FilePreviewDialog.vue";
// Props
interface Props {
  visible: boolean;
  submissionId: string | null;
  assignmentId: string;
}

const props = defineProps<Props>();

// Emits
const emit = defineEmits<{
  "update:visible": [value: boolean];
  graded: [];
}>();

// 响应式数据
const loading = ref(false);
const submitting = ref(false);
const submissionData = ref<any>(null);
const assignmentData = ref<any>(null);
const gradingFormRef = ref<FormInstance>();
const filePreviewRef = ref();

// 折叠面板激活状态 - 默认展开学生提交和教师批改相关的面板
const activeCollapse = ref(["submission"]);

// 批改表单
const gradingForm = reactive({
  score: undefined as number | undefined,
  reviewContent: "",
});

// 表单验证规则
const gradingRules: FormRules = {
  score: [
    { required: true, message: "请输入评分", trigger: "blur" },
    {
      type: "number",
      min: 0,
      max: 100,
      message: "评分范围为0-100分",
      trigger: "blur",
    },
  ],
  reviewContent: [
    { required: true, message: "请输入评价内容", trigger: "blur" },
    { min: 10, message: "评价内容不能少于10个字符", trigger: "blur" },
  ],
};

// 计算属性
const visible = computed({
  get: () => props.visible,
  set: (value) => emit("update:visible", value),
});

// AI评价相关计算属性
const aiMetadata = computed(() => {
  return submissionData.value?.aiReviewMetadata || null;
});

const hasAiError = computed(() => {
  return aiMetadata.value?.error ? true : false;
});

const aiErrorMessage = computed(() => {
  return aiMetadata.value?.error || "未知错误";
});

const aiErrorTime = computed(() => {
  return aiMetadata.value?.errorTime || null;
});

const aiModelUsed = computed(() => {
  return aiMetadata.value?.modelUsed || "未知";
});

const shouldShowAiSection = computed(() => {
  // 显示AI评价部分的条件：有AI评价内容、AI评分，或者有AI元数据（包括错误情况）
  return (
    submissionData.value?.aiReviewContent ||
    submissionData.value?.aiScore ||
    aiMetadata.value
  );
});

// 监听弹框显示
watch(
  () => props.visible,
  (newVal) => {
    if (newVal && props.submissionId) {
      loadData();
    }
  }
);

// 监听提交ID变化
watch(
  () => props.submissionId,
  (newVal) => {
    if (newVal && props.visible) {
      loadData();
    }
  }
);

// 解析ai评价，把markdown转为html
// const parseAiReviewContent = (content: string) => {
//   return marked.parse(content)
// }
const formatReviewContent = (content: string) => {
  if (!content) return "";

  return content
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/\n/g, "<br>")
    .replace(/(总分[：:]\s*\d+\s*分)/g, '<span style="color:#e53e3e;font-size:1.3em;font-weight:bold">$1</span>')
    .replace(/(\d+)\s*\/\s*(\d+)(\s*分)/g, '<strong style="color:#e53e3e">$1/$2$3</strong>')
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/~~(.*?)~~/g, '<span style="color:#2563eb;font-weight:600">$1</span>')
    .replace(/✅\s*优点/g, '<span style="color:#16a34a;font-weight:bold;font-size:1.1em">✅ 优点</span>')
    .replace(/📝\s*改进建议/g, '<span style="color:#ea580c;font-weight:bold;font-size:1.1em">📝 改进建议</span>')
    .replace(/(\d+[.、]\s*(?:内容|结构|语言|语法|词汇|表达|论证|逻辑|计算|规范|创意|准确|完整|组织|步骤).*?)(?=<br>|<div>|$)/g, '<strong style="color:#1e40af">$1</strong>')
    .replace(/\*(.*?)\*/g, "<em>$1</em>")
    .replace(/📊\s*(.+?)(?=<br>|<div>|$)/g, '<div style="background:#f0f9ff;padding:4px 8px;border-radius:4px;margin:4px 0">📊 $1</div>');
};

// 加载数据
const loadData = async () => {
  if (!props.submissionId || !props.assignmentId) return;

  loading.value = true;
  try {
    // 调用真实API
    const [submissionRes, assignmentRes] = await Promise.all([
      getSubmissionDetail(props.submissionId),
      getAssignmentDetail(props.assignmentId),
    ]);

    submissionData.value = submissionRes;
    assignmentData.value = assignmentRes;

    // 回显已有的批改数据
    if (submissionData.value.teacherScore) {
      gradingForm.score = submissionData.value.teacherScore;
    }
    if (submissionData.value.teacherReviewContent) {
      gradingForm.reviewContent = submissionData.value.teacherReviewContent;
    }
  } catch (error) {
    console.error("加载数据失败", error);
    ElMessage.error("加载数据失败");
  } finally {
    loading.value = false;
  }
};

// 提交批改
const handleSubmitGrading = async () => {
  if (!gradingFormRef.value) return;

  try {
    const valid = await gradingFormRef.value.validate();
    if (!valid) return;

    const confirmMsg = submissionData.value.teacherScore
      ? "确定要更新这份作业的批改吗？"
      : "确定要提交这份作业的批改吗？";

    await ElMessageBox.confirm(confirmMsg, "确认批改", {
      confirmButtonText: "确定",
      cancelButtonText: "取消",
      type: "warning",
    });

    submitting.value = true;

    // 调用真实批改API
    await submitTeacherReview({
      submissionId: props.submissionId!,
      teacherReviewContent: gradingForm.reviewContent,
      teacherScore: gradingForm.score!,
    });

    ElMessage.success("批改提交成功");
    emit("graded");
    handleClose();
  } catch (error) {
    if (error !== "cancel") {
      console.error("提交批改失败", error);
      ElMessage.error("提交批改失败");
    }
  } finally {
    submitting.value = false;
  }
};

// 关闭抽屉
const handleClose = () => {
  visible.value = false;
  // 重置表单
  nextTick(() => {
    if (gradingFormRef.value) {
      gradingFormRef.value.resetFields();
    }
    gradingForm.score = undefined;
    gradingForm.reviewContent = "";
    submissionData.value = null;
    assignmentData.value = null;
    // 重置折叠面板状态
    activeCollapse.value = ["submission"];
  });
};

// 工具函数
const getWordCount = () => {
  if (!submissionData.value) return 0;
  return submissionData.value.wordCount || 0;
};

const formatFileSize = (bytes: number) => {
  if (!bytes) return '0B';
  if (bytes < 1024) return bytes + 'B';
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + 'KB';
  return (bytes / 1048576).toFixed(1) + 'MB';
};

const handleDownloadAttachment = (att: any) => {
  const token = localStorage.getItem('token');
  const filename = att.fileUrl.replace('/uploads/', '');
  fetch(`/api/upload/download/${filename}`, { headers: { Authorization: `Bearer ${token}` } })
    .then(res => res.blob())
    .then(blob => {
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = att.fileName; a.click();
      URL.revokeObjectURL(url);
    })
    .catch(() => ElMessage.warning('下载失败'));
};

const handlePreviewAttachment = (att: any) => {
  filePreviewRef.value?.open(att);
};

const getSubmissionStatusType = (status: string) => {
  const types: Record<
    string,
    "success" | "info" | "warning" | "primary" | "danger"
  > = {
    draft: "warning",
    submitted: "success",
    ai_reviewed: "primary",
    teacher_reviewed: "success",
    not_submitted: "info",
  };
  return types[status] || "info";
};

const getSubmissionStatusText = (status: string) => {
  const texts: Record<string, string> = {
    draft: "草稿",
    submitted: "已提交",
    ai_reviewed: "AI已评",
    teacher_reviewed: "教师已批改",
    not_submitted: "未提交",
  };
  return texts[status] || "未知";
};

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

const formatProcessingTime = (timeMs: number) => {
  if (!timeMs) return "-";
  if (timeMs < 1000) {
    return `${timeMs}ms`;
  } else if (timeMs < 60000) {
    return `${(timeMs / 1000).toFixed(1)}s`;
  } else {
    const minutes = Math.floor(timeMs / 60000);
    const seconds = Math.floor((timeMs % 60000) / 1000);
    return `${minutes}m ${seconds}s`;
  }
};

// 组件名称
defineOptions({
  name: "GradingDrawer",
});
</script>

<style>
/* 抽屉内容样式 */
.drawer-content {
  padding: 0 20px 20px;
  height: 100%;
  overflow-y: auto;
}

.loading-container {
  padding: 20px;
}

/* 学生信息头部 */
.student-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 20px 0;
  border-bottom: 1px solid #e5e7eb;
  margin-bottom: 20px;
}

.student-info {
  display: flex;
  align-items: center;
  gap: 16px;
}

.student-avatar {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  font-weight: 600;
}

.student-details {
  flex: 1;
}

.student-name {
  margin: 0 0 8px 0;
  font-size: 20px;
  font-weight: 600;
  color: #1f2937;
}

.student-meta {
  margin: 0;
  font-size: 14px;
  color: #6b7280;
  display: flex;
  gap: 16px;
}

.submission-meta {
  text-align: right;
}

.submit-time {
  margin: 8px 0 0 0;
  font-size: 13px;
  color: #6b7280;
}

/* 折叠面板样式 */
.grading-collapse {
  margin-bottom: 24px;
  border: none;
}

.grading-collapse :deep(.el-collapse-item) {
  margin-bottom: 16px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  overflow: hidden;
}

.grading-collapse :deep(.el-collapse-item__header) {
  padding: 16px 20px;
  background: #f8fafc;
  border-bottom: none;
  font-size: 16px;
  font-weight: 600;
  color: #374151;
  height: auto;
  line-height: 1.5;
}

.grading-collapse :deep(.el-collapse-item__content) {
  padding: 0;
  border-top: 1px solid #e5e7eb;
}

.collapse-title {
  display: flex;
  align-items: center;
  width: 100%;
  justify-content: space-between;
}

.collapse-title-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.collapse-title-right {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #6b7280;
}

.collapse-content {
  padding: 20px;
}

/* 章节样式 - 保留给教师批改部分 */
.section {
  margin-bottom: 24px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  overflow: hidden;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  background: #f8fafc;
  border-bottom: 1px solid #e5e7eb;
}

.section-header h4 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #374151;
  display: flex;
  align-items: center;
  gap: 8px;
}

.section-content {
  padding: 20px;
}

/* 作业要求样式 */
.assignment-content {
  font-size: 14px;
  line-height: 1.6;
  color: #374151;
  margin-bottom: 16px;
}

.assignment-meta {
  display: flex;
  gap: 16px;
  font-size: 13px;
  color: #6b7280;
}

/* 学生提交样式 */
.word-count-tag {
  font-weight: 600;
  font-family: "SF Mono", "Monaco", "Inconsolata", "Roboto Mono", monospace;
}

.word-count {
  font-family: "SF Mono", "Monaco", "Inconsolata", "Roboto Mono", monospace;
}

.submission-content {
  font-size: 14px;
  line-height: 1.6;
  color: #374151;
  min-height: 100px;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  padding: 16px;
  background: #fafafa;
}

.no-content {
  text-align: center;
  padding: 40px 0;
}

/* AI评价样式 */
.ai-section :deep(.el-collapse-item__header) {
  background: #eff6ff !important;
}

.ai-error-section :deep(.el-collapse-item__header) {
  background: #fef2f2 !important;
}

.ai-score-tag {
  font-weight: 600;
  font-family: "SF Mono", "Monaco", "Inconsolata", "Roboto Mono", monospace;
  margin-left: 8px;
  font-size: 25px;
}

.ai-error-tag {
  font-weight: 600;
  font-family: "SF Mono", "Monaco", "Inconsolata", "Roboto Mono", monospace;
  margin-left: 8px;
  background: #fee2e2;
  color: #dc2626;
  border-color: #fecaca;
}

.ai-score {
  font-size: 14px;
  color: #1d4ed8;
  font-weight: 600;
}

.ai-content {
  font-size: 14px;
  line-height: 1.6;
  color: #374151;
  background: #f0f9ff;
  border: 1px solid #bfdbfe;
  border-radius: 6px;
  padding: 16px;
  margin-bottom: 12px;
}

.ai-time {
  font-size: 12px;
  color: #6b7280;
}

/* AI错误状态样式 */
.ai-error-content {
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 6px;
  padding: 16px;
}

.error-message {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.error-icon {
  color: #dc2626;
  font-size: 20px;
  margin-top: 2px;
  flex-shrink: 0;
}

.error-details h4 {
  margin: 0 0 8px 0;
  font-size: 16px;
  font-weight: 600;
  color: #dc2626;
}

.error-text {
  margin: 0 0 12px 0;
  font-size: 14px;
  color: #7f1d1d;
  line-height: 1.5;
}

.error-meta {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
  color: #991b1b;
}

/* AI元数据样式 */
.ai-metadata {
  margin-top: 16px;
  padding: 12px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
}

.metadata-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
  font-size: 12px;
}

.metadata-item:last-child {
  margin-bottom: 0;
}

.metadata-item .label {
  color: #64748b;
  font-weight: 500;
}

.metadata-item .value {
  color: #334155;
  font-weight: 600;
  font-family: "SF Mono", "Monaco", "Inconsolata", "Roboto Mono", monospace;
}

/* 教师批改样式 */
.teacher-section .section-header {
  background: #f0fdf4;
}

.teacher-score {
  font-size: 14px;
  color: #166534;
  font-weight: 600;
}

.score {
  font-size: 18px;
  font-weight: 700;
}

.score-unit {
  margin-left: 8px;
  color: #6b7280;
  font-size: 14px;
}

.grading-form {
  margin-bottom: 24px;
}

.current-review {
  border-top: 1px solid #e5e7eb;
  padding-top: 20px;
}

.current-review h5 {
  margin: 0 0 12px 0;
  font-size: 14px;
  font-weight: 600;
  color: #374151;
}

.current-content {
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  padding: 16px;
}

.current-score,
.current-comment,
.current-time {
  margin-bottom: 8px;
  font-size: 13px;
  color: #6b7280;
}

.current-score {
  font-weight: 600;
  color: #374151;
}

/* 底部按钮 */
.drawer-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 16px 20px;
  border-top: 1px solid #e5e7eb;
  background: #fafafa;
}

/* 响应式 */
@media (max-width: 768px) {
  .student-header {
    flex-direction: column;
    gap: 16px;
    align-items: flex-start;
  }

  .student-meta {
    flex-direction: column;
    gap: 4px;
  }

  .section-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }

  .assignment-meta {
    flex-direction: column;
    gap: 8px;
  }

  .collapse-title {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }

  .collapse-title-left {
    align-self: flex-start;
  }

  .collapse-title-right {
    align-self: flex-start;
    margin-top: 4px;
  }

  .grading-collapse :deep(.el-collapse-item__header) {
    padding: 12px 16px;
  }

  .collapse-content {
    padding: 16px;
  }
}

/* 深度样式 */
:deep(.el-drawer__header) {
  margin-bottom: 0;
  padding: 20px 20px 0;
  border-bottom: 1px solid #e5e7eb;
}

:deep(.el-drawer__body) {
  padding: 0;
}

:deep(.el-form-item__label) {
  font-weight: 600;
  color: #374151;
}

:deep(.el-input-number) {
  width: 200px;
}
</style>
