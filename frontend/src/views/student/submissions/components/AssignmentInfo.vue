<template>
  <div class="form-section">
    <div class="section-content">
      <div class="space-y-4">
        <div>
          <div
            ref="descriptionRef"
            class="prose max-w-none text-gray-700 transition-all duration-300"
            :class="{ 'line-clamp-3': !isExpanded && shouldShowToggle }"
            v-html="assignment.description"
          ></div>

          <!-- 展开/收起按钮 - 放在内容底部 -->
          <div v-if="shouldShowToggle" class="flex justify-center mt-3">
            <el-button
              link
              type="primary"
              :icon="isExpanded ? ArrowUp : ArrowDown"
              @click="toggleExpanded"
              class="!text-sm"
            >
              {{ isExpanded ? "收起" : "展开全部" }}
            </el-button>
          </div>
        </div>

        <div class="flex items-center gap-6 text-sm text-gray-600">
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
import { ref, onMounted, nextTick, watch } from "vue";
import {
  Clock,
  Star,
  Warning,
  User,
  ArrowUp,
  ArrowDown,
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

// 折叠状态
const isExpanded = ref(false);
const descriptionRef = ref();
const shouldShowToggle = ref(false);

// 检测内容是否超过3行
const checkContentHeight = async () => {
  await nextTick();
  if (!descriptionRef.value) return;

  // 创建一个临时元素来测量内容高度
  const tempElement = descriptionRef.value.cloneNode(true);
  tempElement.style.position = "absolute";
  tempElement.style.visibility = "hidden";
  tempElement.style.height = "auto";
  tempElement.style.maxHeight = "none";
  tempElement.style.overflow = "visible";
  tempElement.className = tempElement.className.replace(/line-clamp-\d+/g, "");

  document.body.appendChild(tempElement);

  // 计算3行的高度（假设行高为1.5em，字体大小为14px）
  const lineHeight = 24; // 约1.5 * 16px
  const maxHeight = lineHeight * 3;

  const actualHeight = tempElement.scrollHeight;
  shouldShowToggle.value = actualHeight > maxHeight;

  document.body.removeChild(tempElement);
};

// 切换展开/收起
const toggleExpanded = () => {
  isExpanded.value = !isExpanded.value;
};

// 监听assignment内容变化
watch(
  () => props.assignment.description,
  () => {
    checkContentHeight();
  },
  { immediate: true }
);

onMounted(() => {
  checkContentHeight();
});

defineOptions({
  name: "AssignmentInfo",
});
</script>

<style scoped>
/* 表单分区样式 */
.form-section {
  border-bottom: 1px solid #f0f2f5;
  padding: 20px;
}

.section-header {
  padding: 20px 24px 16px;
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
  border-bottom: 1px solid #e5e7eb;
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  color: #1f2937;
  margin: 0;
  display: flex;
  align-items: center;
}

.section-title::before {
  content: "";
  width: 4px;
  height: 16px;
  background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%);
  margin-right: 12px;
  border-radius: 2px;
}

.section-content {
  /* padding: 24px; */
}
</style>

<style scoped>
.prose {
  max-width: none;
}

/* 行数限制样式 */
.line-clamp-3 {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
