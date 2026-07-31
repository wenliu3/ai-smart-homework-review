<template>
  <div class="student-page submission-container">
    <header class="submission-hero">
      <div class="submission-hero__inner">
        <el-button class="back-button" text :icon="ArrowLeft" @click="goBack">
          返回作业列表
        </el-button>

        <div class="submission-hero__content">
          <div class="submission-hero__copy">
            <p class="student-eyebrow">ASSIGNMENT WORKSPACE</p>
            <h1>{{ submissionData?.assignment?.title || "作业提交" }}</h1>
            <p>查看要求、完成提交并跟进 AI 与教师评价。</p>
          </div>
          <div class="submission-hero__statuses">
            <span
              v-if="submissionData?.submission"
              class="student-status"
              :class="`student-status--${statusTagType}`"
            >
              {{ statusText }}
            </span>
            <span
              v-else
              class="student-status student-status--info"
            >
              待提交
            </span>
            <span
              v-if="hasFormalSubmission"
              class="student-status"
              :class="`student-status--${reviewStatusTagType}`"
            >
              {{ reviewStatusText }}
            </span>
          </div>
        </div>

        <el-alert
          v-if="submissionLimitInfo"
          :title="submissionLimitInfo.title"
          :type="submissionLimitInfo.type"
          :closable="false"
          show-icon
          class="submission-limit-alert"
        >
          <template v-if="submissionLimitInfo.message" #default>
            {{ submissionLimitInfo.message }}
          </template>
        </el-alert>
      </div>
    </header>

    <main class="submission-shell" v-loading="loading">
      <div v-if="submissionData" class="submission-workspace student-card">
        <nav class="tab-navigation" aria-label="作业处理步骤">
          <el-tabs
            v-model="activeTab"
            class="submission-tabs"
            @tab-change="handleTabChange"
          >
            <el-tab-pane name="assignment">
              <template #label>
                <span class="tab-label"><b>1</b><span>作业详情</span></span>
              </template>
            </el-tab-pane>
            <el-tab-pane name="submission">
              <template #label>
                <span class="tab-label">
                  <b>2</b><span>提交作业</span>
                  <el-badge
                    v-if="submissionData.submission?.status === 'draft'"
                    is-dot
                  />
                </span>
              </template>
            </el-tab-pane>
            <el-tab-pane name="results">
              <template #label>
                <span class="tab-label">
                  <b>3</b><span>评价结果</span>
                  <el-badge
                    v-if="
                      submissionData.aiReview || submissionData.teacherReview
                    "
                    is-dot
                  />
                </span>
              </template>
            </el-tab-pane>
          </el-tabs>
        </nav>

        <div class="tab-content">
          <section v-show="activeTab === 'assignment'" class="tab-pane">
            <AssignmentInfo
              :assignment="submissionData.assignment"
              :submission="submissionData.submission"
              :status-tag-type="statusTagType"
              :status-text="statusText"
              :is-overdue="isOverdue"
            />
          </section>

          <section
            v-show="activeTab === 'submission'"
            class="tab-pane submission-pane"
          >
            <div
              v-show="showAiProcessingFullscreen"
              class="ai-processing-overlay"
            >
              <div class="ai-processing-content">
                <div class="ai-loading-main">
                  <img
                    src="@/assets/image/ai_loading.gif"
                    alt="AI 正在批改"
                    class="ai-loading-gif-large"
                  />
                </div>
                <p class="student-eyebrow">AI REVIEW</p>
                <h3 class="processing-title">AI 智能批改中</h3>
                <p class="processing-description">
                  正在分析作业内容并生成评分与改进建议。
                </p>
                <p class="status-text">
                  {{
                    isPolling
                      ? `正在查询进度（第 ${pollingCount} 次）`
                      : "通常约 1 分钟完成，请稍候"
                  }}
                </p>
                <el-button
                  class="view-progress-btn"
                  type="primary"
                  plain
                  @click="switchToTab('results')"
                >
                  查看评价进度
                </el-button>
              </div>
            </div>

            <div
              v-show="!showAiProcessingFullscreen"
              class="form-content-wrapper"
            >
              <div class="submission-section-heading">
                <div>
                  <p class="student-eyebrow">YOUR WORK</p>
                  <h2>完成并提交作业</h2>
                  <p>正文和附件至少填写一项，正式提交前仍可保存草稿。</p>
                </div>
                <span v-if="saving || lastSaveTime" class="save-status">
                  <el-icon v-if="saving" class="animate-spin"
                    ><Loading
                  /></el-icon>
                  {{ saving ? "正在保存" : lastSaveTime }}
                </span>
              </div>

              <SubmissionForm
                v-if="showSubmissionForm"
                ref="submissionFormRef"
                :submission="submissionData.submission"
                :assignment="submissionData.assignment"
                :is-overdue="isOverdue"
                @success="handleSuccess"
              />

              <SubmittedContent
                v-if="showSubmittedContent"
                :submission="submissionData.submission"
              />
            </div>

            <footer
              v-if="canSubmit && !isOverdue && !isTerminated"
              class="tab-actions-bar"
            >
              <p>提交后将自动开始 AI 评价，请确认内容与附件无误。</p>
              <div class="actions-right">
                <el-button
                  v-if="submissionData.submission?.status === 'draft'"
                  type="danger"
                  plain
                  :loading="deleting"
                  @click="handleDeleteClick"
                >
                  删除草稿
                </el-button>
                <el-button
                  v-if="canSaveDraft"
                  plain
                  :loading="saving"
                  @click="handleSaveDraftClick"
                >
                  {{ saving ? "保存中..." : "保存草稿" }}
                </el-button>
                <el-button
                  class="student-primary-button submit-btn"
                  type="primary"
                  :loading="submitting"
                  @click="handleSubmitClick"
                >
                  {{ getSubmitButtonText() }}
                </el-button>
              </div>
            </footer>
          </section>

          <section
            v-show="activeTab === 'results'"
            class="tab-pane results-pane"
          >
            <ReviewResults
              :ai-review="submissionData.aiReview"
              :teacher-review="submissionData.teacherReview"
              :submission-status="submissionData.submission?.status"
              :assignment="submissionData.assignment"
              :is-polling="isPolling"
              :polling-count="pollingCount"
            />
          </section>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, watch } from "vue";
import { useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { ArrowLeft, Loading } from "@element-plus/icons-vue";
import AssignmentInfo from "./components/AssignmentInfo.vue"; // 作业信息
import SubmissionForm from "./components/SubmissionForm.vue"; // 作业提交表单
import SubmittedContent from "./components/SubmittedContent.vue"; // 已提交的作业内容
import ReviewResults from "./components/ReviewResults.vue"; // 批改结果
import { useSubmissionManagement, useSubmissionUtils } from "./composables";
import { SubmissionsApi } from "../../../api/submissions";
import { useRoute } from "vue-router";

const router = useRouter();
const route = useRoute();

// 路由参数（兼容query和params）
const assignmentId = computed(() => {
  const id = (route.query.assignmentId || route.params.assignmentId) as string;
  console.log(
    "📍 获取assignmentId:",
    id,
    "from query:",
    route.query.assignmentId,
    "from params:",
    route.params.assignmentId
  );
  return id;
});

const classId = computed(() => {
  const id = (route.query.classId || route.params.classId) as string;
  console.log(
    "📍 获取classId:",
    id,
    "from query:",
    route.query.classId,
    "from params:",
    route.params.classId
  );
  return id;
});

// 表单引用和Tab状态
const submissionFormRef = ref();
const activeTab = ref("assignment");
const lastSaveTime = ref("");
const showAiProcessingFullscreen = ref(false);
const aiTimeoutTimer = ref<NodeJS.Timeout | null>(null);

// 使用组合式函数
const {
  // 状态
  loading,
  submitting,
  saving,
  deleting,
  submissionData,

  // 轮询状态
  isPolling,
  pollingCount,

  // 计算属性
  isSubmitted,
  canSaveDraft,
  canSubmit,
  submissionLimitInfo,
  showSubmissionForm,
  showSubmittedContent,
  isOverdue,
  statusTagType,
  statusText,

  // 方法
  loadData,
  handleSubmit,
  handleSaveDraft,
  handleDelete,
  checkAndStartPolling,
  stopPolling,
} = useSubmissionManagement();

const { formatDate } = useSubmissionUtils();

// 计算属性
const isTerminated = computed(() => {
  return (submissionData.value?.assignment as any)?.status === "terminated";
});

const hasFormalSubmission = computed(() => {
  const status = submissionData.value?.submission?.status;
  return Boolean(status && status !== "draft");
});

// 批改状态标签类型
const reviewStatusTagType = computed(() => {
  if (!submissionData.value?.submission) return "info";

  const status = submissionData.value.submission.status;
  switch (status) {
    case "teacher_reviewed":
      return "success";
    case "ai_reviewed":
      return "warning";
    case "submitted":
      return "info";
    default:
      return "info";
  }
});

// 批改状态文本
const reviewStatusText = computed(() => {
  if (!submissionData.value?.submission) return "待批改";

  const status = submissionData.value.submission.status;
  switch (status) {
    case "teacher_reviewed":
      return "已批改";
    case "ai_reviewed":
      return "AI已评";
    case "submitted":
      return "待批改";
    default:
      return "待批改";
  }
});

// 返回上一页
const goBack = () => {
  router.back();
};

// 获取提交按钮文本
const getSubmitButtonText = () => {
  const submission = submissionData.value?.submission;

  // 如果没有提交记录，显示"提交作业"
  if (!submission) {
    return "提交作业";
  }

  // 根据状态显示不同文本
  switch (submission.status) {
    case "draft":
      return "提交作业";
    case "submitted":
      return "重新提交";
    case "ai_reviewed":
      return "重新提交";
    case "teacher_reviewed":
      return "已批改"; // 这个状态下按钮应该被隐藏，但以防万一
    default:
      return "提交作业";
  }
};

// Tab切换处理
const handleTabChange = (tabName: string) => {
  console.log("切换到Tab:", tabName);

  // 如果切换到提交Tab且有草稿，自动聚焦编辑器
  if (
    tabName === "submission" &&
    submissionData.value?.submission?.status === "draft"
  ) {
    // 延迟执行，等待DOM更新
    setTimeout(() => {
      // 这里可以添加聚焦编辑器的逻辑
    }, 100);
  }
};

// 智能Tab切换
const switchToTab = (tabName: string) => {
  activeTab.value = tabName;
};

// 处理子组件的成功事件
const handleSuccess = (message: string) => {
  // 重新加载数据以更新状态
  loadData();

  // 只有在手动提交成功时才切换到评价结果Tab
  // 轮询更新不应该触发Tab切换
  if (message.includes("提交成功") && !isPolling.value) {
    setTimeout(() => {
      switchToTab("results");
    }, 1000);
  }
};

// 更新最后保存时间
const updateLastSaveTime = () => {
  const now = new Date();
  const timeStr = now.toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
  });
  lastSaveTime.value = `最后保存: ${timeStr}`;
};

// 启动AI超时保护
const startAiTimeout = () => {
  // 清除之前的计时器
  clearAiTimeout();

  console.log("⏰ 启动AI超时保护 (30秒)");
  aiTimeoutTimer.value = setTimeout(() => {
    if (showAiProcessingFullscreen.value) {
      console.log("⚠️ AI评价超时，关闭Loading");
      showAiProcessingFullscreen.value = false;
      ElMessage.warning("AI评价时间较长，请稍后刷新页面查看结果");
    }
  }, 30000); // 30秒
};

// 清除AI超时保护
const clearAiTimeout = () => {
  if (aiTimeoutTimer.value) {
    console.log("🔄 清除AI超时保护计时器");
    clearTimeout(aiTimeoutTimer.value);
    aiTimeoutTimer.value = null;
  }
};

// 提交作业
const handleSubmitClick = async () => {
  if (!submissionFormRef.value) return;

  try {
    console.log("开始表单验证...");
    const isValid = await submissionFormRef.value.validate();
    console.log("表单验证结果:", isValid);
    if (!isValid) {
      ElMessage.warning("请完善作业内容后再提交");
      return;
    }

    // 获取已上传的附件和内容
    const fn = submissionFormRef.value?.getUploadedAttachments;
    const attachments = (typeof fn === "function" ? fn() : []) || [];
    if (!Array.isArray(attachments)) {
      console.error("getUploadedAttachments 返回非数组值:", attachments);
    }
    const content = submissionFormRef.value?.getContent?.() || "";
    console.log(
      "提交时附件数:",
      Array.isArray(attachments) ? attachments.length : "非数组",
      typeof attachments
    );

    // 调用提交处理（确保 attachments 是数组）
    await handleSubmitWithAiLoading(
      Array.isArray(attachments) ? attachments : [],
      content
    );
  } catch (error: any) {
    console.error("提交失败:", error);
    ElMessage.error(error?.message || "提交失败，请重试");
  }
};

// 带AI Loading控制的提交处理
const handleSubmitWithAiLoading = async (
  attachments: any[],
  content: string = ""
) => {
  try {
    // 根据当前状态显示不同的确认信息
    const isResubmit =
      submissionData.value?.submission &&
      submissionData.value.submission.status !== "draft";

    const confirmMessage = isResubmit
      ? "确定要重新提交作业吗？这将覆盖之前的提交内容。"
      : "确定要提交作业吗？";

    await ElMessageBox.confirm(confirmMessage, "确认提交", {
      confirmButtonText: "确定提交",
      cancelButtonText: "取消",
      type: "warning",
    });

    // 用户确认后，先标记文件已被消费（防止组件卸载时清理文件）
    submissionFormRef.value?.markFilesConsumed?.();

    // 显示AI处理Loading
    showAiProcessingFullscreen.value = true;

    // 启动超时保护（每次提交都重新计时）
    startAiTimeout();

    // 调用纯提交逻辑（不包含确认对话框）
    await handleSubmitDirect(attachments, content);

    // 提交成功后不立即关闭Loading，等待AI评价完成
    // Loading会在轮询检测到AI评价完成后自动关闭
  } catch (error: any) {
    // 取消或出错时隐藏Loading并清除超时计时器
    showAiProcessingFullscreen.value = false;
    clearAiTimeout();

    if (error !== "cancel") {
      console.error("提交作业失败:", error);
      ElMessage.error(error.message || "提交作业失败");
    }
  }
};

// 直接提交（不包含确认对话框）
const handleSubmitDirect = async (attachments: any[], content: string = "") => {
  // 根据当前状态判断是否为重新提交
  const isResubmit =
    submissionData.value?.submission &&
    submissionData.value.submission.status !== "draft";

  submitting.value = true;

  try {
    const params: any = {
      assignmentId: assignmentId.value,
      classId: classId.value,
      content,
      isDraft: false,
    };

    // 调试日志
    console.log("🔍 提交参数检查:");
    console.log("assignmentId:", assignmentId.value);
    console.log("classId:", classId.value);
    console.log("attachments count:", attachments?.length || 0);
    console.log("route.params:", route.params);

    // 只有当有附件时才添加 attachments 字段
    if (attachments && attachments.length > 0) {
      params.attachments = attachments;
    }

    console.log("📤 最终提交参数:", params);
    await SubmissionsApi.submit(params);
    // 标记文件已被消费，防止组件卸载时清理
    submissionFormRef.value?.markFilesConsumed?.();
    ElMessage.success(isResubmit ? "作业重新提交成功！" : "作业提交成功！");

    // 重新加载数据
    await loadData();

    // 启动AI评价轮询
    checkAndStartPolling();
  } finally {
    submitting.value = false;
  }
};

// 保存草稿
const handleSaveDraftClick = async () => {
  if (!submissionFormRef.value) return;

  // 检查是否可以保存草稿
  if (!canSaveDraft.value) {
    ElMessage.warning("作业已提交，无法保存草稿");
    return;
  }

  try {
    const isValid = await submissionFormRef.value.validate();
    if (!isValid) {
      // 表单校验失败时，ElementPlus会自动滚动到第一个错误字段
      return;
    }

    const attachments =
      (await submissionFormRef.value.getUploadedAttachments?.()) || [];
    const content = submissionFormRef.value?.getContent?.() || "";
    await handleSaveDraft(attachments, content);
    // 标记文件已被消费，防止组件卸载时清理
    submissionFormRef.value?.markFilesConsumed?.();

    // 更新保存时间
    updateLastSaveTime();
  } catch (error) {
    console.error("表单验证失败:", error);
  }
};

// 删除草稿
const handleDeleteClick = () => {
  handleDelete();
};

// 智能初始化Tab
const initializeTab = () => {
  if (!submissionData.value) return;

  // 如果正在显示AI处理Loading，不要切换Tab
  if (showAiProcessingFullscreen.value) return;

  // 如果当前Tab是用户主动选择的（比如正在查看评价结果），不要自动切换
  if (activeTab.value === "results" && submissionData.value.aiReview) return;

  const submission = submissionData.value.submission;
  const hasAiReview = submissionData.value.aiReview;
  const hasTeacherReview = submissionData.value.teacherReview;

  // 只在首次加载时智能选择Tab，避免轮询更新时的误切换
  const isInitialLoad = !submission || activeTab.value === "assignment";

  if (isInitialLoad) {
    // 根据状态智能选择初始Tab
    if (hasTeacherReview || hasAiReview) {
      // 如果有评价结果，优先显示评价结果
      activeTab.value = "results";
    } else if (submission && submission.status !== "draft") {
      // 如果已提交但还没有评价，显示提交Tab
      activeTab.value = "submission";
    } else if (submission && submission.status === "draft") {
      // 如果是草稿状态，显示提交Tab便于继续编辑
      activeTab.value = "submission";
    } else {
      // 首次访问，显示作业详情
      activeTab.value = "assignment";
    }
  }
};

// 监听数据变化，智能切换Tab
watch(
  submissionData,
  (newData) => {
    if (newData) {
      initializeTab();
    }
  },
  { immediate: true }
);

// 监听轮询状态，当AI评价完成时关闭Loading
watch([isPolling, submissionData], ([polling, data]) => {
  // 如果正在显示AI处理Loading，且轮询停止了，说明AI评价完成
  if (showAiProcessingFullscreen.value && !polling && data?.aiReview) {
    console.log("🎉 AI评价完成，关闭Loading");
    showAiProcessingFullscreen.value = false;

    // 清除超时计时器
    clearAiTimeout();

    // 自动切换到评价结果Tab
    setTimeout(() => {
      switchToTab("results");
    }, 500);
  }
});

// 组件挂载时加载数据
onMounted(async () => {
  await loadData();
  // 加载完成后检查是否需要启动轮询
  checkAndStartPolling();
  // 初始化Tab
  initializeTab();
});

// 组件卸载时清理资源
onUnmounted(() => {
  // 清除AI超时计时器
  clearAiTimeout();

  // 停止轮询和清理轮询相关资源
  stopPolling();

  console.log("🧹 组件卸载，已清理所有计时器和轮询资源");
});
</script>

<style scoped>
@import "../student-theme.css";

/* 主容器 */
.submission-container {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #f8fafc;
  overflow: hidden;
}

/* 页面头部 */
.header-section {
  flex-shrink: 0;
  background: white;
  border-bottom: 1px solid #e5e7eb;
  padding: 1rem 1.5rem;
  box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1);
}

.header-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  max-width: 1200px;
  margin: 0 auto;
}

/* Tab容器 */
.tab-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  max-width: 1200px;
  margin: 0 auto;
  width: 100%;
}

/* Tab导航栏 */
.tab-navigation {
  flex-shrink: 0;
  background: white;
  border-bottom: 1px solid #e5e7eb;
  padding: 0 1.5rem;
}

.submission-tabs {
  --el-tabs-header-height: 60px;
}

.tab-label {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  font-size: 14px;
  font-weight: 500;
}

.tab-text {
  white-space: nowrap;
}

/* Tab内容区域 */
.tab-content {
  flex: 1;
  overflow: hidden;
  background: #f8fafc;
}

.tab-pane {
  height: 100%;
  overflow-y: auto;
  padding: 0;
  position: relative;
}

/* Tab操作按钮区域 */
.tab-actions-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.5rem;
  background: white;
  border-bottom: 1px solid #e5e7eb;
  margin-bottom: 0;
}

/* 表单内容容器 */
.form-content-wrapper {
  padding: 1.5rem;
}

/* 带padding的Tab面板 */
.tab-pane-padded {
  padding: 1.5rem;
}

.actions-left,
.actions-right {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.actions-left .section-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #1f2937;
}

.tab-actions-bar .el-button {
  height: 32px;
  font-size: 13px;
}

/* 内联保存状态 */
.auto-save-status-inline {
  padding: 0 0 1rem;
  text-align: right;
}

/* AI处理全屏Loading */
.ai-processing-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.ai-processing-content {
  text-align: center;
  max-width: 400px;
  padding: 2rem;
}

.processing-animation {
  margin-bottom: 2rem;
  display: flex;
  justify-content: center;
  align-items: center;
}

.ai-loading-main {
  position: relative;
  display: flex;
  justify-content: center;
  align-items: center;
  width: 260px;
  height: 260px;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 16px;
  box-shadow: 0 20px 40px rgba(102, 126, 234, 0.3);
}

.ai-loading-gif-large {
  width: 230px;
  height: 230px;
  border-radius: 50%;
  object-fit: cover;
  border: 4px solid rgba(255, 255, 255, 0.3);
  animation: aiGifPulse 2s ease-in-out infinite;
}

@keyframes aiGifPulse {
  0%,
  100% {
    transform: scale(1);
  }
  50% {
    transform: scale(1.1);
  }
}

.processing-icon {
  font-size: 48px;
  color: #667eea;
  animation: processingPulse 2s ease-in-out infinite;
}

@keyframes processingPulse {
  0%,
  100% {
    transform: scale(1);
    opacity: 0.8;
  }
  50% {
    transform: scale(1.1);
    opacity: 1;
  }
}

.processing-title {
  margin: 0 0 0.75rem 0;
  font-size: 20px;
  font-weight: 600;
  color: #1f2937;
}

.processing-description {
  margin: 0 0 1.5rem 0;
  color: #6b7280;
  line-height: 1.5;
}

.processing-status {
  margin-bottom: 1.5rem;
}

.status-info {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1rem;
}

.status-text {
  margin: 0;
  font-size: 14px;
  color: #9ca3af;
}

.processing-actions {
  margin-top: 2rem;
}

.view-progress-btn {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: 2px solid transparent;
  color: white;
  font-weight: 600;
  padding: 12px 24px;
  border-radius: 25px;
  transition: all 0.3s ease;
  box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
}

.view-progress-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 25px rgba(102, 126, 234, 0.4);
  background: linear-gradient(135deg, #5a67d8 0%, #6b46c1 100%);
}

.submit-btn {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
  font-weight: 600;
  box-shadow: 0 4px 15px 0 rgba(102, 126, 234, 0.3);
  transition: all 0.3s ease;
}

.submit-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px 0 rgba(102, 126, 234, 0.4);
}

/* 响应式设计 */
@media (max-width: 768px) {
  .header-section {
    padding: 0.75rem 1rem;
  }

  .header-content {
    flex-direction: column;
    gap: 0.75rem;
    align-items: flex-start;
  }

  .tab-navigation {
    padding: 0 1rem;
  }

  .tab-actions-bar {
    padding: 0.75rem 1rem;
    flex-direction: column;
    gap: 0.75rem;
    align-items: stretch;
  }

  .actions-left {
    justify-content: center;
  }

  .actions-left .section-title {
    font-size: 14px;
  }

  .actions-right {
    justify-content: center;
    flex-wrap: wrap;
  }

  .tab-actions-bar .el-button {
    height: 36px;
    font-size: 13px;
    flex: 1;
    min-width: 100px;
  }

  .tab-pane > div:not(.ai-processing-overlay):not(.tab-actions-bar) {
    padding: 0 1rem 1rem;
  }

  .auto-save-status-inline {
    padding: 0 1rem 0.5rem;
  }

  .tab-label {
    font-size: 13px;
  }

  .ai-processing-content {
    padding: 1.5rem;
    max-width: 320px;
  }

  .processing-title {
    font-size: 18px;
  }

  .processing-icon {
    font-size: 40px;
  }
}

@media (max-width: 480px) {
  .header-content h1 {
    font-size: 16px;
  }

  .tab-label {
    font-size: 12px;
  }
}

/* Tab内容动画 */
.tab-pane {
  animation: fadeIn 0.3s ease-in-out;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* 自定义滚动条 */
.tab-pane::-webkit-scrollbar {
  width: 6px;
}

.tab-pane::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 3px;
}

.tab-pane::-webkit-scrollbar-thumb {
  background: #c1c1c1;
  border-radius: 3px;
}

.tab-pane::-webkit-scrollbar-thumb:hover {
  background: #a8a8a8;
}

/* 学生端改版覆盖层 */
.submission-container {
  height: 100%;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  background: #f5f6fa;
}

.submission-hero {
  border-bottom: 1px solid #e8e8f0;
  background: #fff;
}

.submission-hero__inner {
  width: min(1180px, calc(100% - 40px));
  margin: 0 auto;
  padding: 18px 0 22px;
}

.back-button {
  margin: 0 0 12px -8px;
  color: #737a90;
}

.submission-hero__content {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
}

.submission-hero__copy h1 {
  margin: 0;
  color: #23273b;
  font-size: clamp(22px, 2.4vw, 30px);
  line-height: 1.25;
}

.submission-hero__copy > p:last-child {
  margin: 8px 0 0;
  color: #858ca0;
  font-size: 14px;
}

.submission-hero__statuses {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.student-status--info {
  background: #f0f1f5;
  color: #747b8f;
}

.submission-limit-alert {
  margin-top: 16px;
  border-radius: 10px;
}

.submission-shell {
  width: min(1180px, calc(100% - 40px));
  min-height: 360px;
  margin: 0 auto;
  padding: 22px 0 40px;
}

.submission-workspace {
  overflow: hidden;
}

.tab-navigation {
  padding: 0 24px;
  border-bottom: 1px solid #e9eaf1;
  background: #fff;
}

.submission-tabs {
  --el-color-primary: #6558d9;
  --el-tabs-header-height: 58px;
}

.submission-tabs :deep(.el-tabs__header) {
  margin: 0;
}

.submission-tabs :deep(.el-tabs__nav-wrap::after) {
  display: none;
}

.submission-tabs :deep(.el-tabs__item) {
  padding: 0 28px;
  color: #858b9d;
  font-size: 14px;
}

.submission-tabs :deep(.el-tabs__item.is-active) {
  color: #5548c7;
  font-weight: 700;
}

.submission-tabs :deep(.el-tabs__active-bar) {
  height: 3px;
  border-radius: 3px 3px 0 0;
  background: #6558d9;
}

.tab-label {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.tab-label b {
  display: inline-flex;
  width: 22px;
  height: 22px;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: #f0f1f5;
  color: #8c92a4;
  font-size: 11px;
}

.submission-tabs :deep(.el-tabs__item.is-active) .tab-label b {
  background: #ebe8ff;
  color: #5c4fcf;
}

.tab-content {
  overflow: visible;
  background: #f8f9fc;
}

.tab-pane {
  position: relative;
  height: auto;
  min-height: 420px;
  overflow: visible;
  padding: 24px;
  animation: none;
}

.submission-pane {
  padding: 0;
}

.form-content-wrapper {
  padding: 24px;
}

.submission-section-heading {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 18px;
}

.submission-section-heading h2 {
  margin: 0;
  color: #252a40;
  font-size: 20px;
}

.submission-section-heading > div > p:last-child {
  margin: 7px 0 0;
  color: #8e95a8;
  font-size: 13px;
}

.save-status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: #8b91a3;
  font-size: 12px;
}

.tab-actions-bar {
  position: sticky;
  bottom: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  margin: 0;
  padding: 14px 24px;
  border-top: 1px solid #e7e9f0;
  border-bottom: 0;
  background: rgba(255, 255, 255, 0.96);
  box-shadow: 0 -10px 30px rgba(35, 39, 66, 0.06);
  backdrop-filter: blur(10px);
}

.tab-actions-bar p {
  margin: 0;
  color: #8b91a4;
  font-size: 12px;
}

.actions-right {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 9px;
}

.submit-btn {
  min-width: 112px;
  border: 0;
  background: linear-gradient(135deg, #685bdc, #5648c4);
}

.ai-processing-overlay {
  position: relative;
  min-height: 520px;
  background: rgba(248, 249, 252, 0.96);
}

.ai-processing-content {
  max-width: 420px;
  padding: 48px 28px;
}

.ai-loading-main {
  width: 150px;
  height: 150px;
  margin: 0 auto 24px;
  padding: 10px;
}

.ai-loading-gif-large {
  width: 130px;
  height: 130px;
}

.processing-title {
  margin: 0 0 8px;
  color: #292e45;
  font-size: 22px;
}

.status-text {
  margin: 16px 0 20px;
  color: #9aa0b2;
  font-size: 12px;
}

.view-progress-btn {
  border-color: #c9c3f6;
  border-radius: 9px;
  color: #5d50cf;
  box-shadow: none;
}

.results-pane {
  height: 620px;
}

@media (max-width: 768px) {
  .submission-hero__inner,
  .submission-shell {
    width: min(100% - 24px, 1180px);
  }

  .submission-hero__content,
  .submission-section-heading,
  .tab-actions-bar {
    align-items: stretch;
    flex-direction: column;
  }

  .submission-hero__statuses {
    justify-content: flex-start;
  }

  .tab-navigation {
    padding: 0 10px;
    overflow-x: auto;
  }

  .submission-tabs :deep(.el-tabs__item) {
    padding: 0 14px;
  }

  .tab-pane,
  .form-content-wrapper {
    padding: 16px;
  }

  .submission-pane {
    padding: 0;
  }

  .tab-actions-bar {
    padding: 14px 16px;
  }

  .actions-right {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .actions-right .submit-btn:last-child {
    grid-column: 1 / -1;
  }
}

@media (max-width: 480px) {
  .tab-label b {
    display: none;
  }
  .submission-tabs :deep(.el-tabs__item) {
    padding: 0 11px;
  }
  .results-pane {
    height: auto;
    min-height: 560px;
  }
}
</style>
