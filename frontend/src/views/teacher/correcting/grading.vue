<template>
  <div class="grading-page p-4">
    <div class="flex items-center gap-3 mb-4">
      <el-button link @click="goBack" :icon="ArrowLeft" class="!p-2">
        <span class="hidden sm:inline ml-1">返回</span>
      </el-button>
      <h1 class="text-lg font-semibold">批改作业</h1>
    </div>

    <div v-loading="loading" class="grading-container">
      <el-card v-if="submission" class="mb-4">
        <template #header>
          <div class="flex justify-between items-center">
            <span>
              <strong>{{ submission.studentName }}</strong>
              <span class="text-gray-400 ml-2">学号：{{ submission.studentNumber }}</span>
            </span>
            <el-tag v-if="submission.aiScore != null" type="warning">AI评分：{{ submission.aiScore }}分</el-tag>
          </div>
        </template>

        <!-- AI评语 -->
        <div v-if="submission.aiReviewContent" class="mb-4 p-3 bg-blue-50 rounded-lg">
          <div class="text-sm font-medium text-blue-700 mb-2">🤖 AI批改评语</div>
          <div class="text-sm text-gray-700 whitespace-pre-wrap" v-html="formatContent(submission.aiReviewContent)"></div>
        </div>

        <!-- 学生作业内容 -->
        <div v-if="submission.content" class="mb-4">
          <div class="text-sm font-medium mb-2 flex items-center gap-1">
            <el-icon :size="14" color="#3b82f6"><Document /></el-icon>
            作业内容
          </div>
          <div class="p-3 bg-blue-50 rounded border border-blue-200 text-sm text-gray-700 submission-content" v-html="submission.content"></div>
        </div>

        <!-- 学生附件 -->
        <div v-if="submission.attachments && submission.attachments.length > 0" class="mb-4">
          <div class="text-sm font-medium mb-2 flex items-center gap-1">
            <el-icon :size="14" color="#f59e0b"><Paperclip /></el-icon>
            作业附件（{{ submission.attachments.length }}个）
          </div>
          <div v-for="(att, i) in submission.attachments" :key="i" class="flex items-center justify-between p-2 mb-1 bg-amber-50 rounded border border-amber-200">
            <div class="flex items-center gap-2 overflow-hidden">
              <el-icon :size="14" :color="att.fileType?.startsWith('image/') ? '#16a34a' : '#2563eb'">
                <PictureFilled v-if="att.fileType?.startsWith('image/')" />
                <Document v-else />
              </el-icon>
              <span class="text-xs truncate max-w-[200px]" :title="att.fileName">{{ att.fileName }}</span>
              <span class="text-xs text-gray-400 shrink-0">{{ formatAttachmentSize(att.fileSize) }}</span>
            </div>
            <div class="flex gap-1 shrink-0">
              <el-button size="small" text type="primary" @click="previewAttachment(att)">预览</el-button>
              <el-button size="small" text type="success" @click="downloadAttachment(att)">下载</el-button>
            </div>
          </div>
        </div>
      </el-card>

      <!-- 教师批改表单 -->
      <el-card v-if="submission">
        <template #header>
          <span class="font-semibold">✏️ 教师评分</span>
        </template>
        <el-form :model="form" label-width="100px">
          <el-form-item label="教师评分" required>
            <el-input-number
              v-model="form.teacherScore"
              :min="0"
              :max="100"
              :step="1"
              placeholder="请输入分数"
              class="!w-40"
            />
            <span class="text-gray-400 ml-2 text-sm">满分参考AI规则</span>
          </el-form-item>
          <el-form-item label="教师评语">
            <el-input
              v-model="form.teacherReviewContent"
              type="textarea"
              :rows="6"
              placeholder="请输入教师评语反馈..."
            />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="handleSubmit" :loading="submitting">
              提交评分
            </el-button>
            <el-button @click="goBack">取消</el-button>
          </el-form-item>
        </el-form>
      </el-card>

      <el-empty v-if="!loading && !submission" description="未找到提交记录" />
    </div>

    <!-- 文件预览对话框 -->
    <FilePreviewDialog ref="filePreviewRef" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft, Paperclip, Document, PictureFilled } from '@element-plus/icons-vue'
import { getSubmissionDetail, submitTeacherReview } from "@/api/correcting";
import FilePreviewDialog from "@/components/FilePreviewDialog.vue";
import type { SubmissionRecord } from '@/api/correcting'

const route = useRoute()
const router = useRouter()
const loading = ref(true)
const submitting = ref(false)
const submission = ref<SubmissionRecord | null>(null)
const form = ref({ teacherScore: 0, teacherReviewContent: '' })
const filePreviewRef = ref()

const goBack = () => router.back()

const formatContent = (content: string) => {
  if (!content) return ''
  return content
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/\n/g, '<br>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/(总分[：:]\s*\d+\s*分)/g, '<span style="color:#e53e3e;font-size:1.2em;font-weight:bold">$1</span>')
}

const formatAttachmentSize = (bytes: number) => {
  if (!bytes) return '0B'
  if (bytes < 1024) return bytes + 'B'
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + 'KB'
  return (bytes / 1048576).toFixed(1) + 'MB'
}

const downloadAttachment = (att: any) => {
  const token = localStorage.getItem('token')
  const filename = att.fileUrl.replace('/uploads/', '')
  fetch(`/api/upload/download/${filename}`, { headers: { Authorization: `Bearer ${token}` } })
    .then(res => res.blob())
    .then(blob => {
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url; a.download = att.fileName; a.click()
      URL.revokeObjectURL(url)
    })
    .catch(() => ElMessage.warning('下载失败'))
}

const previewAttachment = (att: any) => {
  filePreviewRef.value?.open(att);
}

const loadData = async () => {
  try {
    const submissionId = route.query.submissionId as string
    if (!submissionId) {
      ElMessage.error('缺少提交ID')
      router.back()
      return
    }
    const data = await getSubmissionDetail(submissionId)
    submission.value = data
    if (data.teacherScore != null) {
      form.value = { teacherScore: data.teacherScore, teacherReviewContent: data.teacherReviewContent || '' }
    } else if (data.aiScore != null) {
      form.value.teacherScore = data.aiScore
    }
  } catch (e: any) {
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

const handleSubmit = async () => {
  if (!submission.value) return
  if (form.value.teacherScore <= 0) {
    ElMessage.warning('请输入评分')
    return
  }
  submitting.value = true
  try {
    await submitTeacherReview({
      submissionId: submission.value._id,
      teacherReviewContent: form.value.teacherReviewContent,
      teacherScore: form.value.teacherScore,
    })
    ElMessage.success('评分提交成功')
    router.back()
  } catch (e: any) {
    ElMessage.error('提交失败')
  } finally {
    submitting.value = false
  }
}

onMounted(loadData)
</script>

<style scoped>
.submission-content {
  line-height: 1.8;
  max-height: 300px;
  overflow-y: auto;
}

.submission-content :deep(p) {
  margin: 0.5rem 0;
}

.submission-content :deep(img) {
  max-width: 100%;
  border-radius: 6px;
}
</style>
