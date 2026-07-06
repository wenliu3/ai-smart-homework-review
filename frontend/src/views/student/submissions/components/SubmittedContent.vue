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
      <!-- 提交内容 -->
      <div>
        <h4 class="font-medium text-gray-900 mb-2">作业内容：</h4>
        <div
          class="prose max-w-none bg-gray-50 p-4 rounded-md"
          v-html="submission?.content"
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
.prose {
  max-width: none;
}
</style>
