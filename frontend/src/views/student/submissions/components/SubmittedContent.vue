<template>
  <el-card class="shadow-sm">
    <template #header>
      <div class="flex items-center justify-between">
        <h2 class="text-lg font-semibold text-gray-900">我的提交</h2>
        <div class="text-sm text-gray-500">
          提交时间：{{ formatDate(submission?.submittedAt) }}
        </div>
      </div>
    </template>

    <div class="space-y-4">
      <!-- 作业文本内容 -->
      <div v-if="submission?.content" class="content-section">
        <h4 class="font-medium text-gray-900 mb-2">作业内容：</h4>
        <div
          class="prose prose-sm max-w-none text-gray-700 submission-content"
          v-html="submission.content"
        ></div>
      </div>

      <!-- 附件列表 -->
      <div v-if="submission?.attachments?.length">
        <h4 class="font-medium text-gray-900 mb-2">附件：</h4>
        <div class="flex flex-wrap gap-2">
          <el-tag
            v-for="file in submission.attachments"
            :key="file.fileName"
            type="info"
            effect="plain"
            class="cursor-pointer"
            @click="downloadFile(file)"
          >
            <el-icon><Paperclip /></el-icon>
            {{ file.fileName }}
            <span class="text-xs ml-1"
              >({{ formatFileSize(file.fileSize) }})</span
            >
          </el-tag>
        </div>
      </div>

      <!-- 无内容提示 -->
      <div
        v-if="!submission?.content && !submission?.attachments?.length"
        class="text-center text-gray-400 py-8"
      >
        暂无提交内容
      </div>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { Paperclip } from "@element-plus/icons-vue";
import type { Submission } from "../../../../api/submissions";
import { useSubmissionUtils } from "../composables";

interface Props {
  submission?: Submission | null;
}

defineProps<Props>();

const { formatDate, formatFileSize, downloadFile } = useSubmissionUtils();

defineOptions({
  name: "SubmittedContent",
});
</script>

<style scoped>
.content-section {
  padding: 1rem;
  background: #f9fafb;
  border-radius: 8px;
  border: 1px solid #f0f0f0;
}

.submission-content {
  line-height: 1.8;
}

.submission-content :deep(img) {
  max-width: 100%;
  border-radius: 6px;
}

.submission-content :deep(p) {
  margin: 0.5rem 0;
}

.prose {
  max-width: none;
}
</style>
