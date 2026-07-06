<template>
  <div class="student-dashboard">
    <!-- 页面头部 -->
    <div class="dashboard-header">
      <div class="header-content">
        <h1 class="dashboard-title">🎓 {{ userName }}的学习中心</h1>
        <div class="header-actions">
          <el-button
            type="primary"
            :icon="Refresh"
            @click="refreshData"
            :loading="isRefreshing"
            size="default"
          >
            刷新数据
          </el-button>
          <el-button :icon="School" @click="goToClasses" size="default">
            我的班级
          </el-button>
        </div>
      </div>
    </div>

    <!-- 统计卡片 -->
    <div class="stats-grid">
      <StatCard
        title="已完成"
        :value="studentStats?.completedSubmissions || 0"
        unit="份"
        subtitle="已提交"
        icon="document"
        variant="primary"
        :loading="loading"
      />
      <StatCard
        title="平均分"
        :value="studentStats?.averageScore || 0"
        unit="分"
        subtitle="AI+教师"
        icon="trend"
        variant="success"
        :loading="loading"
      />
      <StatCard
        title="加入班级"
        :value="studentStats?.joinedClasses || 0"
        unit="个"
        subtitle="活跃班级"
        icon="school"
        variant="info"
        :loading="loading"
      />
      <StatCard
        title="按时率"
        :value="studentStats?.onTimeRate || 0"
        unit="%"
        subtitle="优秀表现"
        icon="user"
        variant="warning"
        :loading="loading"
        :progress="studentStats?.onTimeRate"
        :show-progress="true"
      />
      <StatCard
        title="待办"
        :value="studentStats?.pendingAssignments || 0"
        unit="个"
        subtitle="待完成"
        icon="list"
        variant="danger"
        :loading="loading"
      />
    </div>

    <!-- 图表区域 -->
    <div class="charts-grid">
      <!-- 提交状态统计 -->
      <div class="chart-card">
        <div class="chart-header">
          <h3 class="chart-title">📅 提交状态统计</h3>
        </div>
        <DonutChart
          :data="submissionStatusData"
          :height="280"
          :loading="loading"
          :show-percentage="true"
        />
      </div>

      <!-- 个人表现分析 -->
      <div class="chart-card">
        <div class="chart-header">
          <h3 class="chart-title">🎯 个人表现分析</h3>
        </div>
        <BarChart
          :data="performanceData"
          :height="280"
          :loading="loading"
          unit="次"
          :show-value="true"
        />
      </div>
    </div>

    <!-- 数据表格区域 -->
    <div class="tables-grid-two">
      <!-- 待完成作业 -->
      <div class="table-card">
        <div class="table-header">
          <h3 class="table-title">📝 待完成作业</h3>
          <div class="table-header-right">
            <el-tag
              v-if="studentStats?.pendingAssignments"
              type="warning"
              size="small"
            >
              {{ studentStats.pendingAssignments }} 个待办
            </el-tag>
            <el-button type="primary" size="small" @click="viewAllAssignments">
              查看更多
            </el-button>
          </div>
        </div>
        <el-table
          :data="(studentStats?.pendingAssignmentsList || []).slice(0, 5)"
          style="width: 100%"
          :loading="loading"
          empty-text="暂无待办作业"
          table-layout="fixed"
        >
          <el-table-column
            prop="title"
            label="作业名"
            min-width="120"
            show-overflow-tooltip
          >
            <template #default="{ row }">
              <div class="assignment-title">
                <span>{{ row.title }}</span>
                <el-tag
                  :type="row.status === 'draft' ? 'info' : 'warning'"
                  size="small"
                >
                  {{ row.status === "draft" ? "草稿" : "未开始" }}
                </el-tag>
              </div>
            </template>
          </el-table-column>
          <el-table-column
            prop="className"
            label="班级"
            width="70"
            align="center"
            show-overflow-tooltip
          />
          <el-table-column
            prop="endDate"
            label="截止时间"
            width="100"
            align="center"
            show-overflow-tooltip
          >
            <template #default="{ row }">
              <div
                class="deadline"
                :class="{ 'deadline--urgent': isUrgent(row.endDate) }"
              >
                <el-icon><Clock /></el-icon>
                {{ formatDateTime(row.endDate) }}
              </div>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="70" align="center" fixed="right">
            <template #default="{ row }">
              <el-button
                type="primary"
                size="small"
                @click="goToAssignment(row.assignmentId, row.classId)"
              >
                {{ row.status === "draft" ? "编辑" : "开始" }}
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <!-- 最近提交记录 -->
      <div class="table-card">
        <div class="table-header">
          <h3 class="table-title">📚 最近提交记录</h3>
          <el-button type="primary" size="small" @click="viewAllSubmissions">
            查看更多
          </el-button>
        </div>
        <el-table
          :data="(studentStats?.recentSubmissions || []).slice(0, 5)"
          style="width: 100%"
          :loading="loading"
          empty-text="暂无提交记录"
          table-layout="fixed"
        >
          <el-table-column
            prop="assignmentTitle"
            label="作业名"
            min-width="120"
            show-overflow-tooltip
          />
          <el-table-column label="得分" width="70" align="center">
            <template #default="{ row }">
              <div class="score-display">
                <span v-if="row.teacherScore" class="score score--teacher">
                  {{ row.teacherScore }}
                </span>
                <span v-else-if="row.aiScore" class="score score--ai">
                  {{ row.aiScore }}
                </span>
                <span v-else class="score score--pending">--</span>
                <span class="score-divider">/</span>
                <span class="score-total">100</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column
            prop="submittedAt"
            label="提交时间"
            width="90"
            align="center"
            show-overflow-tooltip
          >
            <template #default="{ row }">
              {{ formatDateTime(row.submittedAt) }}
            </template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="70" align="center">
            <template #default="{ row }">
              <el-tag :type="getStatusType(row.status)" size="small">
                {{ getStatusText(row.status) }}
              </el-tag>
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
import { Refresh, School, Clock } from "@element-plus/icons-vue";
import StatCard from "./components/StatCard.vue";
import DonutChart from "./components/charts/DonutChart.vue";
import BarChart from "./components/charts/BarChart.vue";
import { formatDateTime } from "@/utils/date";

const store = useStore();
const router = useRouter();

// 响应式数据
const isRefreshing = ref(false);

// 计算属性
const loading = computed(() => store.getters["dashboard/isLoading"]("student"));
const studentStats = computed(() => store.getters["dashboard/studentStats"]);
const userName = computed(() => store.getters["user/userName"] || "学生");

// 监听学生统计数据变化，用于调试
watch(
  studentStats,
  (newStats) => {
    if (newStats?.pendingAssignmentsList) {
      console.log(
        "Student pending assignments:",
        newStats.pendingAssignmentsList
      );
      newStats.pendingAssignmentsList.forEach((assignment, index) => {
        console.log(`Assignment ${index}:`, assignment);
      });
    }
  },
  { immediate: true }
);

// 提交状态数据转换
const submissionStatusData = computed(() => {
  if (!studentStats.value?.submissionStatusStats) return [];

  const statusMap: Record<string, { name: string; color: string }> = {
    draft: { name: "草稿", color: "#8E8E93" },
    submitted: { name: "已提交", color: "#007AFF" },
    ai_reviewed: { name: "AI批改", color: "#FF9F0A" },
    teacher_reviewed: { name: "教师批改", color: "#34C759" },
  };

  return studentStats.value.submissionStatusStats.map((item) => ({
    name: statusMap[item.status]?.name || item.status,
    value: item.count,
    color: statusMap[item.status]?.color,
  }));
});

// 个人表现数据转换
const performanceData = computed(() => {
  if (!studentStats.value?.performanceAnalysis) return [];

  const analysis = studentStats.value.performanceAnalysis;
  return [
    { name: "优秀(90+)", value: analysis.excellentCount, color: "#34C759" },
    { name: "良好(80+)", value: analysis.goodCount, color: "#007AFF" },
    { name: "及格(60+)", value: analysis.passCount, color: "#FF9F0A" },
  ];
});

// 方法
const refreshData = async () => {
  isRefreshing.value = true;
  try {
    await store.dispatch("dashboard/fetchStudentDashboard", true);
    ElMessage.success("数据刷新成功");
  } catch (error) {
    ElMessage.error("数据刷新失败");
  } finally {
    isRefreshing.value = false;
  }
};

const goToClasses = () => {
  router.push("/student/classes");
};

const viewAllAssignments = () => {
  router.push("/student/classes");
};

const viewAllSubmissions = () => {
  router.push("/student/classes");
};

const goToAssignment = (assignmentId: string, classId: string) => {
  console.log("goToAssignment called with:", { assignmentId, classId });
  console.log("Type of classId:", typeof classId);
  router.push(
    `/student/submissions?assignmentId=${assignmentId}&classId=${classId}`
  );
};

const isUrgent = (endDate: string) => {
  const deadline = new Date(endDate);
  const now = new Date();
  const hoursLeft = (deadline.getTime() - now.getTime()) / (1000 * 60 * 60);
  return hoursLeft > 0 && hoursLeft < 24;
};

const getStatusType = (status: string) => {
  const typeMap: Record<
    string,
    "success" | "warning" | "info" | "primary" | "danger"
  > = {
    draft: "info",
    submitted: "warning",
    ai_reviewed: "primary",
    teacher_reviewed: "success",
  };
  return typeMap[status] || "info";
};

const getStatusText = (status: string) => {
  const textMap: Record<string, string> = {
    draft: "草稿",
    submitted: "已提交",
    ai_reviewed: "AI批改",
    teacher_reviewed: "教师批改",
  };
  return textMap[status] || status;
};

// 生命周期
onMounted(async () => {
  try {
    await store.dispatch("dashboard/fetchStudentDashboard");
  } catch (error) {
    ElMessage.error("加载看板数据失败");
  }
});
</script>

<style scoped>
.student-dashboard {
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
  grid-template-columns: repeat(5, 1fr);
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
  margin-bottom: 16px;
}

.chart-title {
  font-size: 16px;
  font-weight: 600;
  color: #1d1d1f;
  margin: 0;
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

.assignment-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.deadline {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 14px;
  color: #666;
}

.deadline--urgent {
  color: #ff3b30;
  font-weight: 500;
}

.score-display {
  display: flex;
  align-items: center;
  gap: 2px;
}

.score {
  font-weight: 600;
}

.score--teacher {
  color: #34c759;
}

.score--ai {
  color: #007aff;
}

.score--pending {
  color: #8e8e93;
}

.score-divider,
.score-total {
  color: #8e8e93;
  font-size: 12px;
}

/* 响应式设计 */

/* 中等屏幕 - 平板横屏 */
@media (max-width: 1200px) {
  .stats-grid {
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
  }

  .charts-grid {
    grid-template-columns: 1fr;
    gap: 16px;
  }
}

/* 平板和小屏幕笔记本 */
@media (max-width: 1024px) {
  .tables-grid,
  .tables-grid-two {
    grid-template-columns: 1fr;
    gap: 16px;
  }

  .charts-grid {
    grid-template-columns: 1fr;
    gap: 16px;
  }
}

/* 手机和小平板 */
@media (max-width: 768px) {
  .student-dashboard {
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
  .student-dashboard {
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

  /* 作业标题在小屏幕上的优化 */
  .assignment-title {
    flex-direction: column;
    align-items: flex-start;
    gap: 4px;
  }

  /* 截止时间在小屏幕上的优化 */
  .deadline {
    flex-direction: column;
    font-size: 12px;
    gap: 2px;
  }
}
</style>
