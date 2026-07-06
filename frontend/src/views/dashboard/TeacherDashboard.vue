<template>
  <div class="teacher-dashboard">
    <!-- 页面头部 -->
    <div class="dashboard-header">
      <div class="header-content">
        <h1 class="dashboard-title">👨‍🏫 {{ userName }}的教学中心</h1>
        <div class="header-actions">
          <el-button
            type="success"
            :icon="Plus"
            @click="createAssignment"
            size="default"
          >
            新建作业
          </el-button>
          <el-button :icon="Setting" @click="manageAiRules" size="default">
            AI规则
          </el-button>
          <el-button
            :icon="Refresh"
            @click="refreshData"
            :loading="isRefreshing"
            size="default"
          >
            刷新
          </el-button>
        </div>
      </div>
    </div>

    <!-- 统计卡片 -->
    <div class="stats-grid">
      <StatCard
        title="我的班级"
        :value="teacherStats?.myClasses || 0"
        unit="个"
        subtitle="活跃/解散"
        icon="school"
        variant="primary"
        :loading="loading"
      />
      <StatCard
        title="我的作业"
        :value="teacherStats?.myAssignments || 0"
        unit="个"
        subtitle="发布/草稿"
        icon="document"
        variant="success"
        :loading="loading"
      />
      <StatCard
        title="待批改"
        :value="teacherStats?.pendingReviews || 0"
        unit="份"
        subtitle="AI已批改"
        icon="list"
        variant="warning"
        :loading="loading"
        :trend="pendingTrend"
        :trend-value="pendingTrendValue"
      />
      <StatCard
        title="班级学生"
        :value="teacherStats?.totalStudents || 0"
        unit="人"
        subtitle="活跃学生"
        icon="user"
        variant="info"
        :loading="loading"
      />
    </div>

    <!-- 图表区域 -->
    <div class="charts-grid">
      <!-- 班级提交统计 -->
      <div class="chart-card">
        <div class="chart-header">
          <h3 class="chart-title">📊 班级提交统计</h3>
          <div class="chart-actions">
            <div class="chart-subtitle">
              平均完成率: {{ averageSubmissionRate }}%
            </div>
            <el-button
              type="primary"
              size="small"
              @click="viewClassSubmissionDetails"
            >
              展示更多
            </el-button>
          </div>
        </div>
        <!-- 改用排名列表展示，更直观 -->
        <div class="class-submission-list" v-loading="loading">
          <div
            v-for="(item, index) in displayedClassSubmissionData"
            :key="item.name"
            class="submission-item"
            :class="{ 'top-performer': index < 3 }"
          >
            <div class="submission-rank">
              <span class="rank-number" :class="getRankClass(index)">{{
                index + 1
              }}</span>
            </div>
            <div class="submission-info">
              <div class="class-name">{{ item.name }}</div>
              <div class="submission-stats">
                <span class="students-count">{{ item.totalStudents }}人</span>
                <span class="submitted-count"
                  >已提交{{ item.submittedCount }}份</span
                >
              </div>
            </div>
            <div class="submission-rate">
              <div
                class="rate-circle-progress"
                :style="{ '--progress': item.value }"
              >
                <span class="rate-text" :class="getRateClass(item.value)"
                  >{{ item.value }}%</span
                >
              </div>
            </div>
          </div>
          <div
            v-if="!loading && displayedClassSubmissionData.length === 0"
            class="empty-state"
          >
            <p>暂无班级数据</p>
          </div>
        </div>
      </div>

      <!-- 作业状态分布 -->
      <div class="chart-card">
        <div class="chart-header">
          <h3 class="chart-title">📈 作业状态分布</h3>
        </div>
        <DonutChart
          :data="assignmentStatusData"
          :height="280"
          :loading="loading"
        />
      </div>
    </div>

    <!-- AI批改统计和学生成绩分析 -->
    <div class="charts-grid">
      <!-- AI批改统计 -->
      <div class="chart-card">
        <div class="chart-header">
          <h3 class="chart-title">🤖 AI批改统计</h3>
          <div class="ai-status">
            <el-tag type="success" size="small">🟢DeepSeek</el-tag>
            <el-tag type="warning" size="small">🟡豆包</el-tag>
          </div>
        </div>
        <div class="ai-stats-grid">
          <div class="ai-stat-item">
            <div class="stat-label">今日AI批改</div>
            <div class="stat-value">
              {{ teacherStats?.aiReviewStats?.todayReviews || 0 }}份
            </div>
          </div>
          <div class="ai-stat-item">
            <div class="stat-label">已累计批改</div>
            <div class="stat-value">
              {{
                formatNumber(teacherStats?.aiReviewStats?.totalReviews || 0)
              }}份
            </div>
          </div>
          <div class="ai-stat-item">
            <div class="stat-label">批改失败</div>
            <div class="stat-value error">
              {{ teacherStats?.aiReviewStats?.failedReviews || 0 }}份
            </div>
          </div>
          <div class="ai-stat-item">
            <div class="stat-label">等待批改</div>
            <div class="stat-value pending">
              {{ teacherStats?.aiReviewStats?.pendingReviews || 0 }}份
            </div>
          </div>
        </div>
      </div>

      <!-- 学生成绩分析 -->
      <div class="chart-card">
        <div class="chart-header">
          <h3 class="chart-title">📊 学生成绩分析</h3>
        </div>
        <div class="score-analysis">
          <div class="score-comparison">
            <div class="score-item">
              <div class="score-label">平均AI分</div>
              <div class="score-value ai">
                {{
                  teacherStats?.studentScoreAnalysis?.avgAiScore?.toFixed(1) ||
                  "--"
                }}分
              </div>
            </div>
            <div class="score-item">
              <div class="score-label">平均教师分</div>
              <div class="score-value teacher">
                {{
                  teacherStats?.studentScoreAnalysis?.avgTeacherScore?.toFixed(
                    1
                  ) || "--"
                }}分
              </div>
            </div>
            <div class="score-item">
              <div class="score-label">分数差异</div>
              <div class="score-value" :class="scoreDifferenceClass">
                {{ scoreDifferenceText }}
              </div>
            </div>
          </div>
          <div class="performance-rates">
            <div class="rate-item">
              <div class="rate-circle excellent">
                <span
                  >{{
                    teacherStats?.studentScoreAnalysis?.excellentRate?.toFixed(
                      1
                    ) || 0
                  }}%</span
                >
              </div>
              <div class="rate-label">🎯 优秀率</div>
            </div>
            <div class="rate-item">
              <div class="rate-circle pass">
                <span
                  >{{
                    teacherStats?.studentScoreAnalysis?.passRate?.toFixed(1) ||
                    0
                  }}%</span
                >
              </div>
              <div class="rate-label">📈 及格率</div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 数据表格区域 -->
    <div class="tables-grid-two">
      <!-- 我的作业管理 -->
      <div class="table-card">
        <div class="table-header">
          <h3 class="table-title">📝 我的作业管理</h3>
          <el-button type="primary" size="small" @click="viewAllAssignments">
            查看全部
          </el-button>
        </div>
        <el-table
          :data="(pendingTasks?.assignments || []).slice(0, 5)"
          style="width: 100%"
          :loading="loading"
          empty-text="暂无需要关注的作业"
          table-layout="fixed"
        >
          <el-table-column
            prop="title"
            label="作业名"
            min-width="100"
            show-overflow-tooltip
          />
          <el-table-column
            prop="classCount"
            label="班级"
            width="60"
            align="center"
          >
            <template #default="{ row }"> {{ row.classCount }}班 </template>
          </el-table-column>
          <el-table-column
            prop="submissionRate"
            label="提交率"
            width="100"
            align="center"
          >
            <template #default="{ row }">
              <div
                class="submission-rate"
                :class="{ 'low-rate': row.submissionRate < 50 }"
              >
                {{ row.submissionRate }}%
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="70" align="center">
            <template #default="{ row }">
              <el-tag :type="getAssignmentStatusType(row.status)" size="small">
                {{ getAssignmentStatusText(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column
            prop="endDate"
            label="截止时间"
            width="90"
            align="center"
            show-overflow-tooltip
          >
            <template #default="{ row }">
              <div
                class="deadline"
                :class="{ 'deadline--urgent': isUrgent(row.endDate) }"
              >
                {{ formatDateTime(row.endDate) }}
              </div>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="60" align="center" fixed="right">
            <template #default="{ row }">
              <el-button
                type="primary"
                size="small"
                @click="viewAssignment(row.id)"
              >
                查看
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <!-- 待处理提交 -->
      <div class="table-card">
        <div class="table-header">
          <h3 class="table-title">✅ 待处理提交</h3>
          <div class="table-header-right">
            <el-tag
              v-if="teacherStats?.pendingReviews"
              type="warning"
              size="small"
            >
              {{ teacherStats.pendingReviews }} 份待批改
            </el-tag>
            <el-button type="primary" size="small" @click="viewAllSubmissions">
              查看更多
            </el-button>
          </div>
        </div>
        <el-table
          :data="(pendingTasks?.submissions || []).slice(0, 5)"
          style="width: 100%"
          :loading="loading"
          empty-text="暂无待处理提交"
          table-layout="fixed"
        >
          <el-table-column
            prop="studentName"
            label="学生"
            width="70"
            align="center"
            show-overflow-tooltip
          />
          <el-table-column
            prop="assignmentTitle"
            label="作业"
            min-width="100"
            show-overflow-tooltip
          />
          <el-table-column
            prop="aiScore"
            label="AI分"
            width="60"
            align="center"
          >
            <template #default="{ row }">
              <span v-if="row.aiScore" class="ai-score"
                >{{ row.aiScore }}分</span
              >
              <span v-else class="no-score">--</span>
            </template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="70" align="center">
            <template #default="{ row }">
              <el-tag :type="getSubmissionStatusType(row.status)" size="small">
                {{ getSubmissionStatusText(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column
            prop="submittedAt"
            label="提交时间"
            width="80"
            align="center"
            show-overflow-tooltip
          >
            <template #default="{ row }">
              {{ formatRelativeTime(row.submittedAt) }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="60" align="center" fixed="right">
            <template #default="{ row }">
              <el-button
                type="primary"
                size="small"
                @click="reviewSubmission(row.assignmentId)"
              >
                批改
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { useStore } from "vuex";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { Refresh, Plus, Setting } from "@element-plus/icons-vue";
import StatCard from "./components/StatCard.vue";
import DonutChart from "./components/charts/DonutChart.vue";
import BarChart from "./components/charts/BarChart.vue";
import { formatDateTime, formatRelativeTime, isUrgent } from "@/utils/date";
import { getTeacherPendingTasks } from "@/api/dashboard";

const store = useStore();
const router = useRouter();

// 响应式数据
const isRefreshing = ref(false);
const pendingTasks = ref<any>(null);

// 计算属性
const loading = computed(() => store.getters["dashboard/isLoading"]("teacher"));
const teacherStats = computed(() => store.getters["dashboard/teacherStats"]);
const userName = computed(() => store.getters["user/userName"] || "教师");

// 班级提交统计数据转换
const classSubmissionData = computed(() => {
  if (!teacherStats.value?.classSubmissionStats) return [];

  return teacherStats.value.classSubmissionStats
    .map((item) => ({
      name: item.className,
      value: Math.round(item.submissionRate * 10) / 10,
      totalStudents: item.totalStudents || 0,
      submittedCount: item.submittedCount || 0,
      color:
        item.submissionRate >= 90
          ? "#34C759"
          : item.submissionRate >= 70
          ? "#007AFF"
          : item.submissionRate >= 50
          ? "#FF9F0A"
          : "#FF3B30",
    }))
    .sort((a, b) => b.value - a.value); // 按提交率降序排列
});

// 显示的班级提交数据（默认只显示前3个）
const displayedClassSubmissionData = computed(() => {
  return classSubmissionData.value.slice(0, 3);
});

// 作业状态分布数据转换
const assignmentStatusData = computed(() => {
  if (!teacherStats.value?.assignmentStatusDistribution) return [];

  const statusMap: Record<string, { name: string; color: string }> = {
    draft: { name: "草稿", color: "#8E8E93" },
    published: { name: "发布中", color: "#007AFF" },
    terminated: { name: "已终止", color: "#FF3B30" },
  };

  return teacherStats.value.assignmentStatusDistribution.map((item) => ({
    name: statusMap[item.status]?.name || item.status,
    value: item.count,
    color: statusMap[item.status]?.color,
  }));
});

// 平均提交率
const averageSubmissionRate = computed(() => {
  if (!teacherStats.value?.classSubmissionStats?.length) return 0;

  const total = teacherStats.value.classSubmissionStats.reduce(
    (sum, item) => sum + item.submissionRate,
    0
  );
  return (
    Math.round((total / teacherStats.value.classSubmissionStats.length) * 10) /
    10
  );
});

// 待批改趋势
const pendingTrend = computed(() => {
  // 这里可以根据历史数据计算趋势，简化处理
  const pending = teacherStats.value?.pendingReviews || 0;
  return pending > 20 ? "up" : pending < 5 ? "down" : "stable";
});

const pendingTrendValue = computed(() => {
  // 模拟趋势值
  return Math.floor(Math.random() * 20) + 5;
});

// 分数差异相关
const scoreDifferenceText = computed(() => {
  const diff = teacherStats.value?.studentScoreAnalysis?.scoreDifference || 0;
  const prefix = diff > 0 ? "+" : "";
  return `${prefix}${diff.toFixed(1)}分`;
});

const scoreDifferenceClass = computed(() => {
  const diff = teacherStats.value?.studentScoreAnalysis?.scoreDifference || 0;
  return diff > 0 ? "positive" : diff < 0 ? "negative" : "neutral";
});

// 方法
const refreshData = async () => {
  isRefreshing.value = true;
  try {
    await Promise.all([
      store.dispatch("dashboard/fetchTeacherDashboard", true),
      loadPendingTasks(),
    ]);
    ElMessage.success("数据刷新成功");
  } catch (error) {
    ElMessage.error("数据刷新失败");
  } finally {
    isRefreshing.value = false;
  }
};

const loadPendingTasks = async () => {
  try {
    pendingTasks.value = await getTeacherPendingTasks();
  } catch (error) {
    console.error("加载待处理任务失败:", error);
  }
};

const createAssignment = () => {
  router.push("/teacher/assignmentsEdit");
};

const manageAiRules = () => {
  router.push("/teacher/ai-rules");
};

const viewAllAssignments = () => {
  router.push("/teacher/assignments");
};

const viewAllSubmissions = () => {
  router.push("/teacher/assignments");
};

const viewAssignment = (assignmentId: string) => {
  router.push(`/teacher/assignments/detail?id=${assignmentId}`);
};

const reviewSubmission = (assignmentId: string) => {
  console.log("批改作业 - assignmentId:", assignmentId);

  if (assignmentId) {
    // 跳转到作业详情页面，自动打开第一个待批改的作业
    router.push(
      `/teacher/assignments/detail?id=${assignmentId}&openFirstPending=true`
    );
  } else {
    console.log("assignmentId 为空，跳转到作业管理页面");
    router.push(`/teacher/assignments`);
  }
};

const viewClassSubmissionDetails = () => {
  router.push("/teacher/classes?tab=submission-stats");
};

const getRankClass = (index: number) => {
  if (index === 0) return "rank-first";
  if (index === 1) return "rank-second";
  if (index === 2) return "rank-third";
  return "rank-normal";
};

const getRateClass = (rate: number) => {
  if (rate >= 90) return "rate-excellent";
  if (rate >= 70) return "rate-good";
  if (rate >= 50) return "rate-normal";
  return "rate-poor";
};

const formatNumber = (num: number) => {
  if (num >= 10000) {
    return (num / 10000).toFixed(1) + "万";
  } else if (num >= 1000) {
    return (num / 1000).toFixed(1) + "k";
  }
  return num.toString();
};

const getAssignmentStatusType = (status: string) => {
  const typeMap: Record<
    string,
    "success" | "warning" | "info" | "primary" | "danger"
  > = {
    draft: "info",
    published: "success",
    terminated: "danger",
  };
  return typeMap[status] || "info";
};

const getAssignmentStatusText = (status: string) => {
  const textMap: Record<string, string> = {
    draft: "草稿",
    published: "发布中",
    terminated: "已终止",
  };
  return textMap[status] || status;
};

const getSubmissionStatusType = (status: string) => {
  const typeMap: Record<
    string,
    "success" | "warning" | "info" | "primary" | "danger"
  > = {
    submitted: "warning",
    ai_reviewed: "primary",
    teacher_reviewed: "success",
  };
  return typeMap[status] || "info";
};

const getSubmissionStatusText = (status: string) => {
  const textMap: Record<string, string> = {
    submitted: "已提交",
    ai_reviewed: "AI批改",
    teacher_reviewed: "教师批改",
  };
  return textMap[status] || status;
};

// 生命周期
onMounted(async () => {
  try {
    await Promise.all([
      store.dispatch("dashboard/fetchTeacherDashboard"),
      loadPendingTasks(),
    ]);
  } catch (error) {
    ElMessage.error("加载看板数据失败");
  }
});
</script>

<style scoped>
.teacher-dashboard {
  padding: 24px;
  background: #f8f9fa;
  overflow-x: hidden; /* 防止页面级别的水平滚动 */
}

.dashboard-header {
  margin-bottom: 24px;
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 16px;
}

.dashboard-title {
  font-size: 24px;
  font-weight: 600;
  color: #1d1d1f;
  margin: 0;
}

.header-actions {
  display: flex;
  gap: 12px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}

.charts-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}

.chart-card {
  background: #ffffff;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  border: 1px solid #f0f0f0;
  overflow: hidden; /* 防止内容溢出 */
  min-width: 0; /* 允许flex子元素收缩 */
}

.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.chart-title {
  font-size: 16px;
  font-weight: 600;
  color: #1d1d1f;
  margin: 0;
}

.chart-actions {
  display: flex;
  align-items: center;
  gap: 16px;
}

.chart-subtitle {
  font-size: 14px;
  color: #666;
  font-weight: 500;
}

/* 班级提交统计样式 */
.class-submission-list {
  min-height: 280px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.submission-item {
  display: flex;
  align-items: center;
  padding: 16px;
  background: #f8f9fa;
  border-radius: 10px;
  transition: all 0.3s ease;
  border: 2px solid transparent;
}

.submission-item:hover {
  background: #f0f1f3;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

.submission-item.top-performer {
  background: linear-gradient(135deg, #f8f9fa 0%, #e3f2fd 100%);
  border-color: #e3f2fd;
}

.submission-rank {
  margin-right: 16px;
}

.rank-number {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  font-weight: 600;
  font-size: 14px;
}

.rank-first {
  background: linear-gradient(135deg, #ffd700, #ffa500);
  color: white;
  box-shadow: 0 2px 8px rgba(255, 215, 0, 0.3);
}

.rank-second {
  background: linear-gradient(135deg, #c0c0c0, #a8a8a8);
  color: white;
  box-shadow: 0 2px 8px rgba(192, 192, 192, 0.3);
}

.rank-third {
  background: linear-gradient(135deg, #cd7f32, #b87333);
  color: white;
  box-shadow: 0 2px 8px rgba(205, 127, 50, 0.3);
}

.rank-normal {
  background: #e9ecef;
  color: #666;
}

.submission-info {
  flex: 1;
  min-width: 0;
}

.class-name {
  font-size: 16px;
  font-weight: 600;
  color: #1d1d1f;
  margin-bottom: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.submission-stats {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: #666;
}

.students-count,
.submitted-count {
  background: #fff;
  padding: 2px 6px;
  border-radius: 4px;
  border: 1px solid #e9ecef;
}

.submission-rate {
  margin-left: 16px;
}

.rate-circle-progress {
  position: relative;
  width: 50px;
  height: 50px;
  border-radius: 50%;
  background: conic-gradient(
    from 0deg,
    transparent 0deg,
    transparent calc(360deg * (100 - var(--progress)) / 100),
    #e9ecef calc(360deg * (100 - var(--progress)) / 100),
    #e9ecef 360deg
  );
  display: flex;
  align-items: center;
  justify-content: center;
}

.rate-circle-progress::before {
  content: "";
  position: absolute;
  inset: 4px;
  border-radius: 50%;
  background: #f8f9fa;
}

.rate-text {
  position: relative;
  z-index: 1;
  font-size: 11px;
  font-weight: 600;
}

.rate-excellent {
  color: #34c759;
}

.rate-good {
  color: #007aff;
}

.rate-normal {
  color: #ff9f0a;
}

.rate-poor {
  color: #ff3b30;
}

/* 优秀率的特殊样式 */
.submission-item.top-performer .rate-circle-progress {
  background: conic-gradient(
    from 0deg,
    #34c759 0deg,
    #34c759 calc(360deg * var(--progress) / 100),
    #e9ecef calc(360deg * var(--progress) / 100),
    #e9ecef 360deg
  );
}

.submission-item:nth-child(2) .rate-circle-progress {
  background: conic-gradient(
    from 0deg,
    #007aff 0deg,
    #007aff calc(360deg * var(--progress) / 100),
    #e9ecef calc(360deg * var(--progress) / 100),
    #e9ecef 360deg
  );
}

.submission-item:nth-child(3) .rate-circle-progress {
  background: conic-gradient(
    from 0deg,
    #ff9f0a 0deg,
    #ff9f0a calc(360deg * var(--progress) / 100),
    #e9ecef calc(360deg * var(--progress) / 100),
    #e9ecef 360deg
  );
}

.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: #999;
  font-size: 14px;
}

.ai-status {
  display: flex;
  gap: 8px;
}

.ai-stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.ai-stat-item {
  text-align: center;
  padding: 16px;
  background: #f8f9fa;
  border-radius: 8px;
}

.stat-label {
  font-size: 12px;
  color: #666;
  margin-bottom: 8px;
}

.stat-value {
  font-size: 18px;
  font-weight: 600;
  color: #1d1d1f;
}

.stat-value.error {
  color: #ff3b30;
}

.stat-value.pending {
  color: #ff9f0a;
}

.score-analysis {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.score-comparison {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.score-item {
  text-align: center;
  padding: 16px;
  background: #f8f9fa;
  border-radius: 8px;
}

.score-label {
  font-size: 12px;
  color: #666;
  margin-bottom: 8px;
}

.score-value {
  font-size: 18px;
  font-weight: 600;
}

.score-value.ai {
  color: #007aff;
}

.score-value.teacher {
  color: #34c759;
}

.score-value.positive {
  color: #34c759;
}

.score-value.negative {
  color: #ff3b30;
}

.score-value.neutral {
  color: #8e8e93;
}

.performance-rates {
  display: flex;
  justify-content: space-around;
  gap: 20px;
}

.rate-item {
  text-align: center;
}

.rate-circle {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  font-weight: 600;
  color: white;
  margin-bottom: 8px;
}

.rate-circle.excellent {
  background: linear-gradient(135deg, #34c759, #30d158);
}

.rate-circle.pass {
  background: linear-gradient(135deg, #007aff, #5ac8fa);
}

.rate-label {
  font-size: 12px;
  color: #666;
}

.tables-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 16px;
}

.tables-grid-two {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.table-card {
  background: #ffffff;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  border: 1px solid #f0f0f0;
  overflow: hidden; /* 防止内容溢出 */
  min-width: 0; /* 允许flex子元素收缩 */
}

.table-card :deep(.el-table) {
  overflow: hidden;
}

.table-card :deep(.el-table__body-wrapper) {
  overflow-x: auto;
}

.table-card :deep(.el-table__header-wrapper) {
  overflow-x: hidden;
}

.table-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.table-header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.table-title {
  font-size: 16px;
  font-weight: 600;
  color: #1d1d1f;
  margin: 0;
}

.submission-rate {
  font-weight: 500;
  color: #34c759;
}

.submission-rate.low-rate {
  color: #ff3b30;
}

.deadline {
  font-size: 14px;
  color: #666;
}

.deadline--urgent {
  color: #ff3b30;
  font-weight: 500;
}

.ai-score {
  color: #007aff;
  font-weight: 500;
}

.no-score {
  color: #8e8e93;
}

/* 响应式设计 */

/* 中等屏幕 - 平板横屏 */
@media (max-width: 1200px) {
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
    gap: 16px;
  }

  .ai-stats-grid {
    grid-template-columns: repeat(2, 1fr);
    gap: 16px;
  }

  .charts-grid {
    grid-template-columns: 1fr;
    gap: 16px;
  }
}

/* 平板和小屏幕笔记本 */
@media (max-width: 1024px) {
  .tables-grid-two {
    grid-template-columns: 1fr;
    gap: 16px;
  }

  .charts-grid {
    grid-template-columns: 1fr;
    gap: 16px;
  }

  .score-comparison {
    grid-template-columns: 1fr;
  }
}

/* 手机和小平板 */
@media (max-width: 768px) {
  .teacher-dashboard {
    padding: 16px;
  }

  .dashboard-title {
    font-size: 20px;
  }

  .header-content {
    flex-direction: column;
    align-items: flex-start;
  }

  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
    gap: 12px;
  }

  .charts-grid {
    grid-template-columns: 1fr;
    gap: 12px;
  }

  .chart-card,
  .table-card {
    padding: 16px;
  }

  .ai-stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  /* 表格在中等屏幕上的优化 */
  .table-card :deep(.el-table__cell) {
    padding: 10px 6px;
  }

  .table-card :deep(.el-table) {
    font-size: 13px;
  }
}

/* 小屏手机 */
@media (max-width: 480px) {
  .teacher-dashboard {
    padding: 12px;
  }

  .dashboard-title {
    font-size: 18px;
  }

  .header-actions {
    flex-direction: column;
    width: 100%;
    gap: 8px;
  }

  .header-actions .el-button {
    width: 100%;
  }

  .stats-grid {
    grid-template-columns: 1fr;
    gap: 8px;
  }

  .chart-card,
  .table-card {
    padding: 12px;
  }

  .ai-stats-grid {
    grid-template-columns: 1fr;
  }

  /* 表格在小屏幕上的优化 */
  .table-card :deep(.el-table__cell) {
    padding: 8px 4px;
  }

  .table-card :deep(.el-table) {
    font-size: 12px;
  }

  .table-card :deep(.el-button) {
    padding: 4px 8px;
    font-size: 11px;
  }
}
</style>
