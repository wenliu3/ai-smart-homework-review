<template>
  <div style="height: 100%">
    <!-- 批改结果标签页 -->
    <el-card v-if="showReviewTabs" class="shadow-sm review-card">
      <div class="review-overview">
        <div
          class="review-overview__score"
          :class="{ 'is-pending': displayScore === null }"
        >
          <strong>{{ displayScore ?? "--" }}</strong>
          <span>/ 100</span>
        </div>
        <div class="review-overview__copy">
          <p>REVIEW SUMMARY</p>
          <h2>{{ overviewTitle }}</h2>
          <span>{{ overviewSubtitle }}</span>
        </div>
      </div>

      <el-tabs v-model="activeTab" tab-position="left" class="review-tabs">
        <!-- AI批改结果标签页 -->
        <el-tab-pane
          v-if="aiSupported || aiReview"
          name="ai"
          class="tab-content"
          :disabled="!aiReview"
        >
          <template #label>
            <div class="tab-label">
              <el-icon><Monitor /></el-icon>
              <span>AI批改</span>
              <el-tag
                v-if="runFailed"
                type="danger"
                size="small"
                class="ml-2"
                effect="plain"
              >
                失败
              </el-tag>
              <el-tag
                v-else-if="runCancelled"
                type="info"
                size="small"
                class="ml-2"
                effect="plain"
              >
                已取消
              </el-tag>
              <el-tag
                v-else-if="aiReview && typeof aiReview.score === 'number'"
                type="primary"
                size="small"
                class="ml-2"
              >
                {{ aiReview.score }}分
              </el-tag>
              <el-tag
                v-else-if="!aiReview"
                type="info"
                size="small"
                class="ml-2"
                effect="plain"
              >
                评价中
              </el-tag>
            </div>
          </template>

          <!-- 🔥 AI评价错误状态 -->
          <div v-if="aiReview?.aiReviewMetadata?.error" class="review-error">
            <el-alert
              title="AI评价失败"
              :description="aiReview.aiReviewMetadata.error"
              type="error"
              show-icon
              :closable="false"
            >
              <template #default>
                <div class="error-details">
                  <p class="mb-2">{{ aiReview.aiReviewMetadata.error }}</p>
                  <p
                    class="text-sm text-gray-500"
                    v-if="aiReview.aiReviewMetadata.errorTime"
                  >
                    失败时间：{{
                      formatDate(aiReview.aiReviewMetadata.errorTime)
                    }}
                  </p>
                  <p
                    class="text-sm text-gray-500"
                    v-if="aiReview.aiReviewMetadata.modelUsed"
                  >
                    使用模型：{{ aiReview.aiReviewMetadata.modelUsed }}
                  </p>
                </div>
              </template>
            </el-alert>
          </div>

          <!-- AI评价成功内容 -->
          <div v-else-if="aiReview && aiReview.content" class="review-content">
            <div class="review-meta mb-4">
              <div class="text-sm text-gray-500">
                批改时间：{{ formatDate(aiReview.reviewedAt) }}
              </div>
            </div>
            <div class="review-content-scroll">
              <div
                class="prose max-w-none whitespace-pre-wrap"
                v-html="formatReviewContent(aiReview.content)"
              ></div>
            </div>
          </div>

          <!-- 🔥 AI批改 Run 失败终态 -->
          <div v-else-if="runFailed" class="no-review-content">
            <div class="ai-empty-state">
              <div class="empty-description">
                <h4 class="text-gray-700 mb-2 text-lg">AI 批改失败</h4>
                <p class="text-gray-500 mb-1">等待教师人工批改</p>
                <p class="text-gray-400 text-sm">
                  本次 AI 自动批改未完成，教师将为您进行人工批改，请耐心等待
                </p>
              </div>
            </div>
          </div>

          <!-- 🔥 AI批改 Run 取消终态 -->
          <div v-else-if="runCancelled" class="no-review-content">
            <div class="ai-empty-state">
              <div class="empty-description">
                <h4 class="text-gray-700 mb-2 text-lg">AI 批改已取消</h4>
                <p class="text-gray-500 mb-1">等待教师人工批改</p>
                <p class="text-gray-400 text-sm">
                  AI 自动批改已取消，教师将为您进行人工批改
                </p>
              </div>
            </div>
          </div>

          <!-- AI评价进行中 / 未取得终态 -->
          <div v-else class="no-review-content">
            <div class="ai-empty-state">
              <template v-if="isPolling">
                <div class="ai-loading-container large">
                  <img
                    src="@/assets/image/ai_loading.gif"
                    alt="AI正在批改"
                    class="ai-loading-gif large"
                  />
                </div>
                <div class="empty-description">
                  <h4 class="text-gray-700 mb-2 text-lg">AI 智能评价中</h4>
                  <p class="text-gray-500 mb-1">人工智能正在仔细分析您的作业</p>
                  <p class="text-gray-400 text-sm">
                    评价完成后会自动显示结果，请耐心等待
                  </p>
                  <p
                    v-if="isPolling"
                    class="text-gray-400 text-sm"
                    data-testid="grading-progress"
                  >
                    正在查询批改进度（第 {{ pollingCount || 0 }} 次）…
                  </p>
                </div>
              </template>
              <template v-else>
                <div class="empty-description">
                  <h4 class="text-gray-700 mb-2 text-lg">
                    暂未取得最终状态，请稍后刷新
                  </h4>
                  <p class="text-gray-500 mb-1">
                    AI 批改仍在进行或暂时无法获取进度
                  </p>
                  <p class="text-gray-400 text-sm">
                    请稍后刷新页面查看最新结果
                  </p>
                </div>
              </template>
            </div>
          </div>
        </el-tab-pane>

        <!-- 教师批改结果标签页 -->
        <el-tab-pane
          name="teacher"
          class="tab-content"
          :disabled="!teacherReview && !waitingForTeacherOnly"
        >
          <template #label>
            <div class="tab-label">
              <el-icon><User /></el-icon>
              <span>教师批改</span>
              <el-tag
                v-if="teacherReview && typeof teacherReview.score === 'number'"
                type="success"
                size="small"
                class="ml-2"
              >
                {{ teacherReview.score }}分
              </el-tag>
              <el-tag
                v-else-if="!teacherReview"
                type="warning"
                size="small"
                class="ml-2"
                effect="plain"
              >
                待批改
              </el-tag>
            </div>
          </template>

          <div v-if="teacherReview" class="review-content">
            <div class="review-meta mb-4">
              <div class="text-sm text-gray-500">
                批改时间：{{ formatDate(teacherReview.reviewedAt) }}
              </div>
            </div>
            <div class="review-content-scroll">
              <div
                class="prose max-w-none whitespace-pre-wrap"
                v-html="formatReviewContent(teacherReview.content)"
              ></div>
            </div>
          </div>
          <div v-else class="no-review-content">
            <el-empty description="等待教师批改" :image-size="80">
              <template #description>
                <div class="empty-description">
                  <p class="text-gray-500 mb-2">教师还没有批改这份作业</p>
                  <p class="text-gray-400 text-sm">
                    请耐心等待老师的评价和打分
                  </p>
                </div>
              </template>
            </el-empty>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 提示信息 - 只在不显示标签页时显示 -->
    <template v-if="!showReviewTabs">
      <el-card
        v-if="isPreSubmission"
        data-testid="no-submission-review"
        class="review-empty-card"
      >
        <div class="review-empty-state">
          <span class="review-empty-state__icon">
            <el-icon><Document /></el-icon>
          </span>
          <p class="student-eyebrow">REVIEW RESULT</p>
          <h3>评价结果将在提交后显示</h3>
          <p>完成并提交作业后，可在这里查看 AI 评价、教师反馈和最终得分。</p>
        </div>
      </el-card>

      <!-- 教师尚未打分提示 -->
      <el-card v-if="showTeacherPendingTip" class="shadow-sm border-orange-200">
        <div class="flex items-center gap-3 text-orange-600">
          <el-icon><Clock /></el-icon>
          <span class="text-sm">老师尚未打分，请耐心等待...</span>
        </div>
      </el-card>

      <!-- 作业过期提示 -->
      <el-card v-if="showOverdueTip" class="shadow-sm border-orange-200">
        <div class="flex items-center gap-3 text-orange-600">
          <el-icon><Clock /></el-icon>
          <span class="text-sm"
            >作业已过期，不支持AI智能评价。请等待老师人工批改。</span
          >
        </div>
      </el-card>

      <!-- 无评价结果提示 -->
      <el-card v-if="showNoReviewTip" class="shadow-sm border-gray-200">
        <div class="flex items-center gap-3 text-gray-500">
          <el-icon><InfoFilled /></el-icon>
          <span class="text-sm">作业尚未批改，请等待AI或老师评价</span>
        </div>
      </el-card>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import {
  Monitor,
  User,
  Loading,
  Clock,
  InfoFilled,
  Document,
} from "@element-plus/icons-vue";
import type { AiReview, TeacherReview } from "../../../../api/submissions";
import { useSubmissionUtils } from "../composables";
import { checkAiSupport } from "../../../../config/ai-config";

interface Props {
  aiReview?: AiReview | null;
  teacherReview?: TeacherReview | null;
  submissionStatus?: string;
  assignment?: any;
  isPolling?: boolean;
  pollingCount?: number;
  /** 批改 Run 终态摘要（只读）：failed/cancelled 为真实终态。 */
  gradingRun?: {
    status?: string | null;
    errorCode?: string | null;
    finalOutput?: string | null;
  } | null;
}

const props = defineProps<Props>();

const { formatDate } = useSubmissionUtils();

const displayScore = computed<number | null>(() => {
  if (typeof props.teacherReview?.score === "number") {
    return props.teacherReview.score;
  }
  if (typeof props.aiReview?.score === "number") {
    return props.aiReview.score;
  }
  return null;
});

const displaySource = computed(() =>
  typeof props.teacherReview?.score === "number" ? "教师" : "AI"
);

const isPreSubmission = computed(
  () =>
    !props.submissionStatus ||
    props.submissionStatus === "draft" ||
    props.submissionStatus === "not_submitted"
);

const aiSupported = computed(() =>
  props.assignment ? checkAiSupport(props.assignment).supported : true
);

const waitingForTeacherOnly = computed(
  () =>
    !isPreSubmission.value &&
    !aiSupported.value &&
    !props.aiReview &&
    !props.teacherReview
);

// 批改 Run 终态：failed/cancelled 均为真实终态，优先于进行中状态展示
const runFailed = computed(() => props.gradingRun?.status === "failed");
const runCancelled = computed(() => props.gradingRun?.status === "cancelled");

// 评价摘要标题（优先级：教师结果 > AI 结果 > Run 失败/取消 > 进行中）
const overviewTitle = computed(() => {
  if (displayScore.value !== null) return "本次作业评价";
  if (runFailed.value) return "AI 批改失败";
  if (runCancelled.value) return "AI 批改已取消";
  if (waitingForTeacherOnly.value) return "等待教师批改";
  if (props.isPolling) return "评价进行中";
  // 轮询已停止且仍未取得结果：不再继续写“评价中”
  return "暂未取得最终状态，请稍后刷新";
});

const overviewSubtitle = computed(() => {
  if (displayScore.value !== null) {
    return `${displaySource.value}已给出评价，可切换标签查看详细反馈`;
  }
  if (waitingForTeacherOnly.value) {
    return "本作业未启用 AI 评价，教师批改后将在这里显示反馈";
  }
  if (runFailed.value || runCancelled.value) {
    return "AI 批改出现问题，教师批改后将在这里显示反馈";
  }
  if (props.isPolling) {
    return "评价完成后将在这里显示得分与改进建议";
  }
  return "AI 批改暂未完成，请稍后刷新页面查看最新状态";
});

// 当前激活的标签页 - 默认显示AI评价
const activeTab = ref("ai");

// 是否显示批改结果标签页
const showReviewTabs = computed(() => {
  // 如果作业已提交，就显示标签页（即使还没有批改结果）
  return !isPreSubmission.value;
});

// 监听评价数据变化，自动切换到合适的标签页
watch(
  () => [props.aiReview, props.teacherReview, aiSupported.value],
  ([aiReview, teacherReview, supportsAi]) => {
    // 默认优先显示AI评价，如果没有AI评价则显示教师评价
    if (aiReview) {
      activeTab.value = "ai";
    } else if (teacherReview || !supportsAi) {
      activeTab.value = "teacher";
    } else {
      // 如果都没有，默认显示AI标签页
      activeTab.value = "ai";
    }
  },
  { immediate: true }
);

// 显示AI处理中提示（已删除导航条，保留逻辑用于其他判断）
const showAiProcessingTip = computed(() => {
  return false; // 不再显示顶部AI处理提示条
});

// 显示教师待评价提示
const showTeacherPendingTip = computed(() => {
  return props.submissionStatus === "ai_reviewed" && !props.teacherReview;
});

// 显示无评价结果提示
// 显示作业过期提示
const showOverdueTip = computed(() => {
  // 如果已经有AI评价或教师评价，不显示过期提示
  if (props.aiReview || props.teacherReview) {
    return false;
  }

  // 如果已经在显示AI处理提示，不显示过期提示
  if (showAiProcessingTip.value) {
    return false;
  }

  // 检查作业是否过期
  if (props.assignment && props.submissionStatus === "submitted") {
    const aiSupport = checkAiSupport(props.assignment);
    return !aiSupport.supported && aiSupport.reason.includes("过期");
  }

  return false;
});

const showNoReviewTip = computed(() => {
  return (
    !props.aiReview &&
    !props.teacherReview &&
    !isPreSubmission.value &&
    !showAiProcessingTip.value &&
    !showTeacherPendingTip.value &&
    !showOverdueTip.value
  );
});

// 格式化评价内容 - 支持高亮和彩色标记
const formatReviewContent = (content: string) => {
  if (!content) return "";

  return (
    content
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\n/g, "<br>")
      // 总分高亮：总分：XX分 → 红色大字
      .replace(
        /(总分[：:]\s*\d+\s*分)/g,
        '<span style="color:#e53e3e;font-size:1.3em;font-weight:bold">$1</span>'
      )
      // 分数/XX → 加粗
      .replace(
        /(\d+)\s*\/\s*(\d+)(\s*分)/g,
        '<strong style="color:#e53e3e">$1/$2$3</strong>'
      )
      // 加粗
      .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
      // 蓝色高亮
      .replace(
        /~~(.*?)~~/g,
        '<span style="color:#2563eb;font-weight:600">$1</span>'
      )
      // 绿色优点
      .replace(
        /✅\s*优点/g,
        '<span style="color:#16a34a;font-weight:bold;font-size:1.1em">✅ 优点</span>'
      )
      .replace(
        /✅\s*(.+?)(?=<br>|<div>|$)/g,
        '<div style="color:#16a34a;padding-left:8px">✅ $1</div>'
      )
      // 橙色建议
      .replace(
        /📝\s*改进建议/g,
        '<span style="color:#ea580c;font-weight:bold;font-size:1.1em">📝 改进建议</span>'
      )
      .replace(
        /📝\s*(.+?)(?=<br>|<div>|$)/g,
        '<div style="color:#ea580c;padding-left:8px">📝 $1</div>'
      )
      // 评分维度加粗
      .replace(
        /(\d+[.、]\s*(?:内容|结构|语言|语法|词汇|表达|论证|逻辑|计算|规范|创意|准确|完整|组织|步骤).*?)(?=<br>|<div>|$)/g,
        '<strong style="color:#1e40af">$1</strong>'
      )
      // 斜体
      .replace(/\*(.*?)\*/g, "<em>$1</em>")
      // 统计信息
      .replace(
        /📊\s*(.+?)(?=<br>|<div>|$)/g,
        '<div style="background:#f0f9ff;padding:4px 8px;border-radius:4px;margin:4px 0">📊 $1</div>'
      )
  );
};

defineOptions({
  name: "ReviewResults",
});
</script>

<style scoped>
.prose {
  max-width: none;
}

/* 组件根容器 */
.review-card {
  height: 100%;
  overflow: hidden;
}

.review-card :deep(.el-card__body) {
  height: 100%;
  padding: 0;
  overflow: hidden;
}

.review-empty-card {
  height: 100%;
  border-color: #e8eaf2;
  border-radius: 15px;
  box-shadow: 0 8px 26px rgba(36, 40, 68, 0.05);
}

.review-empty-card :deep(.el-card__body) {
  display: grid;
  min-height: 420px;
  place-items: center;
}

.review-empty-state {
  max-width: 440px;
  padding: 36px 24px;
  text-align: center;
}

.review-empty-state__icon {
  display: inline-flex;
  width: 58px;
  height: 58px;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
  border-radius: 16px;
  background: #efedff;
  color: #6558d9;
}

.review-empty-state__icon :deep(svg) {
  width: 26px;
}

.review-empty-state .student-eyebrow {
  margin: 0 0 5px;
  color: #6b5ed6;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.12em;
}

.review-empty-state h3 {
  margin: 0;
  color: #2d3248;
  font-size: 19px;
}

.review-empty-state > p:last-child {
  margin: 9px 0 0;
  color: #8e95a8;
  font-size: 13px;
  line-height: 1.7;
}

.review-overview {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  gap: 18px;
  padding: 20px 24px;
  border-bottom: 1px solid #e9eaf1;
  background: linear-gradient(120deg, #f3f1ff, #f8f7ff 60%, #edf7ff);
}

.review-overview__score {
  display: flex;
  width: 102px;
  height: 76px;
  flex: 0 0 102px;
  align-items: baseline;
  justify-content: center;
  padding-top: 12px;
  border: 1px solid rgba(101, 88, 217, 0.16);
  border-radius: 14px;
  background: #fff;
  color: #5d50ce;
  box-shadow: 0 9px 24px rgba(80, 68, 161, 0.09);
}

.review-overview__score strong {
  font-size: 34px;
  line-height: 1;
}

.review-overview__score span {
  margin-left: 4px;
  color: #9a9fb0;
  font-size: 11px;
}

.review-overview__score.is-pending {
  color: #9da3b4;
}

.review-overview__copy p {
  margin: 0 0 4px;
  color: #7063d8;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.12em;
}

.review-overview__copy h2 {
  margin: 0;
  color: #282d43;
  font-size: 19px;
}

.review-overview__copy span {
  display: block;
  margin-top: 6px;
  color: #8c93a7;
  font-size: 12px;
}

/* 标签页样式 - 实现左侧固定，右侧滚动 */
.review-tabs {
  height: calc(100% - 117px);
  display: flex;
}

.review-tabs :deep(.el-tabs__header) {
  margin: 0;
  width: 200px;
  flex-shrink: 0;
  height: 100%;
  background: #f8fafc;
  border-radius: 0;
  border-right: 1px solid #e5e7eb;
}

.review-tabs :deep(.el-tabs__nav-wrap) {
  height: 100%;
  background: transparent;
  border-radius: 0;
  padding: 16px 0;
}

.review-tabs :deep(.el-tabs__nav-scroll) {
  height: 100%;
  background: transparent;
}

.review-tabs :deep(.el-tabs__nav) {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.review-tabs :deep(.el-tabs__item) {
  padding: 12px 20px !important;
  margin: 4px 8px;
  border-radius: 6px;
  transition: all 0.3s ease;
  border: none !important;
  background: transparent;
  color: #6b7280;
  font-weight: 500;
  height: auto;
  line-height: 1.4;
}

.review-tabs :deep(.el-tabs__item.is-active) {
  background: linear-gradient(135deg, #695ddd, #594bc8);
  color: white;
  box-shadow: 0 5px 14px rgba(90, 75, 199, 0.23);
}

.review-tabs :deep(.el-tabs__item:hover:not(.is-active):not(.is-disabled)) {
  background: #e5e7eb;
  color: #374151;
}

.review-tabs :deep(.el-tabs__item.is-disabled) {
  background: #f3f4f6;
  color: #9ca3af;
  cursor: not-allowed;
  opacity: 0.6;
}

.review-tabs :deep(.el-tabs__content) {
  flex: 1;
  height: 100%;
  overflow: hidden;
  padding: 0;
  background: #ffffff;
}

.review-tabs :deep(.el-tab-pane) {
  height: 100%;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.review-tabs :deep(.el-tabs__active-bar) {
  display: none;
}

/* 标签页标签样式 */
.tab-label {
  display: flex;
  align-items: center;
  gap: 8px;
  white-space: nowrap;
  min-width: 120px;
  width: 100%;
}

.tab-label .el-icon {
  font-size: 16px;
}

.tab-label .el-tag {
  font-weight: 600;
  font-family: "SF Mono", "Monaco", "Inconsolata", "Roboto Mono", monospace;
}

/* 标签页内容样式 */
.tab-content {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.review-content {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 24px;
  overflow: hidden;
}

.review-meta {
  flex-shrink: 0;
  padding: 12px 16px;
  background: #f8fafc;
  border-radius: 6px;
  border-left: 3px solid #6558d9;
  margin-bottom: 16px;
}

.review-content-scroll {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding-right: 8px;
  margin-right: -8px;
}

/* 自定义滚动条样式 */
.review-content-scroll::-webkit-scrollbar {
  width: 6px;
}

.review-content-scroll::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 3px;
}

.review-content-scroll::-webkit-scrollbar-thumb {
  background: #c1c1c1;
  border-radius: 3px;
}

.review-content-scroll::-webkit-scrollbar-thumb:hover {
  background: #a8a8a8;
}

.no-review-content {
  flex: 1;
  display: flex;
  justify-content: center;
  align-items: center;
  color: #9ca3af;
  padding: 24px;
}

.empty-description {
  text-align: center;
  line-height: 1.6;
}

.empty-description p {
  margin: 0;
}

/* AI Loading样式 */
.ai-loading-container.large {
  width: 80px;
  height: 80px;
  border-radius: 16px;
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(59, 130, 246, 0.1);
}

.ai-loading-gif.large {
  width: 64px;
  height: 64px;
  border-radius: 12px;
  object-fit: cover;
}

.ai-empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 40px 20px;
  height: 100%;
}

.empty-description h4 {
  margin: 0;
  font-weight: 600;
}

.empty-description p {
  margin: 4px 0;
  line-height: 1.5;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .review-tabs :deep(.el-tabs__header) {
    width: 140px;
  }

  .review-tabs :deep(.el-tabs__nav-wrap) {
    padding: 8px 0;
  }

  .review-tabs :deep(.el-tabs__item) {
    padding: 8px 12px !important;
    margin: 2px 4px;
    font-size: 13px;
  }

  .review-content {
    padding: 16px;
  }

  .tab-label {
    min-width: 100px;
    font-size: 13px;
  }

  .tab-label .el-icon {
    font-size: 14px;
  }
}

@media (max-width: 480px) {
  .review-overview {
    align-items: flex-start;
    padding: 16px;
  }

  .review-overview__score {
    width: 82px;
    height: 68px;
    flex-basis: 82px;
  }

  .review-overview__score strong {
    font-size: 28px;
  }

  .review-tabs {
    flex-direction: column;
    height: auto;
  }

  .review-tabs :deep(.el-tabs__header) {
    width: 100%;
    height: auto;
    border-right: none;
    border-bottom: 1px solid #e5e7eb;
  }

  .review-tabs :deep(.el-tabs__nav-wrap) {
    height: auto;
    padding: 8px 16px;
  }

  .review-tabs :deep(.el-tabs__nav) {
    height: auto;
    flex-direction: row;
    justify-content: space-around;
  }

  .review-tabs :deep(.el-tabs__content) {
    height: 400px;
  }

  .tab-label {
    min-width: auto;
    justify-content: center;
  }
}
</style>
