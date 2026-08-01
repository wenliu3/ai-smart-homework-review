<template>
  <el-dialog
    :model-value="modelValue"
    title="作业内容"
    width="min(800px, 92vw)"
    class="assignment-content-preview-dialog"
    destroy-on-close
    append-to-body
    @update:model-value="emit('update:modelValue', $event)"
  >
    <div v-if="assignmentDetail" class="preview-content">
      <div class="preview-title-row">
        <h2>{{ assignmentDetail.title }}</h2>
        <el-tag :type="statusType" effect="light">
          {{ statusText }}
        </el-tag>
      </div>

      <div class="metadata-grid">
        <div class="metadata-item">
          <span class="metadata-label">关联班级</span>
          <div v-if="assignmentDetail.classes?.length" class="class-list">
            <el-tag
              v-for="classItem in assignmentDetail.classes"
              :key="classItem.id"
              size="small"
            >
              {{ classItem.name }}
            </el-tag>
          </div>
          <span v-else class="metadata-value muted">暂无关联班级</span>
        </div>
        <div class="metadata-item">
          <span class="metadata-label">开始时间</span>
          <span class="metadata-value">
            {{ formatDateTime(assignmentDetail.startDate) }}
          </span>
        </div>
        <div class="metadata-item">
          <span class="metadata-label">截止时间</span>
          <span class="metadata-value">
            {{ formatDateTime(assignmentDetail.endDate) }}
          </span>
        </div>
      </div>

      <section class="content-section">
        <h3>作业要求</h3>
        <div
          v-if="sanitizedDescription"
          class="assignment-description editor-content-view"
          v-html="sanitizedDescription"
        ></div>
        <div v-else class="empty-state">暂无作业要求</div>
      </section>

      <section class="content-section">
        <div class="section-heading">
          <h3>作业附件</h3>
          <span v-if="assignmentDetail.attachments?.length" class="file-count">
            共 {{ assignmentDetail.attachments.length }} 个文件
          </span>
        </div>

        <div
          v-if="assignmentDetail.attachments?.length"
          class="attachment-list"
        >
          <div
            v-for="attachment in assignmentDetail.attachments"
            :key="attachment.fileUrl || attachment.fileName"
            class="attachment-item"
          >
            <el-icon class="attachment-icon"><Document /></el-icon>
            <div class="attachment-info">
              <span class="attachment-name">{{ attachment.fileName }}</span>
              <span class="attachment-size">
                {{ formatFileSize(attachment.fileSize) }}
              </span>
            </div>
            <el-button
              type="primary"
              link
              :icon="Download"
              :disabled="!attachment.fileUrl"
              @click="downloadAttachment(attachment)"
            >
              下载
            </el-button>
          </div>
        </div>
        <div v-else class="empty-state">暂无作业附件</div>
      </section>
    </div>

    <template #footer>
      <el-button data-testid="close-preview" @click="closeDialog">
        关闭
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed } from "vue";
import DOMPurify from "dompurify";
import moment from "moment";
import { Document, Download } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";

import type { AssignmentDetail } from "@/api/assignments";

type AssignmentAttachment = NonNullable<
  AssignmentDetail["attachments"]
>[number];

interface Props {
  modelValue: boolean;
  assignmentDetail: AssignmentDetail | null;
}

interface Emits {
  (e: "update:modelValue", value: boolean): void;
}

const props = defineProps<Props>();
const emit = defineEmits<Emits>();

const sanitizedDescription = computed(() =>
  DOMPurify.sanitize(props.assignmentDetail?.description || "", {
    USE_PROFILES: { html: true },
  })
);

const statusText = computed(() => {
  switch (props.assignmentDetail?.status) {
    case "draft":
      return "草稿";
    case "published":
      return "已发布";
    case "terminated":
      return "已终止";
    default:
      return "未知";
  }
});

const statusType = computed(() => {
  switch (props.assignmentDetail?.status) {
    case "published":
      return "success";
    case "terminated":
      return "warning";
    default:
      return "info";
  }
});

const formatDateTime = (dateTime?: string) => {
  if (!dateTime) return "-";
  return moment(dateTime).format("YYYY年MM月DD日 HH:mm");
};

const formatFileSize = (size?: number) => {
  if (!size || size <= 0) return "0 B";
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) {
    return `${Math.round(size / 1024)} KB`;
  }
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
};

const closeDialog = () => emit("update:modelValue", false);

const downloadAttachment = async (attachment: AssignmentAttachment) => {
  if (!attachment.fileUrl) {
    ElMessage.warning("附件地址无效");
    return;
  }

  const filename = attachment.fileUrl.split("/uploads/").pop();
  if (!filename) {
    ElMessage.warning("附件地址无效");
    return;
  }

  try {
    const token = localStorage.getItem("token");
    const response = await fetch(
      `/api/upload/download/${encodeURIComponent(filename)}`,
      {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      }
    );
    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = attachment.fileName || filename;
    link.click();
    URL.revokeObjectURL(url);
  } catch (error) {
    console.error("下载作业附件失败", error);
    ElMessage.warning("附件下载失败");
  }
};

defineOptions({
  name: "AssignmentContentPreviewDialog",
});
</script>

<style scoped>
.preview-content {
  color: #1f2937;
}

.preview-title-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding-bottom: 18px;
  border-bottom: 1px solid #e5e7eb;
}

.preview-title-row h2 {
  margin: 0;
  font-size: 22px;
  line-height: 1.4;
}

.metadata-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
  padding: 18px 0;
  border-bottom: 1px solid #e5e7eb;
}

.metadata-item:first-child {
  grid-column: 1 / -1;
}

.metadata-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.metadata-label {
  color: #6b7280;
  font-size: 13px;
}

.metadata-value {
  font-size: 14px;
  font-weight: 500;
}

.muted,
.empty-state {
  color: #9ca3af;
}

.class-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.content-section {
  padding-top: 20px;
}

.content-section h3 {
  margin: 0 0 12px;
  font-size: 16px;
}

.section-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.file-count {
  color: #9ca3af;
  font-size: 13px;
}

.assignment-description.editor-content-view {
  min-height: 48px;
  margin: 0;
  padding: 0;
  overflow-x: visible;
  overflow-wrap: anywhere;
  border: 0;
  border-radius: 0;
}

.assignment-description :deep(img) {
  max-width: 100%;
  height: auto;
}

.assignment-description :deep(pre) {
  max-width: 100%;
  overflow-x: auto;
}

.empty-state {
  padding: 24px;
  text-align: center;
  background: #f8fafc;
  border: 1px dashed #dbe3ee;
  border-radius: 8px;
}

.attachment-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.attachment-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  background: #f8fafc;
  border: 1px solid #eef2f7;
  border-radius: 8px;
}

.attachment-icon {
  color: #409eff;
  font-size: 20px;
}

.attachment-info {
  display: flex;
  flex: 1;
  min-width: 0;
  flex-direction: column;
  gap: 3px;
}

.attachment-name {
  overflow: hidden;
  font-size: 14px;
  font-weight: 500;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.attachment-size {
  color: #9ca3af;
  font-size: 12px;
}

:deep(.assignment-content-preview-dialog) {
  max-width: 92vw;
  margin-top: 8vh;
}

:deep(.assignment-content-preview-dialog .el-dialog__body) {
  max-height: calc(80vh - 130px);
  overflow-y: auto;
}

@media (max-width: 640px) {
  .metadata-grid {
    grid-template-columns: 1fr;
  }

  .metadata-item:first-child {
    grid-column: auto;
  }

  .preview-title-row h2 {
    font-size: 19px;
  }
}
</style>
