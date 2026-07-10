<template>
  <div class="submission-form">
    <!-- 过期或终止提示 -->
    <div v-if="isOverdue || isTerminated" class="mb-6">
      <el-alert
        v-if="isOverdue"
        title="作业已过期"
        type="error"
        :closable="false"
        show-icon
      >
        <template #default>
          <p class="mb-2">
            <strong>截止时间：</strong>{{ formatDate(assignment?.dueDate) }}
          </p>
          <p class="text-sm">作业提交时间已过，无法再提交作业或保存草稿</p>
        </template>
      </el-alert>

      <el-alert
        v-else-if="isTerminated"
        title="作业已终止"
        type="error"
        :closable="false"
        show-icon
      >
        <template #default>
          <p class="mb-2" v-if="assignment?.terminatedReason">
            <strong>终止原因：</strong>{{ assignment.terminatedReason }}
          </p>
          <p class="text-sm">该作业已被教师终止，无法再提交作业或保存草稿</p>
        </template>
      </el-alert>
    </div>

    <!-- 表单内容 -->
    <div v-if="!isOverdue && !isTerminated" class="form-body">
      <!-- 富文本编辑器区域 -->
      <div class="editor-card">
        <div class="card-header">
          <span class="card-title">
            <el-icon :size="18"><EditPen /></el-icon>
            作业内容
          </span>
          <span class="card-hint">可直接编写内容，也支持拖拽文件到编辑器上传</span>
        </div>
        <div
          class="editor-wrapper"
          :class="{ 'drag-active': isDragging }"
          @dragover.capture="handleDragOver"
          @dragleave="handleDragLeave"
          @drop.capture="handleDrop"
        >
          <WangEditor
            v-model="form.content"
            height="360px"
            placeholder="请在此处编写作业内容，也可以上传附件..."
          />
          <!-- 拖拽提示遮罩 -->
          <div v-if="isDragging" class="drag-overlay">
            <el-icon :size="40" color="#3b82f6"><UploadFilled /></el-icon>
            <span>松开鼠标上传文件</span>
          </div>
        </div>
      </div>

      <!-- 附件上传区域 -->
      <div class="upload-card">
        <div class="card-header">
          <span class="card-title">
            <el-icon :size="18"><Paperclip /></el-icon>
            作业附件
          </span>
          <span class="card-hint">可选，支持 PDF/Word/图片/文本</span>
        </div>
        <div class="upload-body">
          <!-- 上传进度 -->
          <div v-if="uploading" class="upload-progress">
            <el-progress :percentage="uploadProgress" :stroke-width="8" />
            <span class="text-xs text-blue-500">正在上传... {{ uploadProgress }}%</span>
          </div>

          <!-- 已上传文件列表 -->
          <div v-if="uploadedResults.length > 0" class="file-list">
            <div
              v-for="(f, i) in uploadedResults"
              :key="i"
              class="file-item"
            >
              <el-icon class="file-icon" :size="18">
                <Document />
              </el-icon>
              <span class="file-name" :title="f.fileName">{{ f.fileName }}</span>
              <el-icon
                class="file-remove"
                :size="16"
                @click="removeUploadedFile(i)"
              >
                <CircleClose />
              </el-icon>
            </div>
          </div>

          <input
            ref="fileInputRef"
            type="file"
            multiple
            accept=".jpg,.jpeg,.png,.gif,.webp,.pdf,.doc,.docx,.txt"
            style="display:none"
            @change="onFilesSelected"
          />
          <el-button type="primary" plain size="small" @click="triggerFileSelect" :disabled="uploading">
            <el-icon class="mr-1"><Upload /></el-icon>
            上传附件
          </el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, watch, computed, onUnmounted } from "vue";
import type { Submission } from "../../../../api/submissions";
import { useSubmissionUtils } from "../composables";
import {
  Upload,
  EditPen,
  Paperclip,
  Document,
  CircleClose,
  UploadFilled,
} from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";
import WangEditor from "../../../../components/WangEditor.vue";

interface Props {
  submission?: Submission | null;
  assignment?: any;
  isOverdue?: boolean;
}

const props = defineProps<Props>();

const { formatDate } = useSubmissionUtils();

// 计算属性
const isTerminated = computed(() => {
  return props.assignment?.status === "terminated";
});

// 表单数据
const form = reactive({
  content: "",
  attachments: [] as any[],
});

// ========== 附件上传（原生 input + XHR，完全可控） ==========
const fileInputRef = ref<HTMLInputElement>();
const uploadedResults = ref<any[]>([]);
const uploading = ref(false);
const uploadProgress = ref(0);
const filesConsumed = ref(false);

// 拖拽状态
const isDragging = ref(false);

const MAX_SIZE = 10 * 1024 * 1024;
const ALLOWED_EXT = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'pdf', 'doc', 'docx', 'txt'];

const triggerFileSelect = () => {
  if (uploading.value) return;
  fileInputRef.value?.click();
};

// 统一的上传逻辑（按钮和拖拽共用）
const uploadFiles = async (files: File[]) => {
  if (files.length === 0) return;

  // 校验
  for (const f of files) {
    const ext = f.name.split('.').pop()?.toLowerCase() || '';
    if (!ALLOWED_EXT.includes(ext)) { ElMessage.warning(`不支持的文件类型: ${f.name}`); return; }
    if (f.size > MAX_SIZE) { ElMessage.warning(`文件「${f.name}」超过10MB限制`); return; }
  }

  uploading.value = true;
  uploadProgress.value = 0;
  const results: any[] = [];

  for (let i = 0; i < files.length; i++) {
    const file = files[i];
    try {
      const result = await uploadFileXHR(file, (pct) => {
        uploadProgress.value = Math.round((i * 100 + pct) / files.length);
      });
      results.push(result);
      ElMessage.success(`「${file.name}」上传成功`);
    } catch (e: any) {
      ElMessage.error(`「${file.name}」上传失败: ${e.message}`);
    }
  }

  uploadedResults.value.push(...results);
  uploading.value = false;
  uploadProgress.value = 100;
};

// 按钮选择文件
const onFilesSelected = async (e: Event) => {
  const input = e.target as HTMLInputElement;
  const files = Array.from(input.files || []);
  await uploadFiles(files);
  input.value = '';
};

// ========== 拖拽上传 ==========
const hasFiles = (e: DragEvent): boolean => {
  return Array.from(e.dataTransfer?.items || []).some(
    item => item.kind === 'file'
  );
};

const handleDragOver = (e: DragEvent) => {
  if (!hasFiles(e)) return;
  e.preventDefault();
  e.dataTransfer!.dropEffect = 'copy';
  isDragging.value = true;
};

const handleDragLeave = (e: DragEvent) => {
  // 只有离开整个编辑器区域才取消拖拽状态
  const related = e.relatedTarget as Node | null;
  const wrapper = e.currentTarget as HTMLElement;
  if (!related || !wrapper.contains(related)) {
    isDragging.value = false;
  }
};

const handleDrop = async (e: DragEvent) => {
  if (!hasFiles(e)) return; // 不是文件拖拽，让编辑器处理

  e.preventDefault();
  e.stopPropagation();
  isDragging.value = false;

  const files = Array.from(e.dataTransfer?.files || []);
  await uploadFiles(files);
};

// XHR 上传
const uploadFileXHR = (file: File, onProgress: (pct: number) => void): Promise<any> => {
  return new Promise((resolve, reject) => {
    const formData = new FormData();
    formData.append('files', file);
    const xhr = new XMLHttpRequest();
    xhr.open('POST', '/api/upload/files');
    const token = localStorage.getItem('token');
    if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`);
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100));
    };
    xhr.onload = () => {
      if (xhr.status === 200 || xhr.status === 201) {
        const data = JSON.parse(xhr.responseText);
        const files = data.data?.files || data.files || [];
        resolve(files.length > 0 ? files[0] : { fileName: file.name, error: '返回数据为空' });
      } else {
        reject(new Error(`HTTP ${xhr.status}`));
      }
    };
    xhr.onerror = () => reject(new Error('网络错误'));
    xhr.send(formData);
  });
};

const removeUploadedFile = (index: number) => {
  const file = uploadedResults.value[index];
  if (file?.fileUrl) {
    const filename = file.fileUrl.replace('/uploads/', '');
    const token = localStorage.getItem('token');
    fetch(`/api/upload/delete/${filename}`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${token}` },
    }).catch(() => {});
  }
  uploadedResults.value.splice(index, 1);
  ElMessage.success('已移除文件');
};

const cleanupUploadedFiles = () => {
  for (const file of uploadedResults.value) {
    if (file?.fileUrl) {
      const filename = file.fileUrl.replace('/uploads/', '');
      const token = localStorage.getItem('token');
      fetch(`/api/upload/delete/${filename}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      }).catch(() => {});
    }
  }
  uploadedResults.value = [];
};

onUnmounted(() => {
  if (!filesConsumed.value) {
    cleanupUploadedFiles();
  }
});

const getUploadedAttachments = (): any[] => {
  return uploadedResults.value || [];
};

const getContent = (): string => {
  return form.content || "";
};

// 校验方法：至少有内容或附件
const validate = async () => {
  const hasContent = form.content && form.content.trim() && form.content !== "<p><br></p>";
  const hasAttachments = uploadedResults.value.length > 0;
  if (!hasContent && !hasAttachments) {
    ElMessage.warning("请编写作业内容或上传作业文件");
    return false;
  }
  return true;
};

// 暴露表单实例和数据给父组件
defineExpose({
  form,
  validate,
  getUploadedAttachments,
  getContent,
  fileList: uploadedResults,
  markFilesConsumed: () => { filesConsumed.value = true; },
});

// 监听 submission 变化，填充数据
watch(
  () => props.submission,
  (newSubmission) => {
    if (newSubmission) {
      form.content = newSubmission.content || "";
      uploadedResults.value = newSubmission.attachments || [];
    }
  },
  { immediate: true }
);

defineOptions({
  name: "SubmissionForm",
});
</script>

<style scoped>
.submission-form {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.form-body {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

/* 卡片通用样式 */
.editor-card,
.upload-card {
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.875rem 1.25rem;
  background: #f9fafb;
  border-bottom: 1px solid #f0f0f0;
}

.card-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 14px;
  font-weight: 600;
  color: #1f2937;
}

.card-hint {
  font-size: 12px;
  color: #9ca3af;
}

/* 编辑器 */
.editor-wrapper {
  position: relative;
}

.editor-wrapper :deep(.wang-editor) {
  border: none;
  border-radius: 0;
}

/* 拖拽高亮 */
.editor-wrapper.drag-active {
  outline: 2px dashed #3b82f6;
  outline-offset: -2px;
  background: #eff6ff;
}

/* 拖拽遮罩 */
.drag-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  background: rgba(239, 246, 255, 0.85);
  backdrop-filter: blur(2px);
  z-index: 100;
  pointer-events: none;
  font-size: 14px;
  font-weight: 500;
  color: #3b82f6;
}

/* 附件上传 */
.upload-body {
  padding: 1rem 1.25rem;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.625rem;
}

.upload-progress {
  width: 100%;
  margin-bottom: 0.5rem;
}

.file-list {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
  margin-bottom: 0.5rem;
}

.file-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0.75rem;
  background: #f0f9ff;
  border: 1px solid #bae6fd;
  border-radius: 8px;
  transition: background 0.2s;
}

.file-item:hover {
  background: #e0f2fe;
}

.file-icon {
  color: #0284c7;
  flex-shrink: 0;
}

.file-name {
  flex: 1;
  font-size: 13px;
  color: #1f2937;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-remove {
  color: #ef4444;
  cursor: pointer;
  flex-shrink: 0;
  transition: transform 0.2s;
}

.file-remove:hover {
  transform: scale(1.15);
}
</style>
