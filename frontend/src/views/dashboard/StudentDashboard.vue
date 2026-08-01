<template>
  <div class="student-page student-dashboard">
    <div class="student-page__inner dashboard-inner">
      <section class="student-hero dashboard-hero">
        <div class="dashboard-hero__copy">
          <p class="student-eyebrow">LEARNING CENTER</p>
          <h1 class="student-page-title">{{ greeting }}，{{ userName }}</h1>
          <p class="student-page-description">
            {{
              priorityMessage
            }}。先完成临近截止的任务，再查看最近评价和学习表现。
          </p>
        </div>
        <div class="dashboard-hero__actions">
          <el-button :icon="School" @click="goToClasses">我的班级</el-button>
          <el-button
            class="student-primary-button"
            type="primary"
            :icon="Refresh"
            :loading="isRefreshing"
            @click="refreshData"
          >
            刷新数据
          </el-button>
        </div>
      </section>

      <section class="stats-grid" aria-label="学习数据概览">
        <StatCard
          title="待完成"
          :value="studentStats?.pendingAssignments || 0"
          unit="个"
          subtitle="优先处理"
          icon="list"
          variant="danger"
          :loading="loading"
        />
        <StatCard
          title="已评价"
          :value="studentStats?.completedSubmissions || 0"
          unit="份"
          subtitle="累计"
          icon="document"
          variant="primary"
          :loading="loading"
        />
        <StatCard
          title="平均分"
          :value="studentStats?.averageScore || 0"
          unit="分"
          subtitle="AI 与教师评价"
          icon="trend"
          variant="success"
          :loading="loading"
        />
        <StatCard
          title="按时率"
          :value="studentStats?.onTimeRate || 0"
          unit="%"
          subtitle="按期提交表现"
          icon="user"
          variant="warning"
          :loading="loading"
          :progress="studentStats?.onTimeRate"
          show-progress
        />
        <StatCard
          title="加入班级"
          :value="studentStats?.joinedClasses || 0"
          unit="个"
          subtitle="当前班级"
          icon="school"
          variant="info"
          :loading="loading"
        />
      </section>

      <section class="dashboard-priority-grid">
        <article
          data-testid="priority-todos"
          class="priority-card priority-card--todos student-card"
        >
          <header class="priority-card__header">
            <div>
              <p class="student-eyebrow">UP NEXT</p>
              <h2 class="student-section-title">待完成作业</h2>
              <p class="student-section-description">
                按截止时间优先处理近期任务
              </p>
            </div>
            <el-button text type="primary" @click="viewAllAssignments">
              查看全部
              <el-icon><ArrowRight /></el-icon>
            </el-button>
          </header>

          <div v-if="pendingAssignments.length" class="todo-list">
            <button
              v-for="assignment in pendingAssignments"
              :key="assignment.assignmentId"
              type="button"
              class="todo-item"
              :class="{ 'todo-item--urgent': isUrgent(assignment.endDate) }"
              @click="
                goToAssignment(assignment.assignmentId, assignment.classId)
              "
            >
              <span class="todo-item__date">
                <strong>{{ formatDeadlineDay(assignment.endDate) }}</strong>
                <small>{{ formatDeadlineMonth(assignment.endDate) }}</small>
              </span>
              <span class="todo-item__main">
                <span class="todo-item__title-row">
                  <strong>{{ assignment.title }}</strong>
                  <span
                    v-if="isUrgent(assignment.endDate)"
                    class="urgent-badge"
                  >
                    即将截止
                  </span>
                </span>
                <span
                  >{{ assignment.className }} ·
                  {{ deadlineHint(assignment.endDate) }}</span
                >
              </span>
              <span class="todo-item__action">
                {{ assignment.status === "draft" ? "继续编辑" : "开始作业" }}
                <el-icon><ArrowRight /></el-icon>
              </span>
            </button>
          </div>
          <div v-else class="dashboard-empty">
            <el-empty description="当前没有待办作业" :image-size="78" />
          </div>
        </article>

        <article class="priority-card priority-card--recent student-card">
          <header class="priority-card__header">
            <div>
              <p class="student-eyebrow">RECENT</p>
              <h2 class="student-section-title">最近提交</h2>
              <p class="student-section-description">快速回顾成绩与批改状态</p>
            </div>
            <el-button text type="primary" @click="viewAllSubmissions">
              查看全部
            </el-button>
          </header>

          <div v-if="recentSubmissions.length" class="recent-list">
            <div
              v-for="submission in recentSubmissions"
              :key="
                submission.id ||
                `${submission.assignmentTitle}-${submission.submittedAt}`
              "
              class="recent-item"
            >
              <span class="recent-item__score">
                <strong>{{
                  submission.teacherScore ?? submission.aiScore ?? "--"
                }}</strong>
                <small>/100</small>
              </span>
              <span class="recent-item__main">
                <strong>{{ submission.assignmentTitle }}</strong>
                <small>{{ formatDateTime(submission.submittedAt) }}</small>
              </span>
              <span
                class="student-status"
                :class="`student-status--${getStatusType(submission.status)}`"
              >
                {{ getStatusText(submission.status) }}
              </span>
            </div>
          </div>
          <div v-else class="dashboard-empty">
            <el-empty description="暂无提交记录" :image-size="78" />
          </div>
        </article>
      </section>

      <section data-testid="dashboard-charts" class="dashboard-charts">
        <div class="dashboard-section-heading">
          <div>
            <p class="student-eyebrow">INSIGHTS</p>
            <h2 class="student-section-title">学习表现</h2>
            <p class="student-section-description">
              查看提交结构和成绩分布趋势
            </p>
          </div>
        </div>
        <div class="charts-grid">
          <article class="chart-card student-card">
            <h3>提交状态</h3>
            <DonutChart
              :data="submissionStatusData"
              :height="260"
              :loading="loading"
              :show-percentage="true"
            />
          </article>
          <article class="chart-card student-card">
            <h3>成绩分布</h3>
            <BarChart
              :data="performanceData"
              :height="260"
              :loading="loading"
              unit="次"
              :show-value="true"
            />
          </article>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { useStore } from "vuex";
import { ElMessage } from "element-plus";
import { ArrowRight, Refresh, School } from "@element-plus/icons-vue";
import { formatDateTime } from "@/utils/date";
import BarChart from "./components/charts/BarChart.vue";
import DonutChart from "./components/charts/DonutChart.vue";
import StatCard from "./components/StatCard.vue";

const store = useStore();
const router = useRouter();
const isRefreshing = ref(false);

const loading = computed(() => store.getters["dashboard/isLoading"]("student"));
const studentStats = computed(() => store.getters["dashboard/studentStats"]);
const userName = computed(
  () => store.getters["user/getUserInfo"]?.name || "同学"
);
const pendingAssignments = computed(() =>
  (studentStats.value?.pendingAssignmentsList || []).slice(0, 5)
);
const recentSubmissions = computed(() =>
  (studentStats.value?.recentSubmissions || []).slice(0, 5)
);

const greeting = computed(() => {
  const hour = new Date().getHours();
  if (hour < 6) return "夜深了";
  if (hour < 12) return "早上好";
  if (hour < 18) return "下午好";
  return "晚上好";
});

const priorityMessage = computed(() => {
  const count = studentStats.value?.pendingAssignments || 0;
  return count > 0 ? `当前还有 ${count} 项作业待完成` : "当前没有待完成作业";
});

const submissionStatusData = computed(() => {
  const statusMap: Record<string, { name: string; color: string }> = {
    draft: { name: "草稿", color: "#8E8E93" },
    submitted: { name: "已提交", color: "#6558D9" },
    ai_reviewed: { name: "AI 批改", color: "#D18B2D" },
    teacher_reviewed: { name: "教师批改", color: "#2D9A70" },
  };
  return (studentStats.value?.submissionStatusStats || []).map((item: any) => ({
    name: statusMap[item.status]?.name || item.status,
    value: item.count,
    color: statusMap[item.status]?.color,
  }));
});

const performanceData = computed(() => {
  const analysis = studentStats.value?.performanceAnalysis;
  if (!analysis) return [];
  return [
    { name: "优秀（90+）", value: analysis.excellentCount, color: "#2D9A70" },
    { name: "良好（80+）", value: analysis.goodCount, color: "#6558D9" },
    { name: "及格（60+）", value: analysis.passCount, color: "#D18B2D" },
  ];
});

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

const goToClasses = () => router.push("/student/classes");
const viewAllAssignments = () => router.push("/student/assignments");
const viewAllSubmissions = viewAllAssignments;
const goToAssignment = (assignmentId: string, classId: string) =>
  router.push(
    `/student/submissions?assignmentId=${assignmentId}&classId=${classId}`
  );

const hoursUntil = (endDate: string) =>
  (new Date(endDate).getTime() - Date.now()) / (1000 * 60 * 60);
const isUrgent = (endDate: string) => {
  const hours = hoursUntil(endDate);
  return hours > 0 && hours < 24;
};
const deadlineHint = (endDate: string) => {
  const hours = hoursUntil(endDate);
  if (hours <= 0) return "已截止";
  if (hours < 24) return `剩余 ${Math.max(1, Math.ceil(hours))} 小时`;
  return `${Math.ceil(hours / 24)} 天后截止`;
};
const formatDeadlineDay = (date: string) =>
  String(new Date(date).getDate()).padStart(2, "0");
const formatDeadlineMonth = (date: string) =>
  `${new Date(date).getMonth() + 1} 月`;

const getStatusType = (status: string) => {
  if (status === "teacher_reviewed") return "success";
  if (status === "ai_reviewed") return "primary";
  if (status === "submitted") return "warning";
  return "info";
};
const getStatusText = (status: string) => {
  const labels: Record<string, string> = {
    draft: "草稿",
    submitted: "待批改",
    ai_reviewed: "AI 已评",
    teacher_reviewed: "教师已评",
  };
  return labels[status] || status;
};

onMounted(async () => {
  try {
    await store.dispatch("dashboard/fetchStudentDashboard");
  } catch (error) {
    ElMessage.error("加载看板数据失败");
  }
});
</script>

<style scoped>
@import "../student/student-theme.css";

.student-dashboard {
  min-height: 100%;
}
.dashboard-hero {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
}
.dashboard-hero__copy,
.dashboard-hero__actions {
  position: relative;
  z-index: 1;
}
.dashboard-hero__actions {
  display: flex;
  gap: 10px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 13px;
  margin: 18px 0;
}

.dashboard-priority-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(320px, 0.65fr);
  gap: 16px;
  align-items: start;
}
.priority-card {
  overflow: hidden;
  padding: 22px;
}
.priority-card__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
  margin-bottom: 16px;
}
.priority-card__header .el-button :deep(.el-icon) {
  margin-left: 4px;
}

.todo-list,
.recent-list {
  display: grid;
  gap: 8px;
}
.todo-item {
  display: flex;
  width: 100%;
  align-items: center;
  gap: 13px;
  padding: 11px;
  border: 1px solid #eceef4;
  border-radius: 12px;
  background: #fff;
  cursor: pointer;
  text-align: left;
  transition: 0.2s ease;
}
.todo-item:hover {
  transform: translateY(-1px);
  border-color: #cec8f2;
  box-shadow: 0 8px 20px rgba(53, 47, 99, 0.07);
}
.todo-item--urgent {
  border-color: #f1c7ca;
  background: linear-gradient(90deg, #fff7f7, #fff);
}
.todo-item__date {
  display: flex;
  width: 48px;
  height: 48px;
  flex: 0 0 48px;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  border-radius: 10px;
  background: #f0eeff;
  color: #5c4fcc;
}
.todo-item--urgent .todo-item__date {
  background: #ffecee;
  color: #d44f5b;
}
.todo-item__date strong {
  font-size: 18px;
  line-height: 1;
}
.todo-item__date small {
  margin-top: 4px;
  font-size: 9px;
}
.todo-item__main {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
  gap: 6px;
}
.todo-item__title-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.todo-item__title-row strong {
  overflow: hidden;
  color: #30354a;
  font-size: 14px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.todo-item__main > span:last-child {
  color: #9298aa;
  font-size: 11px;
}
.urgent-badge {
  flex: 0 0 auto;
  padding: 3px 6px;
  border-radius: 999px;
  background: #ffe9eb;
  color: #cd4b57;
  font-size: 9px;
  font-weight: 700;
}
.todo-item__action {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 5px;
  color: #6154cf;
  font-size: 11px;
  font-weight: 700;
}

.recent-item {
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 11px 0;
  border-bottom: 1px solid #eff0f4;
}
.recent-item:last-child {
  border-bottom: 0;
}
.recent-item__score {
  display: flex;
  width: 54px;
  flex: 0 0 54px;
  align-items: baseline;
  color: #5d50cd;
}
.recent-item__score strong {
  font-size: 20px;
}
.recent-item__score small {
  margin-left: 2px;
  color: #a2a7b6;
  font-size: 9px;
}
.recent-item__main {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
  gap: 5px;
}
.recent-item__main strong {
  overflow: hidden;
  color: #373c51;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.recent-item__main small {
  color: #9ba0b0;
  font-size: 10px;
}
.student-status--info {
  background: #f0f1f5;
  color: #787f91;
}

.dashboard-empty {
  display: grid;
  min-height: 210px;
  place-items: center;
}

.dashboard-charts {
  margin-top: 22px;
}
.dashboard-section-heading {
  margin-bottom: 14px;
}
.charts-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}
.chart-card {
  min-width: 0;
  overflow: hidden;
  padding: 20px;
}
.chart-card h3 {
  margin: 0 0 12px;
  color: #34394f;
  font-size: 14px;
}

@media (max-width: 1100px) {
  .stats-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
  .dashboard-priority-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 760px) {
  .dashboard-hero {
    align-items: flex-start;
    flex-direction: column;
  }
  .dashboard-hero__actions {
    width: 100%;
  }
  .dashboard-hero__actions .el-button {
    flex: 1;
  }
  .stats-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .charts-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 520px) {
  .stats-grid {
    gap: 9px;
  }
  .priority-card {
    padding: 16px;
  }
  .todo-item__action {
    display: none;
  }
  .todo-item__title-row {
    align-items: flex-start;
    flex-direction: column;
    gap: 4px;
  }
  .priority-card__header {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
