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
                <br />算法综合<span class="highlight">片段重合度</span>(整句照抄)和<span class="highlight">主题相似度</span>(改写/打乱)两种指标。
              </p>
            </div>
            <el-button
              type="primary"
              :icon="Search"
              :loading="plagiarismLoading"
              @click="runPlagiarismCheck"
            >
              {{ plagiarismLoading ? "查重中..." : "开始查重" }}
            </el-button>
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
              <el-col :span="6">
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
              <el-table-column label="最相似对象" min-width="160">
                <template #default="{ row }">
                  <span v-if="row.matchName !== '-'">
                    {{ row.matchName }} ({{ row.matchId }})
                  </span>
                  <span v-else class="text-gray">-</span>
                </template>
              </el-table-column>
              <el-table-column prop="status" label="判定结果" width="140" align="center" fixed="right">
                <template #default="{ row }">
                  <el-tag :type="row.status === '合格' ? 'success' : 'danger'" size="small">
                    {{ row.status }}
                  </el-tag>
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
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { User, CopyDocument, Search } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";
import { checkPlagiarism, type PlagiarismResult } from "@/api/assignments";

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

/** 执行查重 */
const runPlagiarismCheck = async () => {
  if (!props.assignmentId) {
    ElMessage.warning("无法获取作业ID");
    return;
  }
  plagiarismLoading.value = true;
  try {
    plagiarismResult.value = await checkPlagiarism(props.assignmentId);
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
  margin-bottom: 20px;
  border: 1px solid #e5e7eb;
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
</style>
