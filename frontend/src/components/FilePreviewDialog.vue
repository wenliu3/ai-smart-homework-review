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
    @opened="onDialogOpened"
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
const docxBlob = ref<Blob | null>(null); // 暂存 docx blob，等弹窗就绪后渲染
const docxContainerRef = ref<HTMLElement | null>(null);
const dialogReady = ref(false);  // 弹窗动画完成后置 true

const dialogWidth = computed(() => {
  return window.innerWidth < 768 ? "95%" : "80%";
});

const previewHeight = computed(() => {
  return `${window.innerHeight * 0.75}px`;
});

const open = async (att: any) => {
  visible.value = true;
  dialogReady.value = false;
  docxBlob.value = null;
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

    // docx 类型 — 先保存 blob，等 dialog opened 后再渲染
    if (ext === "docx" || contentType.includes("wordprocessingml")) {
      docxBlob.value = await resp.blob();
      previewType.value = "docx";
      // 如果弹窗已就绪则直接渲染，否则等 @opened
      if (dialogReady.value) {
        await nextTick();
        await renderDocx();
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
  dialogReady.value = false;
  docxBlob.value = null;
  if (blobUrl.value) {
    URL.revokeObjectURL(blobUrl.value);
    blobUrl.value = "";
  }
  if (docxContainerRef.value) {
    docxContainerRef.value.innerHTML = "";
  }
  previewType.value = "";
};

/** 渲染 docx 文件 */
async function renderDocx(): Promise<void> {
  if (!docxBlob.value || !docxContainerRef.value) return;
  const container = docxContainerRef.value;
  container.innerHTML = "";
  try {
    console.log("[docx-preview:FilePreview] 开始渲染，大小:", docxBlob.value.size);
    console.log("[docx-preview:FilePreview] 容器宽度:", container.offsetWidth);
    await renderAsync(docxBlob.value, container, undefined, {
      className: "docx-preview-content",
      inWrapper: true,
      ignoreWidth: true,           // 自适应容器宽度
      ignoreHeight: false,
      breakPages: true,
      useBase64URL: true,
      experimental: true,
      trimXmlDeclaration: true,
      renderHeaders: true,
      renderFooters: true,
      renderFootnotes: true,
      renderEndnotes: true,
      debug: true,
    });
    // 调试 & EMF/WMF 检测
    const imgs = container.querySelectorAll("img");
    console.log("[docx-preview:FilePreview] 渲染完成，图片数量:", imgs.length);
    imgs.forEach((img, i) => {
      const src = img.getAttribute("src") || "";
      const srcType = src.startsWith("data:") ? "base64" : src.startsWith("blob:") ? "blob" : "other/empty";
      console.log(`[docx-preview:FilePreview] 图片[${i}]: src类型=${srcType}, 可见=${img.offsetWidth > 0 && img.offsetHeight > 0}`);
    });
    patchImagesAfterRender(container);
  } catch (e) {
    console.error("[docx-preview:FilePreview] 渲染失败:", e);
    container.innerHTML = "<p>Word 文档渲染失败，请下载查看</p>";
  }
}

/** 弹窗动画完成后渲染 docx */
function onDialogOpened(): void {
  dialogReady.value = true;
  nextTick(() => {
    setTimeout(() => renderDocx(), 100);
  });
}

defineExpose({ open });

/** EMF/WMF 占位图 SVG */
const UNSUPPORTED_IMG_PLACEHOLDER = `data:image/svg+xml,${encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" width="200" height="80"><rect width="200" height="80" fill="#fef2f2" stroke="#ef4444" stroke-width="1.5" rx="4"/><text x="100" y="35" text-anchor="middle" font-family="sans-serif" font-size="12" fill="#991b1b">⚠ 浏览器不支持此图片格式</text><text x="100" y="55" text-anchor="middle" font-family="sans-serif" font-size="11" fill="#b91c1c">建议用 PNG/JPG 替代后重新上传</text></svg>`)}`;

function getImageIssue(img: HTMLImageElement): string {
  const src = img.getAttribute("src") || "";
  if (!src) return "src 为空";
  const lower = src.toLowerCase();
  if (lower.includes("image/x-emf") || lower.includes("image/emf") || lower.includes(".emf")) {
    return "EMF 矢量图 — 浏览器不支持此格式";
  }
  if (lower.includes("image/x-wmf") || lower.includes("image/wmf") || lower.includes(".wmf")) {
    return "WMF 矢量图 — 浏览器不支持此格式";
  }
  return "";
}

function patchImagesAfterRender(container: HTMLElement): void {
  const imgs = container.querySelectorAll("img");
  imgs.forEach((img) => {
    const issue = getImageIssue(img);
    if (issue) {
      img.src = UNSUPPORTED_IMG_PLACEHOLDER;
      img.style.border = "2px dashed #ef4444";
      img.style.padding = "4px";
      img.style.background = "#fef2f2";
      img.style.minWidth = "200px";
      img.style.minHeight = "80px";
      img.title = issue;
      console.warn("[docx-preview:FilePreview] 图片已替换为占位图:", issue);
    }
  });
}
</script>

<style scoped>
.preview-container {
  width: 100%;
  display: flex;
  justify-content: center;
  align-items: flex-start;         /* 顶部对齐，避免大文档居中 */
  overflow: auto;                  /* 允许滚动 */
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

/* docx-wrapper 内部 CSS 隔离 — 修复 Tailwind v4 preflight 覆盖 */
.docx-preview-wrapper :deep(.docx-wrapper) {
  background: transparent;
  padding: 0;
}

.docx-preview-wrapper :deep(.docx-wrapper img) {
  max-width: 100%;
  height: auto;
  display: inline;
  vertical-align: baseline;
}

.docx-preview-wrapper :deep(.docx-wrapper table) {
  border-collapse: collapse;
  width: 100%;
}

.docx-preview-wrapper :deep(.docx-wrapper td),
.docx-preview-wrapper :deep(.docx-wrapper th) {
  border: 1px solid #d1d5db;
  padding: 6px 10px;
}

.docx-preview-wrapper :deep(.docx-wrapper th) {
  background: #f3f4f6;
  font-weight: 600;
}

.docx-preview-wrapper :deep(.docx-wrapper ul),
.docx-preview-wrapper :deep(.docx-wrapper ol) {
  margin: 6px 0;
  padding-left: 24px;
}

.docx-preview-wrapper :deep(.docx-wrapper li) {
  margin: 3px 0;
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
