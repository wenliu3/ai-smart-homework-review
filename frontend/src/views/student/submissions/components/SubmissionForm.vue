<template>
  <div class="form-section">
    <!-- <div class="section-header">
      <h3 class="section-title">
        {{ submission?.isDraft ? '编辑作业' : '提交作业' }}
      </h3>
    </div> -->
    <div class="section-content">
      <!-- 过期或终止提示 -->
      <div v-if="isOverdue || isTerminated" class="mb-6">
        <!-- 过期提示 -->
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

        <!-- 终止提示 -->
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
      <div v-if="!isOverdue && !isTerminated">
        <el-form
          ref="formRef"
          :model="form"
          :rules="rules"
          label-width="100px"
          size="large"
          scroll-to-error
        >
          <!-- 作业内容 -->
          <el-form-item label="作业内容" prop="content" required>
            <div class="w-full">
              <wang-editor
                ref="editorRef"
                v-model="form.content"
                :height="'350px'"
                :placeholder="'请在此输入您的作业内容...'"
                :max-length="5000"
              />
            </div>
          </el-form-item>

          <!-- 附件上传 -->
          <el-form-item label="作业附件">
            <div class="w-full">
              <div v-if="uploading" class="mb-2">
                <el-progress :percentage="uploadProgress" :stroke-width="8" />
                <span class="text-xs text-blue-500">正在上传... {{ uploadProgress }}%</span>
              </div>
              <div v-else-if="uploadedResults.length > 0" class="mb-2">
                <el-tag v-for="(f,i) in uploadedResults" :key="i" type="success" size="small" effect="plain" class="mr-1 mb-1">
                  {{ f.fileName }} ✓
                </el-tag>
              </div>
              <input
                ref="fileInputRef"
                type="file"
                multiple
                accept=".jpg,.jpeg,.png,.gif,.webp,.pdf,.doc,.docx,.txt"
                style="display:none"
                @change="onFilesSelected"
              />
              <el-button type="warning" size="small" @click="triggerFileSelect" :disabled="uploading">
                <el-icon><Upload /></el-icon>
                选择文件（PDF/Word/图片/文本）
              </el-button>
              <div class="text-xs text-orange-500 mt-1">
                <el-icon :size="12"><WarningFilled /></el-icon>
                如作业为文档，请先上传文件再提交，AI将自动读取文件内容批改
              </div>
              <div class="text-xs text-gray-400">支持 jpg、png、pdf、doc、docx、txt，单文件不超过10MB</div>
            </div>
          </el-form-item>
        </el-form>
      </div>

      <!-- 只读显示（过期或终止时显示现有内容） -->
      <div v-else-if="submission?.content" class="mt-4">
        <h4 class="text-base font-medium text-gray-900 mb-3">当前作业内容</h4>
        <div
          class="prose max-w-none text-gray-700 p-4 bg-gray-50 rounded-lg border"
          v-html="submission.content"
        ></div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, watch, computed } from "vue";
import type { Submission } from "../../../../api/submissions";
import { useSubmissionUtils } from "../composables";
import { Upload, WarningFilled } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";

interface Props {
  submission?: Submission | null;
  assignment?: any;
  isOverdue?: boolean;
}

const props = defineProps<Props>();

const { formatDate } = useSubmissionUtils();

const formRef = ref();
const editorRef = ref();

// 计算属性
const isTerminated = computed(() => {
  return props.assignment?.status === "terminated";
});

// 表单数据
const form = reactive({
  content: "",
});

// ========== 附件上传（原生 input + XHR，完全可控） ==========
const fileInputRef = ref<HTMLInputElement>();
const uploadedResults = ref<any[]>([]);
const uploading = ref(false);
const uploadProgress = ref(0);

const MAX_SIZE = 10 * 1024 * 1024;
const ALLOWED_EXT = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'pdf', 'doc', 'docx', 'txt'];

const triggerFileSelect = () => {
  fileInputRef.value?.click();
};

const onFilesSelected = async (e: Event) => {
  const input = e.target as HTMLInputElement;
  const files = Array.from(input.files || []);
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
        // 整体进度 = (已完成文件数 * 100 + 当前文件进度) / 总文件数
        uploadProgress.value = Math.round((i * 100 + pct) / files.length);
      });
      results.push(result);
      ElMessage.success(`「${file.name}」上传成功`);
    } catch (e: any) {
      ElMessage.error(`「${file.name}」上传失败: ${e.message}`);
    }
  }

  console.log('上传完成，结果:', results.map(r => r.fileName));
  uploadedResults.value.push(...results);
  uploading.value = false;
  uploadProgress.value = 100;
  input.value = ''; // 清空 input 允许重复选同一文件
};

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

const getUploadedAttachments = (): any[] => {
  return uploadedResults.value || [];
};

// 自定义校验函数：检查富文本的实际字符长度
const validateContent = (rule: any, value: string, callback: any) => {
  const textLength = editorRef.value?.getTextLength() || 0;

  // 有附件：文本可为空；无附件：至少3个字符
  if (textLength === 0 && uploadedResults.value.length === 0) {
    callback(new Error("请输入至少3个字符的作业内容，或上传作业文件"));
    return;
  }
  if (textLength > 0 && textLength < 3 && uploadedResults.value.length === 0) {
    callback(new Error(`作业内容至少需要3个字符，当前只有${textLength}个字符`));
    return;
  }

  callback();
};

// 校验规则
const rules = {
  content: [
    {
      required: true,
      validator: validateContent,
      trigger: "blur",
    },
  ],
};

// 校验方法
const validate = async () => {
  try {
    await formRef.value?.validate();
    return true;
  } catch (error) {
    return false;
  }
};

// 暴露表单实例和数据给父组件
defineExpose({
  formRef,
  form,
  validate,
  getUploadedAttachments,
  fileList: uploadedResults,
});

// 监听 submission 变化，填充表单数据
watch(
  () => props.submission,
  (newSubmission) => {
    if (newSubmission) {
      form.content = newSubmission.content || "";
    }
  },
  { immediate: true }
);

defineOptions({
  name: "SubmissionForm",
});
</script>

<style scoped>
/* 表单分区样式 */
.form-section {
  border-bottom: 1px solid #f0f2f5;
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
