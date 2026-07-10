<!-- 临时文档查重工具 -->
<template>
  <div class="plagiarism-container">
    <!-- 页面标题 -->
    <div class="page-header">
      <h2>文档查重工具</h2>
      <p>上传多份文档，一键查重，不依赖学生提交记录</p>
    </div>

    <!-- 步骤1: 上传文件 -->
    <el-card v-if="step === 'upload'" class="upload-card">
      <el-upload
        drag
        multiple
        :auto-upload="false"
        :show-file-list="false"
        accept=".docx,.txt,.pdf"
        @change="handleFileChange"
      >
        <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
        <div class="el-upload__text">拖拽文件到此处，或<em>点击选择</em></div>
        <template #tip>
          <div class="el-upload__tip">
            支持 .docx / .txt / .pdf 文件，至少需要2份文件。建议文件命名为「姓名_学号.docx」
          </div>
        </template>
      </el-upload>

      <!-- 模板文件上传（可选） -->
      <div class="template-section">
        <el-upload
          :auto-upload="false"
          :show-file-list="false"
          :limit="1"
          accept=".docx,.txt,.pdf"
          @change="handleTemplateChange"
        >
          <el-button type="info" plain :icon="Document">
            {{ templateFile ? templateFile.name : '上传任务书/模板（可选）' }}
          </el-button>
        </el-upload>
        <el-button v-if="templateFile" text type="danger" :icon="Delete" @click="templateFile = null" />
        <span class="template-tip">比对前自动剔除模板内容，避免“大家都抄了任务书”被误判</span>
      </div>

      <!-- 文件列表(可编辑姓名学号) -->
      <div v-if="parsedFiles.length > 0" class="file-list-section">
        <div class="file-list-header">
          <h4>文件列表 ({{ parsedFiles.length }} 份)</h4>
          <el-button text type="danger" :icon="Delete" @click="resetAll">清空全部</el-button>
        </div>
        <el-table :data="parsedFiles" stripe style="width: 100%" max-height="400">
          <el-table-column type="index" label="#" width="60" />
          <el-table-column prop="fileName" label="文件名" min-width="200" show-overflow-tooltip />
          <el-table-column label="姓名" width="150">
            <template #default="{ row }">
              <el-input v-model="row.name" placeholder="姓名" size="small" />
            </template>
          </el-table-column>
          <el-table-column label="学号" width="160">
            <template #default="{ row }">
              <el-input v-model="row.studentId" placeholder="学号" size="small" />
            </template>
          </el-table-column>
          <el-table-column label="操作" width="80" align="center">
            <template #default="{ $index }">
              <el-button text type="danger" :icon="Delete" @click="removeFile($index)" />
            </template>
          </el-table-column>
        </el-table>

        <div class="upload-actions">
          <el-button
            type="primary"
            size="large"
            :loading="checking"
            :disabled="parsedFiles.length < 2"
            @click="startCheck"
          >
            {{ checking ? "查重中，请稍候..." : "开始查重 (" + parsedFiles.length + " 份)" }}
          </el-button>
        </div>
      </div>
    </el-card>

    <!-- 步骤2: 查重结果 -->
    <div v-if="step === 'result'">
      <!-- 统计卡片 -->
      <el-row :gutter="16" class="summary-cards">
        <el-col :span="6">
          <el-card shadow="hover">
            <div class="summary-value">{{ result?.total }}</div>
            <div class="summary-label">参与查重</div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="hover">
            <div class="summary-value danger">{{ result?.suspectCount }}</div>
            <div class="summary-label">疑似抄袭</div>
          </el-card>
        </el-col>
        <el-col :span="6" v-if="result?.codeCheckEnabled">
          <el-card shadow="hover">
            <div class="summary-value danger">{{ result?.codeSuspectCount || 0 }}</div>
            <div class="summary-label">代码疑似</div>
          </el-card>
        </el-col>
        <el-col :span="6" v-if="result?.imageCheckEnabled">
          <el-card shadow="hover">
            <div class="summary-value danger">{{ result?.imageSuspectCount || 0 }}</div>
            <div class="summary-label">图片疑似</div>
          </el-card>
        </el-col>
        <el-col :span="6" v-if="!result?.codeCheckEnabled && !result?.imageCheckEnabled">
          <el-card shadow="hover">
            <div class="summary-value success">{{ (result?.total || 0) - (result?.suspectCount || 0) }}</div>
            <div class="summary-label">合格</div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="hover">
            <div class="summary-value">{{ result?.passRate }}%</div>
            <div class="summary-label">合格阈值</div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 操作按钮 -->
      <div class="result-actions">
        <el-button type="primary" :icon="Download" @click="downloadReport" :disabled="!result?.checkId">
          下载报告
        </el-button>
        <el-button @click="resetAll">重新查重</el-button>
      </div>

      <!-- 结果表格 -->
      <el-card>
        <el-table
          v-if="result && result.results.length > 0"
          :data="result.results"
          stripe
          :default-sort="{ prop: 'rate', order: 'descending' }"
        >
          <el-table-column type="index" label="排名" width="70" align="center" />
          <el-table-column prop="studentName" label="姓名" width="120" />
          <el-table-column prop="studentNumber" label="学号" width="140" />
          <el-table-column prop="phraseRate" label="片段重合度" width="120" align="center">
            <template #default="{ row }">
              <span :class="getRateClass(row.phraseRate)">{{ row.phraseRate }}%</span>
            </template>
          </el-table-column>
          <el-table-column prop="topicRate" label="主题相似度" width="120" align="center">
            <template #default="{ row }">
              <span :class="getRateClass(row.topicRate)">{{ row.topicRate }}%</span>
            </template>
          </el-table-column>
          <el-table-column prop="rate" label="综合重复率" width="120" align="center" sortable>
            <template #default="{ row }">
              <el-tag :type="row.status === '合格' ? 'success' : 'danger'" effect="dark" size="small">
                {{ row.rate !== null ? row.rate + '%' : '-' }}
              </el-tag>
            </template>
          </el-table-column>
          <!-- 代码查重列（仅在启用代码查重时显示） -->
          <el-table-column v-if="result?.codeCheckEnabled" prop="codeRate" label="代码重合度" width="120" align="center" sortable>
            <template #default="{ row }">
              <span v-if="row.codeRate !== null && row.codeRate !== undefined" :class="getRateClass(row.codeRate)">{{ row.codeRate }}%</span>
              <span v-else class="text-gray">-</span>
            </template>
          </el-table-column>
          <el-table-column v-if="result?.codeCheckEnabled" prop="codeStatus" label="代码判定" width="120" align="center">
            <template #default="{ row }">
              <el-tag v-if="row.codeStatus && row.codeStatus !== '-'" :type="row.codeStatus === '合格' ? 'success' : 'danger'" size="small">{{ row.codeStatus }}</el-tag>
              <span v-else class="text-gray">-</span>
            </template>
          </el-table-column>
          <!-- 图片查重列（仅在启用图片查重时显示） -->
          <el-table-column v-if="result?.imageCheckEnabled" prop="imageRate" label="图片重合度" width="120" align="center" sortable>
            <template #default="{ row }">
              <span v-if="row.imageRate !== null && row.imageRate !== undefined" :class="getRateClass(row.imageRate)">{{ row.imageRate }}%</span>
              <span v-else class="text-gray">-</span>
            </template>
          </el-table-column>
          <el-table-column v-if="result?.imageCheckEnabled" prop="matchedImageCount" label="复制图片" width="100" align="center">
            <template #default="{ row }">
              <span v-if="row.matchedImageCount > 0" class="rate-danger">{{ row.matchedImageCount }} 张</span>
              <span v-else class="text-gray">0</span>
            </template>
          </el-table-column>
          <el-table-column v-if="result?.imageCheckEnabled" prop="imageStatus" label="图片判定" width="120" align="center">
            <template #default="{ row }">
              <el-tag v-if="row.imageStatus && row.imageStatus !== '-'" :type="row.imageStatus === '合格' ? 'success' : 'danger'" size="small">{{ row.imageStatus }}</el-tag>
              <span v-else class="text-gray">-</span>
            </template>
          </el-table-column>
          <el-table-column label="最相似对象" min-width="160">
            <template #default="{ row }">
              <span v-if="row.matchName !== '-'">{{ row.matchName }} ({{ row.matchId }})</span>
              <span v-else class="text-gray">-</span>
            </template>
          </el-table-column>
          <el-table-column prop="suspectReason" label="疑似原因" width="140" align="center" fixed="right">
            <template #default="{ row }">
              <el-tag v-if="row.suspectReason" type="danger" effect="dark" size="small">{{ row.suspectReason }}</el-tag>
              <el-tag v-else type="success" size="small">合格</el-tag>
            </template>
          </el-table-column>
        </el-table>

        <!-- 跳过的文件 -->
        <el-alert
          v-if="result && result.skipped.length > 0"
          type="info"
          show-icon
          :closable="false"
          style="margin-top: 16px"
        >
          <template #title>
            以下 {{ result.skipped.length }} 份文件未纳入查重：
          </template>
          <div v-for="(s, i) in result.skipped" :key="i" style="font-size: 13px; line-height: 1.8">
            {{ s.fileName || s.studentName }} — {{ s.reason }}
          </div>
        </el-alert>
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { UploadFilled, Download, Delete, Document } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";
import type { UploadFile } from "element-plus";
import { adhocCheck, type AdhocCheckResult } from "@/api/plagiarism";

interface ParsedFile {
  raw: File;
  fileName: string;
  name: string;
  studentId: string;
}

const step = ref<"upload" | "result">("upload");
const checking = ref(false);
const parsedFiles = ref<ParsedFile[]>([]);
const result = ref<AdhocCheckResult | null>(null);
const templateFile = ref<File | null>(null);

/** 模板文件选择回调 */
const handleTemplateChange = (file: any) => {
  const raw = file.raw || file;
  if (raw) {
    templateFile.value = raw;
  }
};

/** 文件选择回调 — 支持多选 */
const handleFileChange = (file: any) => {
  console.log("file change triggered:", file?.name);
  // el-upload on-change 传的是单个 file 对象
  const raw = file.raw || file;
  if (!raw) {
    console.error("no raw file");
    return;
  }
  const fileName = file.name || raw.name || "unknown.docx";
  // 避免重复添加
  if (parsedFiles.value.some((f) => f.fileName === fileName)) {
    return;
  }
  // 解析 姓名_学号
  const dotIdx = fileName.lastIndexOf(".");
  const base = dotIdx > 0 ? fileName.substring(0, dotIdx) : fileName;
  const underIdx = base.indexOf("_");
  const name = underIdx >= 0 ? base.substring(0, underIdx).trim() : base.trim();
  const studentId = underIdx >= 0 ? base.substring(underIdx + 1).trim() : "";
  parsedFiles.value.push({
    raw: raw,
    fileName,
    name,
    studentId,
  });
  console.log("added file, total:", parsedFiles.value.length);
};

/** 删除单个文件 */
const removeFile = (index: number) => {
  parsedFiles.value.splice(index, 1);
};

/** 开始查重 */
const startCheck = async () => {
  if (parsedFiles.value.length < 2) {
    ElMessage.warning("至少需要2份文件才能进行查重比对");
    return;
  }
  checking.value = true;
  try {
    const files = parsedFiles.value.map((f) => f.raw);
    result.value = await adhocCheck(files, templateFile.value);
    step.value = "result";
    if (result.value.results.length === 0) {
      ElMessage.warning(result.value.message || "查重无结果");
    } else {
      ElMessage.success(`查重完成：${result.value.suspectCount} 人疑似抄袭`);
    }
  } catch (error: any) {
    ElMessage.error(error.message || "查重失败，请重试");
  } finally {
    checking.value = false;
  }
};

/** 下载报告 */
const downloadReport = () => {
  if (!result.value?.checkId) return;
  const url = `/api/plagiarism/${result.value.checkId}/report`;
  const token = localStorage.getItem("token");
  fetch(url, {
    headers: { Authorization: `Bearer ${token}` },
  })
    .then((res) => res.blob())
    .then((blob) => {
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `查重报告_${new Date().toLocaleString("zh-CN").replace(/[/\s:]/g, "")}.xlsx`;
      a.click();
      URL.revokeObjectURL(a.href);
    })
    .catch(() => ElMessage.error("下载失败"));
};

/** 重复率颜色 */
const getRateClass = (rate: number) => {
  if (rate >= 50) return "rate-danger";
  if (rate >= 30) return "rate-warning";
  return "rate-normal";
};

/** 重置 */
const resetAll = () => {
  step.value = "upload";
  parsedFiles.value = [];
  result.value = null;
  templateFile.value = null;
};
</script>

<style scoped>
.plagiarism-container {
  padding: 20px;
}

.page-header {
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0 0 8px 0;
  font-size: 22px;
  color: #1f2937;
}

.page-header p {
  margin: 0;
  font-size: 14px;
  color: #6b7280;
}

.upload-card {
  margin-bottom: 20px;
}

.template-section {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 16px;
  padding: 12px 16px;
  background: #f0f7ff;
  border-radius: 8px;
  border: 1px dashed #a0c4e8;
}

.template-tip {
  font-size: 12px;
  color: #6b7280;
}

.file-list-section {
  margin-top: 24px;
}

.file-list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.file-list-header h4 {
  margin: 0;
  font-size: 16px;
  color: #1f2937;
}

.upload-actions {
  margin-top: 20px;
  display: flex;
  justify-content: center;
}

.summary-cards {
  margin-bottom: 20px;
}

.summary-value {
  font-size: 28px;
  font-weight: 700;
  color: #1f2937;
  text-align: center;
}

.summary-value.danger {
  color: #ef4444;
}

.summary-value.success {
  color: #22c55e;
}

.summary-label {
  font-size: 13px;
  color: #9ca3af;
  margin-top: 4px;
  text-align: center;
}

.result-actions {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}

.rate-danger {
  color: #ef4444;
  font-weight: 600;
}

.rate-warning {
  color: #f59e0b;
  font-weight: 600;
}

.rate-normal {
  color: #22c55e;
}

.text-gray {
  color: #9ca3af;
}
</style>
