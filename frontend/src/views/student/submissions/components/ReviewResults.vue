<template>
  <div style="height: 100%">
    <!-- 批改结果标签页 -->
    <el-card v-if="showReviewTabs" class="shadow-sm review-card">
      <!-- <template #header>
        <h2 class="text-lg font-semibold text-gray-900 flex items-center gap-2">
          <el-icon><Document /></el-icon>
          批改结果
        </h2>
      </template> -->

      <el-tabs v-model="activeTab" tab-position="left" class="review-tabs">
        <!-- AI批改结果标签页 -->
        <el-tab-pane name="ai" class="tab-content" :disabled="!aiReview">
          <template #label>
            <div class="tab-label">
              <el-icon><Monitor /></el-icon>
              <span>AI批改</span>
              <el-tag
                v-if="aiReview && aiReview.score"
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

          <!-- AI评价进行中 -->
          <div v-else class="no-review-content">
            <div class="ai-empty-state">
              <div class="ai-loading-container large">
                <img
                  src="@/assets/image/ai_loading.gif"
                  alt="AI正在批改"
                  class="ai-loading-gif large"
                />
              </div>
              <div class="empty-description">
                <h4 class="text-gray-700 mb-2 text-lg">🤖 AI智能评价中</h4>
                <p class="text-gray-500 mb-1">人工智能正在仔细分析您的作业</p>
                <p class="text-gray-400 text-sm">
                  评价完成后会自动显示结果，请耐心等待
                </p>
              </div>
            </div>
          </div>
        </el-tab-pane>

        <!-- 教师批改结果标签页 -->
        <el-tab-pane
          name="teacher"
          class="tab-content"
          :disabled="!teacherReview"
        >
          <template #label>
            <div class="tab-label">
              <el-icon><User /></el-icon>
              <span>教师批改</span>
              <el-tag
                v-if="teacherReview && teacherReview.score"
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
}

const props = defineProps<Props>();

const { formatDate } = useSubmissionUtils();

// 当前激活的标签页 - 默认显示AI评价
const activeTab = ref("ai");

// 是否显示批改结果标签页
const showReviewTabs = computed(() => {
  // 如果作业已提交，就显示标签页（即使还没有批改结果）
  return (
    props.submissionStatus &&
    props.submissionStatus !== "draft" &&
    props.submissionStatus !== "not_submitted"
  );
});

// 监听评价数据变化，自动切换到合适的标签页
watch(
  () => [props.aiReview, props.teacherReview],
  ([aiReview, teacherReview]) => {
    // 默认优先显示AI评价，如果没有AI评价则显示教师评价
    if (aiReview) {
      activeTab.value = "ai";
    } else if (teacherReview) {
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
    props.submissionStatus &&
    !showAiProcessingTip.value &&
    !showTeacherPendingTip.value &&
    !showOverdueTip.value
  );
});

// 格式化评价内容 - 支持高亮和彩色标记
const formatReviewContent = (content: string) => {
  if (!content) return "";

  return content
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\n/g, "<br>")
    // 总分高亮：总分：XX分 → 红色大字
    .replace(/(总分[：:]\s*\d+\s*分)/g, '<span style="color:#e53e3e;font-size:1.3em;font-weight:bold">$1</span>')
    // 分数/XX → 加粗
    .replace(/(\d+)\s*\/\s*(\d+)(\s*分)/g, '<strong style="color:#e53e3e">$1/$2$3</strong>')
    // 加粗
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    // 蓝色高亮
    .replace(/~~(.*?)~~/g, '<span style="color:#2563eb;font-weight:600">$1</span>')
    // 绿色优点
    .replace(/✅\s*优点/g, '<span style="color:#16a34a;font-weight:bold;font-size:1.1em">✅ 优点</span>')
    .replace(/✅\s*(.+?)(?=<br>|<div>|$)/g, '<div style="color:#16a34a;padding-left:8px">✅ $1</div>')
    // 橙色建议
    .replace(/📝\s*改进建议/g, '<span style="color:#ea580c;font-weight:bold;font-size:1.1em">📝 改进建议</span>')
    .replace(/📝\s*(.+?)(?=<br>|<div>|$)/g, '<div style="color:#ea580c;padding-left:8px">📝 $1</div>')
    // 评分维度加粗
    .replace(/(\d+[.、]\s*(?:内容|结构|语言|语法|词汇|表达|论证|逻辑|计算|规范|创意|准确|完整|组织|步骤).*?)(?=<br>|<div>|$)/g, '<strong style="color:#1e40af">$1</strong>')
    // 斜体
    .replace(/\*(.*?)\*/g, "<em>$1</em>")
    // 统计信息
    .replace(/📊\s*(.+?)(?=<br>|<div>|$)/g, '<div style="background:#f0f9ff;padding:4px 8px;border-radius:4px;margin:4px 0">📊 $1</div>');
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

/* 标签页样式 - 实现左侧固定，右侧滚动 */
.review-tabs {
  height: 100%;
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
  background: #3b82f6;
  color: white;
  box-shadow: 0 2px 8px rgba(59, 130, 246, 0.3);
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
  border-left: 3px solid #3b82f6;
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
