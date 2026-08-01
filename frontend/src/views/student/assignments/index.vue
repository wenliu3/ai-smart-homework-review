<template>
  <div class="student-page assignments-page">
    <div class="student-page__inner">
      <section class="student-hero assignments-hero">
        <div class="assignments-hero__copy">
          <p class="student-eyebrow">MY ASSIGNMENTS</p>
          <h1 class="student-page-title">我的作业</h1>
          <p class="student-page-description">
            优先处理待提交和临近截止的任务，提交后可在同一入口查看评价结果。
          </p>
        </div>
        <el-button :loading="loading" plain @click="loadData">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </section>

      <section v-if="!loading" class="assignment-stats" aria-label="作业统计">
        <div
          v-for="item in statItems"
          :key="item.key"
          class="assignment-stat student-card"
        >
          <span class="assignment-stat__label">{{ item.label }}</span>
          <strong :class="`assignment-stat__value--${item.tone}`">
            {{ item.value }}
          </strong>
          <small>{{ item.hint }}</small>
        </div>
      </section>

      <section class="assignment-list-section student-card" v-loading="loading">
        <div class="assignment-list-toolbar">
          <div>
            <h2 class="student-section-title">作业清单</h2>
            <p class="student-section-description">
              共 {{ total }} 项，按状态快速筛选
            </p>
          </div>
          <div
            class="assignment-filters"
            role="group"
            aria-label="作业状态筛选"
          >
            <button
              v-for="filter in filters"
              :key="filter.value"
              :data-testid="`assignment-filter-${filter.value}`"
              type="button"
              :class="{ active: queryParams.businessStatus === filter.value }"
              @click="setFilter(filter.value)"
            >
              {{ filter.label }}
            </button>
          </div>
        </div>

        <div v-if="!loading && assignments.length === 0" class="student-empty">
          <el-empty description="当前筛选下暂无作业" />
        </div>

        <div v-else class="assignment-list-desktop">
          <el-table :data="assignments" class="assignment-table">
            <el-table-column label="作业" min-width="250">
              <template #default="scope">
                <div class="assignment-name-cell">
                  <span class="assignment-name-cell__accent"></span>
                  <div>
                    <strong>{{ scope.row.title }}</strong>
                    <small
                      >{{ scope.row.className }} ·
                      {{ scope.row.teacherName }}</small
                    >
                  </div>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="截止时间" min-width="170">
              <template #default="scope">
                <div
                  class="assignment-deadline"
                  :class="{ overdue: scope.row.isExpired }"
                >
                  <strong>{{ formatDate(scope.row.endDate) }}</strong>
                  <small>{{
                    scope.row.isExpired ? "已截止" : "请按时完成"
                  }}</small>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="提交状态" width="120">
              <template #default="scope">
                <span
                  class="student-status"
                  :class="`student-status--${getSubmissionStatusType(
                    scope.row
                  )}`"
                >
                  {{ getSubmissionStatusText(scope.row) }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="评价" width="120">
              <template #default="scope">
                <span
                  v-if="scope.row.hasSubmitted"
                  class="student-status"
                  :class="`student-status--${getReviewStatusType(
                    scope.row.submissionStatus
                  )}`"
                >
                  {{ getReviewStatusText(scope.row.submissionStatus) }}
                </span>
                <span v-else class="assignment-muted">—</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="126" align="right">
              <template #default="scope">
                <el-button
                  class="student-primary-button"
                  type="primary"
                  size="small"
                  @click="viewAssignment(scope.row)"
                >
                  {{ getActionText(scope.row) }}
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <div v-if="assignments.length" class="assignment-list-mobile">
          <article
            v-for="assignment in assignments"
            :key="assignment.id"
            class="assignment-mobile-card"
          >
            <div class="assignment-mobile-card__top">
              <span
                class="student-status"
                :class="`student-status--${getSubmissionStatusType(
                  assignment
                )}`"
              >
                {{ getSubmissionStatusText(assignment) }}
              </span>
              <small>{{ assignment.isExpired ? "已截止" : "进行中" }}</small>
            </div>
            <h3>{{ assignment.title }}</h3>
            <p>{{ assignment.className }} · {{ assignment.teacherName }}</p>
            <div class="assignment-mobile-card__deadline">
              截止：{{ formatDate(assignment.endDate) }}
            </div>
            <el-button
              class="student-primary-button"
              type="primary"
              @click="viewAssignment(assignment)"
            >
              {{ getActionText(assignment) }}
            </el-button>
          </article>
        </div>

        <div v-if="total > 0" class="assignment-pagination">
          <el-pagination
            :current-page="queryParams.page"
            :page-size="queryParams.pageSize"
            :page-sizes="[10, 20, 50]"
            :total="total"
            layout="total, sizes, prev, pager, next, jumper"
            @size-change="handleSizeChange"
            @current-change="handleCurrentChange"
          />
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { Refresh } from "@element-plus/icons-vue";
import {
  getMyAssignments,
  getMyAssignmentStatistics,
} from "../../../api/assignments";
import type { StudentAssignmentListItem } from "../../../types/assignments";

type BusinessStatus = "all" | "todo" | "completed" | "draft" | "expired";

const router = useRouter();
const loading = ref(false);
const assignments = ref<StudentAssignmentListItem[]>([]);
const total = ref(0);

const queryParams = reactive({
  page: 1,
  pageSize: 10,
  businessStatus: "all" as BusinessStatus,
});

const statistics = ref({
  totalAssignments: 0,
  submittedCount: 0,
  todoCount: 0,
  draftCount: 0,
  expiredCount: 0,
  reviewedCount: 0,
});

const filters: Array<{ label: string; value: BusinessStatus }> = [
  { label: "全部", value: "all" },
  { label: "待完成", value: "todo" },
  { label: "草稿", value: "draft" },
  { label: "已提交", value: "completed" },
  { label: "已过期", value: "expired" },
];

const statItems = computed(() => [
  {
    key: "total",
    label: "全部作业",
    value: statistics.value.totalAssignments,
    hint: "本学期任务",
    tone: "primary",
  },
  {
    key: "todo",
    label: "待完成",
    value: statistics.value.todoCount,
    hint: "优先处理",
    tone: "warning",
  },
  {
    key: "submitted",
    label: "已提交",
    value: statistics.value.submittedCount,
    hint: "含待评价",
    tone: "success",
  },
  {
    key: "reviewed",
    label: "已评价",
    value: statistics.value.reviewedCount,
    hint: "查看反馈",
    tone: "primary",
  },
]);

const loadAssignments = async () => {
  try {
    loading.value = true;
    const data = await getMyAssignments({
      ...queryParams,
      businessStatus:
        queryParams.businessStatus === "all"
          ? undefined
          : queryParams.businessStatus,
    });
    assignments.value = data.items;
    total.value = data.total;
  } catch (error) {
    console.error("加载作业列表失败:", error);
    ElMessage.error("加载作业列表失败");
  } finally {
    loading.value = false;
  }
};

const loadStatistics = async () => {
  try {
    statistics.value = await getMyAssignmentStatistics();
  } catch (error) {
    console.error("加载作业统计失败:", error);
  }
};

const loadData = async () => Promise.all([loadAssignments(), loadStatistics()]);

const formatDate = (dateStr: string) =>
  new Date(dateStr).toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });

const getSubmissionStatusType = (row: StudentAssignmentListItem) => {
  if (row.hasDraft && !row.hasSubmitted) return "warning";
  if (row.hasSubmitted) return "success";
  if (row.isExpired) return "danger";
  return "primary";
};

const getSubmissionStatusText = (row: StudentAssignmentListItem) => {
  if (row.hasDraft && !row.hasSubmitted) return "草稿";
  if (row.hasSubmitted) return "已提交";
  if (row.isExpired) return "未提交";
  return "待提交";
};

const getReviewStatusType = (status?: string) => {
  if (status === "teacher_reviewed") return "success";
  if (status === "ai_reviewed") return "primary";
  return "warning";
};

const getReviewStatusText = (status?: string) => {
  if (status === "teacher_reviewed") return "已批改";
  if (status === "ai_reviewed") return "AI 已评";
  return "待批改";
};

const getActionText = (row: StudentAssignmentListItem) => {
  if (row.hasSubmitted) return "查看详情";
  if (row.hasDraft) return "继续编辑";
  return "开始作业";
};

const viewAssignment = (assignment: StudentAssignmentListItem) => {
  const query = { assignmentId: assignment.id, classId: assignment.classId };
  if (assignment.hasSubmitted || assignment.hasDraft) {
    router.push({ path: "/student/submissions", query });
    return;
  }
  router.push({
    path: `/student/assignments/${assignment.id}`,
    query: { classId: assignment.classId },
  });
};

const setFilter = (status: BusinessStatus) => {
  if (queryParams.businessStatus === status) return;
  queryParams.businessStatus = status;
  queryParams.page = 1;
  loadAssignments();
};

const handleSizeChange = (size: number) => {
  queryParams.pageSize = size;
  queryParams.page = 1;
  loadAssignments();
};

const handleCurrentChange = (page: number) => {
  queryParams.page = page;
  loadAssignments();
};

onMounted(loadData);
</script>

<style scoped>
@import "../student-theme.css";

.assignments-page {
  min-height: 100%;
}

.assignments-hero {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
}

.assignments-hero__copy {
  position: relative;
  z-index: 1;
}
.assignments-hero > .el-button {
  position: relative;
  z-index: 1;
}

.assignment-stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
  margin: 18px 0;
}

.assignment-stat {
  display: grid;
  gap: 5px;
  padding: 18px 20px;
}

.assignment-stat__label {
  color: #747c91;
  font-size: 13px;
  font-weight: 600;
}
.assignment-stat strong {
  color: #2f344a;
  font-size: 28px;
  line-height: 1.1;
}
.assignment-stat small {
  color: #a0a5b5;
  font-size: 11px;
}
.assignment-stat__value--warning {
  color: #c77c25 !important;
}
.assignment-stat__value--success {
  color: #25936a !important;
}
.assignment-stat__value--primary {
  color: #5d50cc !important;
}

.assignment-list-section {
  overflow: hidden;
  padding: 0 22px 18px;
}

.assignment-list-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 22px;
  padding: 20px 0 16px;
  border-bottom: 1px solid #eceef4;
}

.assignment-filters {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  padding: 4px;
  border-radius: 10px;
  background: #f3f4f8;
}

.assignment-filters button {
  padding: 7px 12px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: #777e92;
  cursor: pointer;
  font-size: 12px;
  transition: 0.2s ease;
}

.assignment-filters button.active {
  background: #fff;
  color: #5d50cc;
  font-weight: 700;
  box-shadow: 0 3px 10px rgba(43, 47, 73, 0.08);
}

.assignment-table {
  --el-table-border-color: #eef0f5;
  --el-table-header-bg-color: #fafbfe;
}
.assignment-table :deep(th.el-table__cell) {
  color: #8a91a4;
  font-size: 12px;
  font-weight: 600;
}
.assignment-table :deep(td.el-table__cell) {
  padding: 15px 0;
}

.assignment-name-cell {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}
.assignment-name-cell__accent {
  width: 4px;
  height: 38px;
  flex: 0 0 4px;
  border-radius: 4px;
  background: linear-gradient(#7164de, #80a8ef);
}
.assignment-name-cell > div {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 5px;
}
.assignment-name-cell strong {
  overflow: hidden;
  color: #30354a;
  font-size: 14px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.assignment-name-cell small,
.assignment-deadline small {
  color: #9aa0b1;
  font-size: 11px;
}

.assignment-deadline {
  display: flex;
  flex-direction: column;
  gap: 5px;
}
.assignment-deadline strong {
  color: #535a70;
  font-size: 12px;
  font-weight: 600;
}
.assignment-deadline.overdue strong,
.assignment-deadline.overdue small {
  color: #d75864;
}
.assignment-muted {
  color: #b0b5c2;
}

.assignment-list-mobile {
  display: none;
}

.assignment-pagination {
  display: flex;
  justify-content: flex-end;
  padding-top: 18px;
}

@media (max-width: 900px) {
  .assignment-stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .assignment-list-toolbar {
    align-items: flex-start;
    flex-direction: column;
  }
}

@media (max-width: 720px) {
  .assignments-hero {
    align-items: flex-start;
    flex-direction: column;
  }
  .assignment-list-section {
    padding: 0 14px 14px;
  }
  .assignment-list-desktop {
    display: none;
  }
  .assignment-list-mobile {
    display: grid;
    gap: 12px;
    padding: 14px 0;
  }

  .assignment-mobile-card {
    display: grid;
    gap: 9px;
    padding: 16px;
    border: 1px solid #e8eaf2;
    border-radius: 13px;
    background: #fff;
  }

  .assignment-mobile-card__top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
  }
  .assignment-mobile-card__top small {
    color: #969caf;
  }
  .assignment-mobile-card h3 {
    margin: 2px 0 0;
    color: #2e3349;
    font-size: 16px;
  }
  .assignment-mobile-card p {
    margin: 0;
    color: #858ca0;
    font-size: 12px;
  }
  .assignment-mobile-card__deadline {
    padding: 9px 11px;
    border-radius: 9px;
    background: #f7f7fb;
    color: #666d82;
    font-size: 12px;
  }
  .assignment-mobile-card .el-button {
    width: 100%;
    margin-top: 2px;
  }
  .assignment-pagination {
    justify-content: center;
    overflow-x: auto;
  }
}

@media (max-width: 440px) {
  .assignment-stats {
    gap: 9px;
  }
  .assignment-stat {
    padding: 14px;
  }
  .assignment-stat strong {
    font-size: 24px;
  }
  .assignment-filters {
    width: 100%;
    overflow-x: auto;
    flex-wrap: nowrap;
  }
  .assignment-filters button {
    flex: 0 0 auto;
  }
}
</style>
