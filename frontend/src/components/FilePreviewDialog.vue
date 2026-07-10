<template>
  <el-dialog
    v-model="visible"
    :title="fileName || '文件预览'"
    :width="dialogWidth"
    :close-on-click-modal="true"
    :destroy-on-close="true"
    top="5vh"
    class="file-preview-dialog"
    @close="handleClose"
  >
    <div v-loading="loading" class="preview-container" :style="{ height: previewHeight }">
      <!-- 图片预览 -->
      <div v-if="previewType === 'image'" class="image-preview">
        <img :src="blobUrl" :alt="fileName" class="preview-image" />
      </div>

      <!-- PDF 预览 -->
      <iframe
        v-else-if="previewType === 'pdf'"
        :src="blobUrl"
        class="preview-iframe"
        frameborder="0"
      ></iframe>

      <!-- 文本预览 -->
      <div v-else-if="previewType === 'text'" class="text-preview">
        <pre>{{ textContent }}</pre>
      </div>

      <!-- docx 预览 — 使用 docx-preview 真实渲染 -->
      <div v-else-if="previewType === 'docx'" class="docx-preview-wrapper" ref="docxContainerRef"></div>

      <!-- 不支持的格式 -->
      <div v-else-if="previewType === 'unsupported'" class="unsupported-preview">
        <el-empty :description="`文件类型 ${fileExt} 不支持在线预览，请下载查看`">
          <el-button type="primary" @click="handleDownload">下载文件</el-button>
        </el-empty>
      </div>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, nextTick } from "vue";
import { ElMessage } from "element-plus";
import { renderAsync } from "docx-preview";

const visible = ref(false);
const loading = ref(false);
const blobUrl = ref("");
const textContent = ref("");
const previewType = ref("");
const fileName = ref("");
const fileExt = ref("");
const currentFileUrl = ref("");
const currentFileName = ref("");
const docxContainerRef = ref<HTMLElement | null>(null);

const dialogWidth = computed(() => {
  return window.innerWidth < 768 ? "95%" : "80%";
});

const previewHeight = computed(() => {
  return `${window.innerHeight * 0.75}px`;
});

const open = async (att: any) => {
  visible.value = true;
  loading.value = true;
  blobUrl.value = "";
  textContent.value = "";
  previewType.value = "";
  fileName.value = att.fileName || "未知文件";
  currentFileUrl.value = att.fileUrl || "";
  currentFileName.value = fileName.value;

  const filename = (att.fileUrl || "").replace("/uploads/", "");
  const ext = (filename.split(".").pop() || "").toLowerCase();
  fileExt.value = `.${ext}`;

  try {
    const token = localStorage.getItem("token");
    const resp = await fetch(`/api/upload/preview/${filename}`, {
      headers: { Authorization: `Bearer ${token}` },
    });

    if (!resp.ok) throw new Error("预览失败");

    const contentType = resp.headers.get("content-type") || "";

    // JSON 响应表示不支持预览
    if (contentType.includes("json")) {
      previewType.value = "unsupported";
      return;
    }

    // 图片类型
    if (contentType.startsWith("image/")) {
      const blob = await resp.blob();
      blobUrl.value = URL.createObjectURL(blob);
      previewType.value = "image";
      return;
    }

    // PDF 类型
    if (contentType.includes("pdf")) {
      const blob = await resp.blob();
      blobUrl.value = URL.createObjectURL(blob);
      previewType.value = "pdf";
      return;
    }

    // docx 类型 — 使用 docx-preview 渲染
    if (ext === "docx" || contentType.includes("wordprocessingml")) {
      const blob = await resp.blob();
      previewType.value = "docx";
      await nextTick();
      if (docxContainerRef.value) {
        await renderAsync(blob, docxContainerRef.value, undefined, {
          className: "docx-preview-content",
          inWrapper: true,
          ignoreWidth: false,
          ignoreHeight: false,
          breakPages: true,
          experimental: true,
        });
      }
      return;
    }

    // 纯文本
    if (contentType.includes("text/plain")) {
      textContent.value = await resp.text();
      previewType.value = "text";
      return;
    }

    // 其他类型尝试作为文本
    const blob = await resp.blob();
    if (ext === "txt") {
      textContent.value = await blob.text();
      previewType.value = "text";
    } else {
      previewType.value = "unsupported";
    }
  } catch (e: any) {
    ElMessage.warning("文件预览失败: " + e.message);
    previewType.value = "unsupported";
  } finally {
    loading.value = false;
  }
};

const handleDownload = () => {
  const token = localStorage.getItem("token");
  const filename = currentFileUrl.value.replace("/uploads/", "");
  fetch(`/api/upload/download/${filename}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
    .then((res) => res.blob())
    .then((blob) => {
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = currentFileName.value;
      a.click();
      URL.revokeObjectURL(url);
    })
    .catch(() => ElMessage.warning("下载失败"));
};

const handleClose = () => {
  if (blobUrl.value) {
    URL.revokeObjectURL(blobUrl.value);
    blobUrl.value = "";
  }
  if (docxContainerRef.value) {
    docxContainerRef.value.innerHTML = "";
  }
  previewType.value = "";
};

defineExpose({ open });
</script>

<style scoped>
.preview-container {
  width: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
  overflow: hidden;
  background: #f5f5f5;
  border-radius: 4px;
}

.image-preview {
  width: 100%;
  height: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
  overflow: auto;
}

.preview-image {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}

.preview-iframe {
  width: 100%;
  height: 100%;
  border: none;
}

.text-preview {
  width: 100%;
  height: 100%;
  overflow: auto;
  padding: 16px;
  background: white;
}

.text-preview pre {
  white-space: pre-wrap;
  word-break: break-all;
  font-family: "Microsoft YaHei", sans-serif;
  font-size: 14px;
  line-height: 1.8;
  margin: 0;
}

.docx-preview-wrapper {
  width: 100%;
  height: 100%;
  overflow: auto;
  background: #e8e8e8;
}

.docx-preview-wrapper :deep(.docx-preview-content) {
  background: white;
  margin: 0 auto;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}

.unsupported-preview {
  width: 100%;
  height: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
  background: white;
}

:deep(.el-dialog__body) {
  padding: 0;
}

:deep(.el-dialog__header) {
  padding: 12px 20px;
  border-bottom: 1px solid #e5e7eb;
  margin-right: 0;
}
</style>
