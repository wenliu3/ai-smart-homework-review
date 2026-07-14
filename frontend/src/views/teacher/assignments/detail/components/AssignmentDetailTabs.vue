<template>
  <div class="assignment-detail-tabs">
    <el-tabs v-model="activeTab" type="border-card" class="detail-tabs">
      <el-tab-pane name="submissions" class="tab-pane">
        <template #label>
          <div class="tab-label">
            <el-icon><User /></el-icon>
            <span>提交学生列表</span>
            <el-badge
              v-if="submissionStats"
              :value="submissionStats.totalSubmissions"
              class="tab-badge"
              :max="999"
            />
          </div>
        </template>

        <div class="tab-content">
          <!-- 搜索区域 -->
          <div class="search-section">
            <slot name="search" />
          </div>

          <!-- 表格区域 -->
          <div class="table-section">
            <slot name="table" />
          </div>

          <!-- 分页区域 -->
          <div class="pagination-section">
            <slot name="pagination" />
          </div>
        </div>
      </el-tab-pane>

      <!-- 作业查重 Tab -->
      <el-tab-pane name="plagiarism" class="tab-pane">
        <template #label>
          <div class="tab-label">
            <el-icon><CopyDocument /></el-icon>
            <span>作业查重</span>
          </div>
        </template>

        <div class="tab-content">
          <!-- 查重操作区 -->
          <div class="plagiarism-action">
            <div class="action-left">
              <h3>作业查重分析</h3>
              <p class="action-desc">
                对当前作业所有已提交的学生作业进行两两比对，识别疑似抄袭。
                <br /><span class="highlight">文本维度</span>：片段重合度(整句照抄) + 主题相似度(改写/打乱)。
                <br /><span class="highlight">代码维度</span>：token归一化 + winnowing指纹（抓改名/改结构）。
                <br /><span class="highlight">图片维度</span>：感知哈希aHash+dHash（抓截图复制粘贴）。
              </p>
            </div>
            <div class="action-buttons">
              <el-button
                type="primary"
                :icon="Search"
                :loading="plagiarismLoading"
                @click="runPlagiarismCheck"
              >
                {{ plagiarismLoading ? "查重中..." : "开始查重" }}
              </el-button>
              <el-button :icon="Setting" @click="configDialogVisible = true">
                参数设置
              </el-button>
            </div>
          </div>

          <!-- 模板上传（可选） -->
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

          <!-- 查重结果 -->
          <div v-if="plagiarismResult" class="plagiarism-result">
            <!-- 汇总卡片 -->
            <el-row :gutter="16" class="summary-cards">
              <el-col :span="6">
                <el-card shadow="hover" class="summary-card">
                  <div class="summary-value">{{ plagiarismResult.total }}</div>
                  <div class="summary-label">参与查重</div>
                </el-card>
              </el-col>
              <el-col :span="6">
                <el-card shadow="hover" class="summary-card">
                  <div class="summary-value danger">{{ plagiarismResult.suspectCount }}</div>
                  <div class="summary-label">疑似抄袭</div>
                </el-card>
              </el-col>
              <el-col :span="6" v-if="plagiarismResult.codeCheckEnabled">
                <el-card shadow="hover" class="summary-card">
                  <div class="summary-value danger">{{ plagiarismResult.codeSuspectCount || 0 }}</div>
                  <div class="summary-label">代码疑似</div>
                </el-card>
              </el-col>
              <el-col :span="6" v-if="plagiarismResult.imageCheckEnabled">
                <el-card shadow="hover" class="summary-card">
                  <div class="summary-value danger">{{ plagiarismResult.imageSuspectCount || 0 }}</div>
                  <div class="summary-label">图片疑似</div>
                </el-card>
              </el-col>
              <el-col :span="6" v-if="!plagiarismResult.codeCheckEnabled && !plagiarismResult.imageCheckEnabled">
                <el-card shadow="hover" class="summary-card">
                  <div class="summary-value success">{{ plagiarismResult.total - plagiarismResult.suspectCount }}</div>
                  <div class="summary-label">合格</div>
                </el-card>
              </el-col>
              <el-col :span="6">
                <el-card shadow="hover" class="summary-card">
                  <div class="summary-value">{{ plagiarismResult.passRate }}%</div>
                  <div class="summary-label">合格阈值</div>
                </el-card>
              </el-col>
            </el-row>

            <!-- 消息提示 -->
            <el-alert
              v-if="plagiarismResult.message"
              :title="plagiarismResult.message"
              type="warning"
              show-icon
              :closable="false"
              style="margin-bottom: 16px"
            />

            <!-- 查重结果表格 -->
            <el-table
              v-if="plagiarismResult.results.length > 0"
              :data="plagiarismResult.results"
              stripe
              style="width: 100%"
              :default-sort="{ prop: 'rate', order: 'descending' }"
            >
              <el-table-column type="index" label="排名" width="70" align="center" />
              <el-table-column prop="studentName" label="姓名" width="100" />
              <el-table-column prop="studentNumber" label="学号" width="120" />
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
                    {{ row.rate }}%
                  </el-tag>
                </template>
              </el-table-column>
              <!-- 代码查重列（仅在启用代码查重时显示） -->
              <el-table-column v-if="plagiarismResult.codeCheckEnabled" prop="codeRate" label="代码重合度" width="120" align="center" sortable>
                <template #default="{ row }">
                  <span v-if="row.codeRate !== null && row.codeRate !== undefined" :class="getRateClass(row.codeRate)">{{ row.codeRate }}%</span>
                  <span v-else class="text-gray">-</span>
                </template>
              </el-table-column>
              <el-table-column v-if="plagiarismResult.codeCheckEnabled" prop="codeStatus" label="代码判定" width="120" align="center">
                <template #default="{ row }">
                  <el-tag v-if="row.codeStatus && row.codeStatus !== '-'" :type="row.codeStatus === '合格' ? 'success' : 'danger'" size="small">{{ row.codeStatus }}</el-tag>
                  <span v-else class="text-gray">-</span>
                </template>
              </el-table-column>
              <!-- 图片查重列（仅在启用图片查重时显示） -->
              <el-table-column v-if="plagiarismResult.imageCheckEnabled" prop="imageRate" label="图片重合度" width="120" align="center" sortable>
                <template #default="{ row }">
                  <span v-if="row.imageRate !== null && row.imageRate !== undefined" :class="getRateClass(row.imageRate)">{{ row.imageRate }}%</span>
                  <span v-else class="text-gray">-</span>
                </template>
              </el-table-column>
              <el-table-column v-if="plagiarismResult.imageCheckEnabled" prop="matchedImageCount" label="复制图片" width="100" align="center">
                <template #default="{ row }">
                  <span v-if="row.matchedImageCount > 0" class="rate-danger">{{ row.matchedImageCount }} 张</span>
                  <span v-else class="text-gray">0</span>
                </template>
              </el-table-column>
              <el-table-column v-if="plagiarismResult.imageCheckEnabled" prop="imageStatus" label="图片判定" width="120" align="center">
                <template #default="{ row }">
                  <el-tag v-if="row.imageStatus && row.imageStatus !== '-'" :type="row.imageStatus === '合格' ? 'success' : 'danger'" size="small">{{ row.imageStatus }}</el-tag>
                  <span v-else class="text-gray">-</span>
                </template>
              </el-table-column>
              <el-table-column label="最相似对象" min-width="160">
                <template #default="{ row }">
                  <span v-if="row.matchName !== '-'">
                    {{ row.matchName }} ({{ row.matchId }})
                  </span>
                  <span v-else class="text-gray">-</span>
                </template>
              </el-table-column>
              <el-table-column prop="suspectReason" label="疑似原因" width="140" align="center" fixed="right">
                <template #default="{ row }">
                  <el-tag v-if="row.suspectReason" type="danger" effect="dark" size="small">{{ row.suspectReason }}</el-tag>
                  <el-tag v-else type="success" size="small">合格</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="160" align="center" fixed="right">
                <template #default="{ row }">
                  <el-button
                    v-if="row.matchSubmissionId"
                    type="primary"
                    link
                    size="small"
                    :icon="Document"
                    @click="openCompare(row)"
                  >
                    对比预览
                  </el-button>
                  <el-button
                    type="warning"
                    link
                    size="small"
                    @click="openSuggestion(row)"
                  >
                    AI建议
                  </el-button>
                </template>
              </el-table-column>
            </el-table>

            <!-- 跳过的作业 -->
            <el-alert
              v-if="plagiarismResult.skipped.length > 0"
              type="info"
              show-icon
              :closable="false"
              style="margin-top: 16px"
            >
              <template #title>
                以下 {{ plagiarismResult.skipped.length }} 份作业因内容过少未纳入查重：
              </template>
              <div v-for="(s, i) in plagiarismResult.skipped" :key="i" style="font-size: 13px; line-height: 1.8">
                {{ s.studentName }} ({{ s.studentNumber }}) — {{ s.reason }}
              </div>
            </el-alert>
          </div>

          <!-- 空状态 -->
          <el-empty
            v-else
            description="点击「开始查重」按钮，对所有学生提交进行查重分析"
            :image-size="120"
          >
            <template #image>
              <el-icon size="80" color="#c0c4cc"><CopyDocument /></el-icon>
            </template>
          </el-empty>

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

          <!-- 对比预览弹窗 -->
          <el-dialog
            v-model="compareVisible"
            title="查重对比预览 — 命中片段标黄"
            width="95%"
            top="3vh"
            class="compare-dialog"
            :close-on-click-modal="false"
            @opened="onCompareDialogOpened"
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
                      <span class="compare-number">({{ compareData?.studentA?.number }})</span>
                    </div>
                    <div class="compare-text" ref="compareTextARef"></div>
                  </div>
                </el-col>
                <el-col :span="12">
                  <div class="compare-panel">
                    <div class="compare-header">
                      <el-icon><User /></el-icon>
                      <span class="compare-name">{{ compareData?.studentB?.name }}</span>
                      <span class="compare-number">({{ compareData?.studentB?.number }})</span>
                    </div>
                    <div class="compare-text" ref="compareTextBRef"></div>
                  </div>
                </el-col>
              </el-row>
              <!-- AI 对比建议 -->
              <div class="compare-suggestion" v-if="compareData">
                <el-button type="warning" :loading="compareSuggestionLoading" @click="openCompareSuggestion">
                  AI 对比建议
                </el-button>
                <div v-if="compareSuggestionText" class="suggestion-content">
                  {{ compareSuggestionText }}
                </div>
              </div>
            </div>
          </el-dialog>

          <!-- AI 建议弹窗 -->
          <el-dialog v-model="suggestionVisible" title="AI 作业建议" width="600px">
            <div v-loading="suggestionLoading">
              <div v-if="suggestionStudentName" class="suggestion-header">
                学生：{{ suggestionStudentName }}
              </div>
              <div v-if="suggestionText" class="suggestion-content">{{ suggestionText }}</div>
              <el-empty v-else-if="!suggestionLoading" description="暂无建议" />
            </div>
          </el-dialog>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, nextTick, watch } from "vue";
import { User, CopyDocument, Search, Document, Delete, Setting } from "@element-plus/icons-vue";
import type { UploadFile } from "element-plus";
import { ElMessage } from "element-plus";
import { checkPlagiarism, compareSubmissions, getAiSuggestion, type PlagiarismResult, type CompareResult, type CompareFileInfo, type PlagiarismConfig } from "@/api/assignments";

interface Props {
  assignmentId?: string;
  submissionStats?: {
    totalSubmissions: number;
    reviewedSubmissions: number;
    pendingSubmissions: number;
    draftSubmissions: number;
  } | null;
}

const props = defineProps<Props>();

// 当前激活的Tab
const activeTab = ref("submissions");

// 查重状态
const plagiarismLoading = ref(false);
const plagiarismResult = ref<PlagiarismResult | null>(null);
const templateFile = ref<File | null>(null);

// 查重参数配置
const DEFAULT_CONFIG = { passRate: 30, phraseWeight: 0.6, topicWeight: 0.4 };
const configDialogVisible = ref(false);
const configForm = reactive({ ...DEFAULT_CONFIG });
const plagiarismConfig = ref<PlagiarismConfig | null>(null);

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

/** 模板文件选择 */
const handleTemplateChange = (file: UploadFile) => {
  if (file.raw) {
    templateFile.value = file.raw;
  }
};

/** 执行查重 */
const runPlagiarismCheck = async () => {
  if (!props.assignmentId) {
    ElMessage.warning("无法获取作业ID");
    return;
  }
  plagiarismLoading.value = true;
  try {
    plagiarismResult.value = await checkPlagiarism(props.assignmentId, templateFile.value, plagiarismConfig.value || undefined);
    if (plagiarismResult.value.results.length === 0) {
      ElMessage.warning(plagiarismResult.value.message || "暂无足够的提交进行查重");
    } else {
      ElMessage.success(`查重完成：${plagiarismResult.value.suspectCount} 人疑似抄袭`);
    }
  } catch (error: any) {
    ElMessage.error(error.message || "查重失败，请重试");
  } finally {
    plagiarismLoading.value = false;
  }
};

/** 重复率颜色 */
const getRateClass = (rate: number) => {
  if (rate >= 50) return "rate-danger";
  if (rate >= 30) return "rate-warning";
  return "rate-normal";
};

// ====== 对比预览 ======
const compareVisible = ref(false);
const compareLoading = ref(false);
const compareData = ref<CompareResult | null>(null);
const compareTextARef = ref<HTMLElement | null>(null);
const compareTextBRef = ref<HTMLElement | null>(null);
const dialogReady = ref(false);  // true 表示弹窗动画完成、容器宽度已稳定

// 当前对比的行数据（供对比弹窗 AI 建议使用）
const compareRowData = ref<any>(null);

// ====== AI 建议 ======
const suggestionVisible = ref(false);
const suggestionLoading = ref(false);
const suggestionText = ref("");
const suggestionStudentName = ref("");
const compareSuggestionLoading = ref(false);
const compareSuggestionText = ref("");

const NGRAM_SIZE = 10; // 与后端 PHRASE_NGRAM 一致
const HIT_RATIO_THRESHOLD = 0.6; // 段落 n-gram 命中率超过 60% 才标黄
const MIN_HITS = 2; // 至少命中 2 个 n-gram 才标黄，避免短段落误匹配

/** 与后端一致的清洗逻辑：只保留中文汉字和英文字母，英文统一转小写 */
function cleanChars(s: string): string {
  return s.replace(/[^\u4e00-\u9fff a-zA-Z]/g, "").replace(/\s/g, "").toLowerCase();
}

/** 与后端一致的 n-gram 生成：先按句分割（不跨句），再为每句生成 n-gram
 *  注意：不添加短碎片（len < n），因为后端 snippets 只含 len >= n 的 gram */
function getSentenceNgramSet(text: string, n: number): Set<string> {
  const grams = new Set<string>();
  // 按句末标点和换行分割（与后端 split_sentences 一致）
  const sentences = text.split(/[。！？；\n\r]+/);
  for (const sentence of sentences) {
    const cleaned = cleanChars(sentence);
    if (cleaned.length < n) continue; // 短于 n 的句子跳过，不生成碎片
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

  // 块级元素（不含 div/span，避免容器被标黄）
  const blocks = Array.from(
    element.querySelectorAll("p, li, td, th, h1, h2, h3, h4, h5, h6, pre, blockquote")
  );

  // 逆序遍历：子元素先处理，父元素被子元素标记后自动跳过
  for (let i = blocks.length - 1; i >= 0; i--) {
    const block = blocks[i];
    if (block.classList.contains("hl-hit")) continue;
    if (block.querySelector(".hl-hit")) continue; // 子元素已标黄，跳过父元素

    const text = block.textContent || "";
    if (!text.trim()) continue;

    // 与后端一致：按句分割生成 n-gram（不跨句）
    const blockNgrams = getSentenceNgramSet(text, NGRAM_SIZE);
    if (blockNgrams.size === 0) continue;

    let hitCount = 0;
    for (const ng of blockNgrams) {
      if (snippetSet.has(ng)) hitCount++;
    }
    // 命中数达标即标黄（段落含 >=2 个重合 ngram 说明有重合内容）
    if (hitCount >= MIN_HITS) {
      block.classList.add("hl-hit");
    }
  }
}

/** 渲染单个提交内容 — 直接用 contentHtml（mammoth 转的 HTML），稳定且支持 DOM 标黄 */
async function renderSubmission(
  container: HTMLElement | null,
  fileInfo: CompareFileInfo | null,
  contentHtml: string
): Promise<void> {
  if (!container) return;
  container.innerHTML = contentHtml || "<p>（无内容）</p>";
}

/** EMF/WMF 占位图 SVG */
const UNSUPPORTED_IMG_PLACEHOLDER = `data:image/svg+xml,${encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" width="200" height="80"><rect width="200" height="80" fill="#fef2f2" stroke="#ef4444" stroke-width="1.5" rx="4"/><text x="100" y="35" text-anchor="middle" font-family="sans-serif" font-size="12" fill="#991b1b">⚠ 浏览器不支持此图片格式</text><text x="100" y="55" text-anchor="middle" font-family="sans-serif" font-size="11" fill="#b91c1c">建议用 PNG/JPG 替代后重新上传</text></svg>`)}`;

function getImageIssue(img: HTMLImageElement): string {
  const src = img.getAttribute("src") || "";
  if (!src) return "src 为空，可能 rel 关系缺失或图片文件损坏";
  const lower = src.toLowerCase();
  if (lower.includes("image/x-emf") || lower.includes("image/emf") || lower.includes(".emf")) {
    return "EMF 矢量图 — 浏览器不支持此格式，建议用 PNG/JPG 替代";
  }
  if (lower.includes("image/x-wmf") || lower.includes("image/wmf") || lower.includes(".wmf")) {
    return "WMF 矢量图 — 浏览器不支持此格式，建议用 PNG/JPG 替代";
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
      console.warn("[docx-preview:AssignmentDetail] 图片已替换为占位图:", issue);
    }
  });
}

/** 弹窗动画完成后渲染对比内容 */
async function renderCompareContent(): Promise<void> {
  if (!compareData.value || !dialogReady.value) return;
  const val = compareData.value;
  compareLoading.value = true;
  try {
    await nextTick();
    await new Promise(r => setTimeout(r, 100));
    console.log("[docx-preview:AssignmentDetail] 容器宽度: A=", compareTextARef.value?.offsetWidth, "B=", compareTextBRef.value?.offsetWidth);
    await Promise.all([
      renderSubmission(compareTextARef.value, val.fileA, val.contentHtmlA),
      renderSubmission(compareTextBRef.value, val.fileB, val.contentHtmlB),
    ]);
    applyDomHighlighting(compareTextARef.value, val.snippets);
    applyDomHighlighting(compareTextBRef.value, val.snippets);
  } finally {
    compareLoading.value = false;
  }
}

/** 弹窗动画完成后触发渲染 */
function onCompareDialogOpened(): void {
  dialogReady.value = true;
  renderCompareContent();
}

/** 弹窗关闭时重置状态 */
watch(compareVisible, (v) => {
  if (!v) {
    dialogReady.value = false;
  }
});

/** 数据加载完成后，如果弹窗已就绪则直接渲染 */
watch(compareData, async (val) => {
  if (val && dialogReady.value) {
    await nextTick();
    renderCompareContent();
  }
});

/** 打开对比预览 */
const openCompare = async (row: any) => {
  if (!row.matchSubmissionId) {
    ElMessage.warning("该记录没有可对比对象");
    return;
  }
  dialogReady.value = false;
  compareLoading.value = true;
  compareData.value = null;
  compareRowData.value = row;
  compareSuggestionText.value = "";
  compareVisible.value = true;
  try {
    compareData.value = await compareSubmissions(row.submissionId, row.matchSubmissionId);
    if (dialogReady.value) {
      await nextTick();
      renderCompareContent();
    }
  } catch (error: any) {
    ElMessage.error(error.message || "加载对比数据失败");
    compareVisible.value = false;
    compareLoading.value = false;
  }
};

/** 获取 AI 建议（结果表格） */
const openSuggestion = async (row: any) => {
  if (!row.submissionId) return;
  suggestionVisible.value = true;
  suggestionLoading.value = true;
  suggestionText.value = "";
  suggestionStudentName.value = row.studentName;
  try {
    const plagInfo: Record<string, any> = {
      rate: row.rate,
      phraseRate: row.phraseRate,
      topicRate: row.topicRate,
      status: row.status,
      matchName: row.matchName,
      matchId: row.matchId,
      suspectReason: row.suspectReason,
    };
    if (row.imageRate != null) {
      plagInfo.imageRate = row.imageRate;
      plagInfo.matchedImageCount = row.matchedImageCount ?? 0;
    }
    const res = await getAiSuggestion(row.submissionId, plagInfo);
    suggestionText.value = res.suggestion;
  } catch (error: any) {
    ElMessage.error(error.message || "AI 建议生成失败");
    suggestionVisible.value = false;
  } finally {
    suggestionLoading.value = false;
  }
};

/** 对比弹窗中获取 AI 建议 */
const openCompareSuggestion = async () => {
  if (!compareRowData.value) return;
  compareSuggestionLoading.value = true;
  compareSuggestionText.value = "";
  try {
    const plagInfo: Record<string, any> = {
      rate: compareRowData.value.rate,
      phraseRate: compareRowData.value.phraseRate,
      topicRate: compareRowData.value.topicRate,
      status: compareRowData.value.status,
      matchName: compareRowData.value.matchName,
      matchId: compareRowData.value.matchId,
      suspectReason: compareRowData.value.suspectReason,
    };
    if (compareRowData.value.imageRate != null) {
      plagInfo.imageRate = compareRowData.value.imageRate;
      plagInfo.matchedImageCount = compareRowData.value.matchedImageCount ?? 0;
    }
    const res = await getAiSuggestion(
      compareRowData.value.submissionId,
      plagInfo,
      compareRowData.value.matchSubmissionId,
    );
    compareSuggestionText.value = res.suggestion;
  } catch (error: any) {
    ElMessage.error(error.message || "AI 建议生成失败");
  } finally {
    compareSuggestionLoading.value = false;
  }
};

defineOptions({
  name: "AssignmentDetailTabs",
});
</script>

<style scoped>
.assignment-detail-tabs {
  background: white;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.detail-tabs {
  border: none;
  box-shadow: none;
}

.detail-tabs :deep(.el-tabs__header) {
  margin: 0;
  background: #f8fafc;
  border-bottom: 1px solid #e5e7eb;
}

.detail-tabs :deep(.el-tabs__nav-wrap) {
  padding: 0 0;
}

.detail-tabs :deep(.el-tabs__item) {
  border: none;
  background: transparent;
  color: #6b7280;
  font-weight: 500;
  font-size: 15px;
  padding: 16px 20px;
  margin-right: 8px;
  border-radius: 8px 8px 0 0;
  transition: all 0.3s ease;
}

.detail-tabs :deep(.el-tabs__item:hover) {
  background: rgba(59, 130, 246, 0.1);
  color: #3b82f6;
}

.detail-tabs :deep(.el-tabs__item.is-active) {
  background: white;
  color: #3b82f6;
  font-weight: 600;
  box-shadow: 0 -2px 8px rgba(0, 0, 0, 0.1);
}

.detail-tabs :deep(.el-tabs__active-bar) {
  display: none;
}

.detail-tabs :deep(.el-tabs__content) {
  padding: 0;
  min-height: 500px;
}

.tab-label {
  display: flex;
  align-items: center;
  gap: 8px;
}

.tab-badge {
  margin-left: 4px;
}

.tab-badge :deep(.el-badge__content) {
  background: #3b82f6;
  border: none;
  font-weight: 600;
  font-size: 11px;
  min-width: 18px;
  height: 18px;
  line-height: 18px;
  border-radius: 9px;
}

.tab-content {
  padding: 16px 20px;
}

.search-section {
  background: #f8fafc;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 16px;
  border: 1px solid #e5e7eb;
}

.table-section {
  margin-bottom: 16px;
}

.pagination-section {
  display: flex;
  justify-content: flex-end;
  padding: 12px 0;
  border-top: 1px solid #f3f4f6;
}

/* 查重样式 */
.plagiarism-action {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #f8fafc;
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 12px;
  border: 1px solid #e5e7eb;
}

.template-section {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 20px;
}

.template-tip {
  font-size: 12px;
  color: #9ca3af;
}

.action-left h3 {
  margin: 0 0 8px 0;
  font-size: 18px;
  color: #1f2937;
}

.action-desc {
  margin: 0;
  font-size: 13px;
  color: #6b7280;
  line-height: 1.8;
}

.highlight {
  color: #3b82f6;
  font-weight: 600;
}

.summary-cards {
  margin-bottom: 20px;
}

/* ====== 对比预览弹窗 ====== */
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
  overflow: auto;                  /* 改为 auto：允许水平和垂直滚动 */
  height: 70vh;
  display: flex;
  flex-direction: column;
  min-width: 0;                    /* flex 容器内防止内容撑破 */
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
  overflow: auto;                  /* 改为 auto：允许水平和垂直滚动 */
  padding: 16px 24px;
  font-size: 14px;
  line-height: 1.8;
  color: #374151;
  word-break: break-word;
}

/* 标黄 PDF 内嵌渲染 */
.compare-text :deep(.pdf-embed) {
  width: 100%;
}
.compare-text :deep(.pdf-embed canvas) {
  width: 100% !important;
  height: auto !important;
}

/* Word 文档渲染样式 */
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

/* docx-preview 容器样式 — 修复 Tailwind v4 preflight 对 .docx-wrapper 内部的样式覆盖 */
.compare-text :deep(.docx-wrapper) {
  background: transparent;
  padding: 0;
}

.compare-text :deep(.docx-wrapper > .docx) {
  box-shadow: none;
  margin: 0 auto;
  max-width: 100%;
}

/* 恢复 docx-wrapper 内部被 Tailwind preflight 覆盖的样式 */
.compare-text :deep(.docx-wrapper img) {
  max-width: 100%;
  height: auto;
  margin: 8px 0;
  display: inline;
  vertical-align: baseline;
}

.compare-text :deep(.docx-wrapper table) {
  border-collapse: collapse;
  width: 100%;
  margin: 8px 0;
}

.compare-text :deep(.docx-wrapper td),
.compare-text :deep(.docx-wrapper th) {
  border: 1px solid #d1d5db;
  padding: 6px 10px;
  font-size: 13px;
}

.compare-text :deep(.docx-wrapper th) {
  background: #f3f4f6;
  font-weight: 600;
}

.compare-text :deep(.docx-wrapper strong) {
  font-weight: 600;
}

.compare-text :deep(.docx-wrapper ul),
.compare-text :deep(.docx-wrapper ol) {
  margin: 6px 0;
  padding-left: 24px;
}

.compare-text :deep(.docx-wrapper li) {
  margin: 3px 0;
}

.compare-text :deep(.docx-wrapper pre) {
  background: #f8fafc;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  padding: 12px;
  overflow-x: auto;
  font-size: 13px;
  line-height: 1.6;
}

.summary-card {
  text-align: center;
  border-radius: 8px;
}

.summary-value {
  font-size: 28px;
  font-weight: 700;
  color: #1f2937;
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

/* 响应式设计 */
@media (max-width: 768px) {
  .detail-tabs :deep(.el-tabs__nav-wrap) {
    padding: 0 16px;
  }

  .detail-tabs :deep(.el-tabs__item) {
    padding: 12px 16px;
    font-size: 14px;
  }

  .tab-content {
    padding: 12px 16px;
  }

  .search-section {
    padding: 12px;
  }

  .plagiarism-action {
    flex-direction: column;
    gap: 12px;
    text-align: center;
  }
}

.action-buttons {
  display: flex;
  gap: 12px;
  align-items: center;
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

/* ====== AI 建议弹窗 ====== */
.suggestion-header {
  font-size: 15px;
  font-weight: 600;
  color: #1f2937;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid #e5e7eb;
}

.suggestion-content {
  font-size: 14px;
  line-height: 1.8;
  color: #374151;
  white-space: pre-wrap;
  word-break: break-word;
  background: #f9fafb;
  border-radius: 8px;
  padding: 16px;
  max-height: 400px;
  overflow-y: auto;
}

.compare-suggestion {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #e5e7eb;
}

.compare-suggestion .suggestion-content {
  margin-top: 12px;
}
</style>
