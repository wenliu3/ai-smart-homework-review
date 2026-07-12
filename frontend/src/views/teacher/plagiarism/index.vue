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
          <el-button size="large" :icon="Setting" @click="configDialogVisible = true">
            参数设置
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
          <el-table-column label="操作" width="100" align="center" fixed="right">
            <template #default="{ row }">
              <el-button
                v-if="row.matchSubmissionId"
                type="primary"
                size="small"
                link
                @click="openCompare(row)"
              >
                对比
              </el-button>
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

    <!-- 对比预览弹窗 -->
    <el-dialog
      v-model="compareVisible"
      title="查重对比预览 — 命中片段标黄"
      width="95%"
      top="3vh"
      class="compare-dialog"
      :close-on-click-modal="false"
    >
      <div v-loading="compareLoading" class="compare-container">
        <div class="compare-hit-count" v-if="compareData">
          共 {{ compareData.snippets.length }} 个命中片段，黄色标记的句子与对方重合
        </div>
        <el-row :gutter="12">
          <el-col :span="12">
            <div class="compare-panel">
              <div class="compare-header">
                <el-icon><User /></el-icon>
                <span class="compare-name">{{ compareData?.studentA?.name }}</span>
                <span class="compare-number">({{ compareData?.studentA?.number || '-' }})</span>
              </div>
              <div class="compare-text" ref="compareTextARef"></div>
            </div>
          </el-col>
          <el-col :span="12">
            <div class="compare-panel">
              <div class="compare-header">
                <el-icon><User /></el-icon>
                <span class="compare-name">{{ compareData?.studentB?.name }}</span>
                <span class="compare-number">({{ compareData?.studentB?.number || '-' }})</span>
              </div>
              <div class="compare-text" ref="compareTextBRef"></div>
            </div>
          </el-col>
        </el-row>
      </div>
    </el-dialog>

    <!-- 参数配置弹窗 -->
    <el-dialog v-model="configDialogVisible" title="查重参数设置" width="500px">
      <el-form label-width="130px" label-position="left">
        <el-form-item label="合格阈值">
          <div class="config-row">
            <el-slider v-model="configForm.passRate" :min="1" :max="100" :step="1" show-input style="flex: 1" />
            <span class="config-unit">%</span>
          </div>
        </el-form-item>
        <el-form-item label="片段重合度权重">
          <el-slider v-model="configForm.phraseWeight" :min="0" :max="1" :step="0.05" show-input style="width: 100%" />
        </el-form-item>
        <el-form-item label="主题相似度权重">
          <el-slider v-model="configForm.topicWeight" :min="0" :max="1" :step="0.05" show-input style="width: 100%" />
        </el-form-item>
      </el-form>
      <el-alert type="info" :closable="false" style="margin-top: 8px">
        综合重复率 = 片段重合度 × 片段权重 + 主题相似度 × 主题权重<br />
        超过合格阈值即判定为"疑似抄袭"
      </el-alert>
      <template #footer>
        <el-button @click="resetConfig">重置默认</el-button>
        <el-button type="primary" @click="confirmConfig">确认</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, watch, computed, nextTick } from "vue";
import { UploadFilled, Download, Delete, Document, Setting, User } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";
import type { UploadFile } from "element-plus";
import { renderAsync } from "docx-preview";
import { adhocCheck, compareFiles, type AdhocCheckResult, type CompareResult } from "@/api/plagiarism";

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

// 查重参数配置
const DEFAULT_CONFIG = { passRate: 30, phraseWeight: 0.6, topicWeight: 0.4 };
const configDialogVisible = ref(false);
const configForm = reactive({ ...DEFAULT_CONFIG });
const plagiarismConfig = ref<{ passRate?: number; phraseWeight?: number; topicWeight?: number } | null>(null);

const resetConfig = () => {
  configForm.passRate = DEFAULT_CONFIG.passRate;
  configForm.phraseWeight = DEFAULT_CONFIG.phraseWeight;
  configForm.topicWeight = DEFAULT_CONFIG.topicWeight;
};

const confirmConfig = () => {
  plagiarismConfig.value = { ...configForm };
  configDialogVisible.value = false;
  ElMessage.success("参数已更新，下次查重将使用新参数");
};

// 权重联动：片段权重 + 主题权重 = 1
let _weightUpdating = false;
watch(() => configForm.phraseWeight, (val) => {
  if (_weightUpdating) return;
  _weightUpdating = true;
  configForm.topicWeight = Math.round((1 - val) * 100) / 100;
  _weightUpdating = false;
});
watch(() => configForm.topicWeight, (val) => {
  if (_weightUpdating) return;
  _weightUpdating = true;
  configForm.phraseWeight = Math.round((1 - val) * 100) / 100;
  _weightUpdating = false;
});

// ====== 对比预览 ======
const compareVisible = ref(false);
const compareLoading = ref(false);
const compareData = ref<CompareResult | null>(null);
const compareTextARef = ref<HTMLElement | null>(null);
const compareTextBRef = ref<HTMLElement | null>(null);

const NGRAM_SIZE = 10;
const HIT_RATIO_THRESHOLD = 0.6;
const MIN_HITS = 2;

/** 与后端一致的清洗逻辑 */
function cleanChars(s: string): string {
  return s.replace(/[^\u4e00-\u9fff a-zA-Z]/g, "").replace(/\s/g, "").toLowerCase();
}

/** 与后端一致的 n-gram 生成 */
function getSentenceNgramSet(text: string, n: number): Set<string> {
  const grams = new Set<string>();
  const sentences = text.split(/[。！？；\n\r]+/);
  for (const sentence of sentences) {
    const cleaned = cleanChars(sentence);
    if (cleaned.length < n) continue;
    for (let i = 0; i <= cleaned.length - n; i++) {
      grams.add(cleaned.substring(i, i + n));
    }
  }
  return grams;
}

/** DOM 级标黄：按段落块遍历，命中率达阈值且命中数达最低要求的整块标黄 */
function applyDomHighlighting(element: HTMLElement | null, snippets: string[]) {
  if (!element || !snippets || snippets.length === 0) return;
  const snippetSet = new Set(snippets);
  const blocks = Array.from(
    element.querySelectorAll("p, li, td, th, h1, h2, h3, h4, h5, h6, pre, blockquote")
  );
  for (let i = blocks.length - 1; i >= 0; i--) {
    const block = blocks[i];
    if (block.classList.contains("hl-hit")) continue;
    if (block.querySelector(".hl-hit")) continue;
    const text = block.textContent || "";
    if (!text.trim()) continue;
    const blockNgrams = getSentenceNgramSet(text, NGRAM_SIZE);
    if (blockNgrams.size === 0) continue;
    let hitCount = 0;
    for (const ng of blockNgrams) {
      if (snippetSet.has(ng)) hitCount++;
    }
    const ratio = hitCount / blockNgrams.size;
    if (ratio >= HIT_RATIO_THRESHOLD && hitCount >= MIN_HITS) {
      block.classList.add("hl-hit");
    }
  }
}

/** 渲染单个提交内容（docx 用 docx-preview 渲染原始 Word，其他用 innerHTML） */
async function renderSubmission(
  container: HTMLElement | null,
  fileInfo: { fileUrl: string; ext: string; fileName: string } | null,
  contentHtml: string
): Promise<void> {
  if (!container) return;
  container.innerHTML = "";

  if (fileInfo && fileInfo.ext === ".docx" && fileInfo.fileUrl) {
    try {
      const res = await fetch(fileInfo.fileUrl);
      const blob = await res.blob();
      await renderAsync(blob, container, undefined, {
        className: "docx",
        inWrapper: true,
        ignoreWidth: false,
        ignoreHeight: false,
        breakPages: true,
      });
    } catch {
      container.innerHTML = "<p>Word 渲染失败，显示纯文本：</p>";
      container.innerHTML += contentHtml || "<p>（无内容）</p>";
    }
  } else if (contentHtml) {
    container.innerHTML = contentHtml;
  } else {
    container.innerHTML = "<p>（无内容）</p>";
  }
}

/** 数据加载后渲染内容（docx 用 docx-preview）+ 标黄 */
watch(compareData, async (val) => {
  if (!val) return;
  await nextTick();
  compareLoading.value = true;
  try {
    // 并行渲染两侧
    await Promise.all([
      renderSubmission(compareTextARef.value, val.fileA, val.contentHtmlA),
      renderSubmission(compareTextBRef.value, val.fileB, val.contentHtmlB),
    ]);
    // 渲染完成后标黄
    applyDomHighlighting(compareTextARef.value, val.snippets);
    applyDomHighlighting(compareTextBRef.value, val.snippets);
  } finally {
    compareLoading.value = false;
  }
});

/** 打开对比预览 */
const openCompare = async (row: any) => {
  if (!result.value?.checkId || !row.submissionId || !row.matchSubmissionId) return;
  compareVisible.value = true;
  compareLoading.value = true;
  compareData.value = null;
  try {
    compareData.value = await compareFiles(
      result.value.checkId,
      Number(row.submissionId),
      Number(row.matchSubmissionId),
    );
  } catch (error: any) {
    ElMessage.error(error.message || "加载对比数据失败，可能已过期，请重新查重");
    compareVisible.value = false;
  } finally {
    compareLoading.value = false;
  }
};

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
    result.value = await adhocCheck(files, templateFile.value, plagiarismConfig.value || undefined);
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
const downloadReport = async () => {
  if (!result.value?.checkId) return;
  const url = `/api/plagiarism/${result.value.checkId}/report`;
  const token = localStorage.getItem("token");
  try {
    const res = await fetch(url, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) {
      const errorData = await res.json().catch(() => null);
      ElMessage.error(errorData?.message || `下载失败 (HTTP ${res.status})`);
      return;
    }
    const blob = await res.blob();
    if (blob.size === 0 || blob.type.includes("application/json")) {
      ElMessage.error("下载失败：服务器未返回有效文件，可能查重结果已过期");
      return;
    }
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `查重报告_${new Date().toLocaleString("zh-CN").replace(/[/\s:]/g, "")}.xlsx`;
    a.click();
    URL.revokeObjectURL(a.href);
    ElMessage.success("报告下载成功");
  } catch (error) {
    ElMessage.error("下载失败，请重试");
  }
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

.config-row {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
}

.config-unit {
  font-size: 14px;
  color: #6b7280;
}

/* 对比预览 */
.compare-dialog .el-dialog__body {
  padding: 12px 20px;
}

.compare-container {
  min-height: 400px;
}

.compare-hit-count {
  font-size: 13px;
  color: #92400e;
  background: #fef3c7;
  border-radius: 6px;
  padding: 8px 12px;
  margin-bottom: 12px;
}

.compare-panel {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  overflow: hidden;
  height: 70vh;
  display: flex;
  flex-direction: column;
}

.compare-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 14px;
  background: #f8fafc;
  border-bottom: 1px solid #e5e7eb;
  font-size: 15px;
}

.compare-name {
  font-weight: 600;
  color: #1f2937;
}

.compare-number {
  color: #9ca3af;
  font-size: 13px;
}

.compare-text {
  flex: 1;
  overflow-y: auto;
  padding: 16px 24px;
  font-size: 14px;
  line-height: 1.8;
  color: #374151;
  word-break: break-word;
}

.compare-text :deep(h1),
.compare-text :deep(h2),
.compare-text :deep(h3),
.compare-text :deep(h4) {
  margin: 16px 0 8px 0;
  font-weight: 600;
  color: #1f2937;
}
.compare-text :deep(h1) { font-size: 20px; }
.compare-text :deep(h2) { font-size: 17px; }
.compare-text :deep(h3) { font-size: 15px; }
.compare-text :deep(h4) { font-size: 14px; }

.compare-text :deep(p) {
  margin: 6px 0;
}

.compare-text :deep(table) {
  border-collapse: collapse;
  width: 100%;
  margin: 8px 0;
}
.compare-text :deep(td),
.compare-text :deep(th) {
  border: 1px solid #d1d5db;
  padding: 6px 10px;
  font-size: 13px;
}
.compare-text :deep(th) {
  background: #f3f4f6;
  font-weight: 600;
}

.compare-text :deep(strong) {
  font-weight: 600;
}

.compare-text :deep(img) {
  max-width: 100%;
  height: auto;
  margin: 8px 0;
}

.compare-text :deep(ul),
.compare-text :deep(ol) {
  margin: 6px 0;
  padding-left: 24px;
}

.compare-text :deep(li) {
  margin: 3px 0;
}

.compare-text :deep(pre) {
  background: #f8fafc;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  padding: 12px;
  overflow-x: auto;
  font-size: 13px;
  line-height: 1.6;
}

.compare-text :deep(.hl-hit) {
  background: #fef08a;
  box-shadow: inset 4px 0 0 #f59e0b;
  border-radius: 2px;
}

/* docx-preview 容器样式 */
.compare-text :deep(.docx-wrapper) {
  background: transparent;
  padding: 0;
}

.compare-text :deep(.docx-wrapper > .docx) {
  box-shadow: none;
  margin: 0 auto;
  max-width: 100%;
}
</style>
