<template>
  <el-dialog
    :model-value="modelValue"
    width="min(880px, 92vw)"
    class="assignment-content-preview-dialog"
    modal-class="assignment-content-preview-overlay"
    :show-close="false"
    destroy-on-close
    append-to-body
    aria-label="作业内容"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <template #header>
      <div class="preview-dialog-header">
        <div class="preview-dialog-heading">
          <span class="preview-kicker">
            <el-icon><Reading /></el-icon>
            作业内容
          </span>
          <h2 class="preview-dialog-title">
            {{ assignmentDetail?.title || "作业详情" }}
          </h2>
          <div class="preview-class-list">
            <el-icon><User /></el-icon>
            <template v-if="assignmentDetail?.classes?.length">
              <span
                v-for="classItem in assignmentDetail.classes"
                :key="classItem.id"
              >
                {{ classItem.name }}
              </span>
            </template>
            <span v-else>暂无关联班级</span>
          </div>
        </div>

        <div class="preview-header-actions">
          <el-tag :type="statusType" effect="light">
            {{ statusText }}
          </el-tag>
          <el-button
            class="preview-icon-close"
            :icon="Close"
            circle
            text
            aria-label="关闭"
            @click="closeDialog"
          />
        </div>
      </div>
    </template>

    <div v-if="assignmentDetail" class="preview-content">
      <div class="preview-time-panel">
        <div class="preview-time-item">
          <span class="preview-time-icon">
            <el-icon><Calendar /></el-icon>
          </span>
          <span class="preview-time-copy">
            <span class="preview-time-label">开始时间</span>
            <strong>{{ formatDateTime(assignmentDetail.startDate) }}</strong>
          </span>
        </div>

        <el-icon class="preview-time-arrow"><Right /></el-icon>

        <div class="preview-time-item">
          <span class="preview-time-icon">
            <el-icon><Clock /></el-icon>
          </span>
          <span class="preview-time-copy">
            <span class="preview-time-label">截止时间</span>
            <strong>{{ formatDateTime(assignmentDetail.endDate) }}</strong>
          </span>
        </div>
      </div>

      <section class="content-section">
        <div class="content-section-heading">
          <span class="content-section-index">01</span>
          <h3>作业要求</h3>
        </div>
        <div
          v-if="sanitizedDescription"
          class="assignment-description editor-content-view"
          v-html="sanitizedDescription"
        ></div>
        <div v-else class="empty-state">暂无作业要求</div>
      </section>

      <section class="content-section">
        <div class="content-section-heading">
          <span class="content-section-index">02</span>
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
      <div class="preview-dialog-footer">
        <span class="read-only-hint">
          <el-icon><View /></el-icon>
          正文按编辑器内容原样显示
        </span>
        <el-button
          type="primary"
          class="preview-close-button"
          data-testid="close-preview"
          @click="closeDialog"
        >
          关闭
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed } from "vue";
import DOMPurify from "dompurify";
import moment from "moment";
import {
  Calendar,
  Clock,
  Close,
  Document,
  Download,
  Reading,
  Right,
  User,
  View,
} from "@element-plus/icons-vue";
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
  color: var(--preview-text);
}

.preview-dialog-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  padding: 24px 26px 20px;
  border-bottom: 1px solid var(--preview-line);
}

.preview-dialog-heading {
  min-width: 0;
}

.preview-kicker {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
  color: var(--preview-primary);
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.04em;
}

.preview-dialog-title {
  margin: 0;
  color: var(--preview-text);
  font-size: 24px;
  line-height: 1.35;
  overflow-wrap: anywhere;
}

.preview-class-list {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px 10px;
  margin-top: 10px;
  color: var(--preview-muted);
  font-size: 13px;
}

.preview-class-list .el-icon {
  color: var(--preview-primary);
}

.preview-header-actions {
  display: flex;
  align-items: center;
  flex: 0 0 auto;
  gap: 10px;
}

.preview-icon-close {
  color: var(--preview-muted);
  font-size: 18px;
}

.preview-icon-close:hover {
  color: var(--preview-primary);
  background: var(--preview-primary-soft);
}

.preview-time-panel {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
  align-items: center;
  gap: 18px;
  margin: 22px 0 0;
  padding: 16px 20px;
  background: linear-gradient(135deg, #f7f9ff 0%, var(--preview-primary-soft) 100%);
  border: 1px solid var(--preview-primary-border);
  border-radius: 12px;
}

.preview-time-item {
  display: flex;
  align-items: center;
  gap: 12px;
}

.preview-time-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 38px;
  height: 38px;
  flex: 0 0 38px;
  color: var(--preview-primary);
  font-size: 18px;
  background: #ffffff;
  border: 1px solid var(--preview-primary-border);
  border-radius: 10px;
  box-shadow: 0 6px 16px rgba(79, 115, 232, 0.09);
}

.preview-time-copy {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 4px;
}

.preview-time-label {
  color: var(--preview-muted);
  font-size: 12px;
}

.preview-time-copy strong {
  color: var(--preview-text);
  font-size: 14px;
  font-weight: 600;
  line-height: 1.4;
}

.preview-time-arrow {
  color: #9dafea;
  font-size: 18px;
}

.content-section {
  padding: 26px 0 4px;
}

.content-section + .content-section {
  margin-top: 22px;
  padding-top: 24px;
  border-top: 1px solid var(--preview-line);
}

.content-section-heading {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 17px;
}

.content-section-heading h3 {
  margin: 0;
  color: var(--preview-text);
  font-size: 17px;
  line-height: 1.4;
}

.content-section-index {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 32px;
  flex: 0 0 36px;
  color: var(--preview-primary);
  font-size: 12px;
  font-weight: 700;
  background: var(--preview-primary-soft);
  border: 1px solid var(--preview-primary-border);
  border-radius: 9px;
}

.file-count {
  margin-left: auto;
  color: var(--preview-muted);
  font-size: 13px;
}

.assignment-description.editor-content-view {
  min-height: 48px;
  margin: 0 0 0 48px;
  padding: 0;
  overflow-x: visible;
  overflow-wrap: anywhere;
  color: var(--preview-text);
  line-height: 1.8;
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
  margin-left: 48px;
  padding: 22px;
  color: var(--preview-muted);
  text-align: center;
  background: var(--preview-soft);
  border: 1px dashed var(--preview-primary-border);
  border-radius: 10px;
}

.attachment-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-left: 48px;
}

.attachment-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 13px 14px;
  background: var(--preview-soft);
  border: 1px solid var(--preview-line);
  border-radius: 10px;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.attachment-item:hover {
  border-color: var(--preview-primary-border);
  box-shadow: 0 8px 22px rgba(54, 89, 199, 0.08);
}

.attachment-icon {
  color: var(--preview-primary);
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
  color: var(--preview-muted);
  font-size: 12px;
}

.preview-dialog-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 14px 26px;
  background: var(--preview-soft);
  border-top: 1px solid var(--preview-line);
}

.read-only-hint {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  color: var(--preview-muted);
  font-size: 13px;
}

.read-only-hint .el-icon {
  color: var(--preview-primary);
}

.preview-close-button {
  min-width: 88px;
  background: var(--preview-primary);
  border-color: var(--preview-primary);
}

.preview-close-button:hover,
.preview-close-button:focus {
  background: var(--preview-primary-deep);
  border-color: var(--preview-primary-deep);
}

:global(.assignment-content-preview-dialog.el-dialog) {
  --preview-primary: #4f73e8;
  --preview-primary-deep: #3659c7;
  --preview-primary-soft: #f0f4ff;
  --preview-primary-border: #dfe7ff;
  --preview-text: #26324a;
  --preview-muted: #7b869b;
  --preview-line: #e7ebf2;
  --preview-soft: #f8fafe;
  max-width: 92vw;
  margin-top: 8vh;
  overflow: hidden;
  border-radius: 15px;
  box-shadow: 0 28px 72px rgba(31, 43, 72, 0.24);
}

:global(.assignment-content-preview-dialog.el-dialog::before) {
  display: block;
  height: 4px;
  background: linear-gradient(90deg, #4f73e8, #3659c7);
  content: "";
}

:global(.assignment-content-preview-overlay) {
  background: rgba(15, 23, 42, 0.5);
}

:global(.assignment-content-preview-dialog .el-dialog__header) {
  margin: 0;
  padding: 0;
}

:global(.assignment-content-preview-dialog .el-dialog__body) {
  max-height: calc(84vh - 166px);
  padding: 0 26px 18px;
  overflow-y: auto;
}

:global(.assignment-content-preview-dialog .el-dialog__footer) {
  padding: 0;
}

@media (max-width: 640px) {
  .preview-dialog-header {
    flex-wrap: wrap;
    gap: 14px;
    padding: 20px 18px 16px;
  }

  .preview-dialog-title {
    font-size: 20px;
  }

  .preview-header-actions {
    width: 100%;
    justify-content: space-between;
  }

  .preview-time-panel {
    grid-template-columns: 1fr;
    gap: 12px;
    margin-top: 18px;
    padding: 14px;
  }

  .preview-time-arrow {
    display: none;
  }

  .assignment-description.editor-content-view,
  .attachment-list,
  .empty-state {
    margin-left: 0;
  }

  .attachment-item {
    align-items: flex-start;
    flex-wrap: wrap;
  }

  .attachment-info {
    flex-basis: calc(100% - 42px);
  }

  .preview-dialog-footer {
    justify-content: flex-end;
    padding: 12px 18px;
  }

  .read-only-hint {
    display: none;
  }

  :global(.assignment-content-preview-dialog .el-dialog__body) {
    padding: 0 18px 16px;
  }
}
</style>
