<template>
  <section
    v-if="attachments.length"
    class="assignment-attachment-list"
    aria-label="作业附件"
  >
    <div class="attachment-list__heading">
      <div>
        <p class="attachment-list__eyebrow">ATTACHMENTS</p>
        <h3>{{ title }}</h3>
      </div>
      <span class="attachment-list__count"
        >{{ attachments.length }} 个文件</span
      >
    </div>

    <ul class="attachment-list__items">
      <li
        v-for="attachment in attachments"
        :key="attachment.fileUrl"
        class="attachment-list__item"
      >
        <span
          class="attachment-list__type"
          :class="`attachment-list__type--${getFileKind(attachment)}`"
          aria-hidden="true"
        >
          {{ getFileLabel(attachment) }}
        </span>
        <span class="attachment-list__meta">
          <strong :title="attachment.fileName">{{
            attachment.fileName
          }}</strong>
          <small>{{ formatFileSize(attachment.fileSize) }}</small>
        </span>
        <el-button
          class="attachment-list__download"
          text
          type="primary"
          :aria-label="`下载 ${attachment.fileName}`"
          @click="emit('download', attachment)"
        >
          <el-icon><Download /></el-icon>
          下载
        </el-button>
      </li>
    </ul>
  </section>
</template>

<script setup lang="ts">
import { Download } from "@element-plus/icons-vue";
import type { Attachment } from "@/api/submissions";

withDefaults(
  defineProps<{
    attachments?: Attachment[];
    title?: string;
  }>(),
  {
    attachments: () => [],
    title: "教师附件",
  }
);

const emit = defineEmits<{
  (event: "download", attachment: Attachment): void;
}>();

const getExtension = (attachment: Attachment) => {
  const fileName = attachment.fileName || attachment.fileUrl || "";
  return fileName.split(".").pop()?.toLowerCase() || "";
};

const getFileKind = (attachment: Attachment) => {
  const extension = getExtension(attachment);
  const type = (attachment.fileType || "").toLowerCase();

  if (extension === "pdf" || type.includes("pdf")) return "pdf";
  if (["doc", "docx"].includes(extension) || type.includes("word"))
    return "word";
  if (["xls", "xlsx", "csv"].includes(extension) || type.includes("sheet"))
    return "sheet";
  if (["ppt", "pptx"].includes(extension) || type.includes("presentation"))
    return "slides";
  if (["zip", "rar", "7z"].includes(extension) || type.includes("zip"))
    return "archive";
  if (
    ["png", "jpg", "jpeg", "gif", "webp"].includes(extension) ||
    type.startsWith("image/")
  )
    return "image";
  return "file";
};

const getFileLabel = (attachment: Attachment) => {
  const extension = getExtension(attachment);
  return extension ? extension.slice(0, 4).toUpperCase() : "FILE";
};

const formatFileSize = (size: number) => {
  if (!Number.isFinite(size) || size <= 0) return "大小未知";
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) {
    const kilobytes = size / 1024;
    return `${
      Number.isInteger(kilobytes) ? kilobytes : kilobytes.toFixed(1)
    } KB`;
  }
  const megabytes = size / (1024 * 1024);
  return `${Number.isInteger(megabytes) ? megabytes : megabytes.toFixed(1)} MB`;
};
</script>

<style scoped>
.assignment-attachment-list {
  padding: 20px;
  border: 1px solid #e7eaf3;
  border-radius: 14px;
  background: #f8f9ff;
}

.attachment-list__heading {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 12px;
}

.attachment-list__eyebrow {
  margin: 0 0 3px;
  color: #7c6ee6;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.12em;
}

.attachment-list__heading h3 {
  margin: 0;
  color: #20243a;
  font-size: 15px;
}

.attachment-list__count {
  color: #8b91a7;
  font-size: 12px;
}

.attachment-list__items {
  display: grid;
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.attachment-list__item {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
  padding: 11px 12px;
  border: 1px solid #ebeef7;
  border-radius: 11px;
  background: #fff;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.attachment-list__item:hover {
  border-color: #cfc9f8;
  box-shadow: 0 8px 22px rgba(87, 73, 170, 0.08);
}

.attachment-list__type {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  flex: 0 0 44px;
  border-radius: 10px;
  background: #eef0f6;
  color: #667085;
  font-size: 10px;
  font-weight: 800;
}

.attachment-list__type--pdf {
  background: #fff0f1;
  color: #e4515c;
}
.attachment-list__type--word {
  background: #edf4ff;
  color: #4078d4;
}
.attachment-list__type--sheet {
  background: #eaf8f1;
  color: #278b60;
}
.attachment-list__type--slides {
  background: #fff4e8;
  color: #d87935;
}
.attachment-list__type--archive {
  background: #fff7dc;
  color: #a57917;
}
.attachment-list__type--image {
  background: #f3edff;
  color: #7d54cb;
}

.attachment-list__meta {
  display: flex;
  flex: 1;
  min-width: 0;
  flex-direction: column;
  gap: 4px;
}

.attachment-list__meta strong {
  overflow: hidden;
  color: #30344a;
  font-size: 14px;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.attachment-list__meta small {
  color: #9298aa;
  font-size: 12px;
}

.attachment-list__download {
  flex: 0 0 auto;
}

.attachment-list__download :deep(.el-icon) {
  margin-right: 4px;
}

@media (max-width: 560px) {
  .assignment-attachment-list {
    padding: 14px;
  }
  .attachment-list__count {
    display: none;
  }
  .attachment-list__item {
    gap: 9px;
    padding: 10px;
  }
  .attachment-list__type {
    width: 38px;
    height: 38px;
    flex-basis: 38px;
  }
  .attachment-list__download {
    padding-inline: 6px;
  }
}
</style>
