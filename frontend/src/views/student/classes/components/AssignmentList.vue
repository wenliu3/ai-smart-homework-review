<template>
  <section class="class-assignments">
    <div v-if="!selectedClass" class="class-assignments__empty">
      <el-empty description="请选择班级查看作业" :image-size="110">
        <template #description>
          <p>从班级列表选择一门课程，即可查看相关作业。</p>
        </template>
      </el-empty>
    </div>

    <template v-else>
      <header class="selected-class-header">
        <div class="selected-class-header__main">
          <p>SELECTED CLASS</p>
          <h2>{{ selectedClass.name }}</h2>
          <div class="selected-class-meta">
            <span>教师：{{ selectedClass.teacherName || "未知教师" }}</span>
            <span
              >{{ selectedClass.studentCount || 0 }} /
              {{ selectedClass.maxStudents || 60 }} 人</span
            >
            <span>班级码：{{ selectedClass.code || "-" }}</span>
          </div>
        </div>
        <el-button
          type="danger"
          plain
          :icon="Delete"
          @click="handleLeaveClassClick"
        >
          退出班级
        </el-button>
      </header>

      <div class="class-statistics" aria-label="班级作业统计">
        <div>
          <span>全部</span>
          <strong>{{ classStatistics.totalAssignments }}</strong>
        </div>
        <div>
          <span>待办</span>
          <strong class="warning">{{ classStatistics.todoCount }}</strong>
        </div>
        <div>
          <span>已提交</span>
          <strong class="success">{{ classStatistics.submittedCount }}</strong>
        </div>
        <div>
          <span>已批改</span>
          <strong class="primary">{{ classStatistics.reviewedCount }}</strong>
        </div>
      </div>

      <div class="assignment-toolbar">
        <div class="assignment-toolbar__filters">
          <button
            v-for="filter in filters"
            :key="filter.value"
            type="button"
            :class="{ active: assignmentFilter === filter.value }"
            @click="assignmentFilter = filter.value"
          >
            {{ filter.label }}
          </button>
        </div>
        <div class="assignment-toolbar__search">
          <el-input
            v-model="assignmentSearchKeyword"
            placeholder="搜索作业"
            clearable
            :prefix-icon="Search"
            @keyup.enter="handleAssignmentSearch"
            @clear="handleAssignmentClearSearch"
          />
          <el-button
            :loading="assignmentSearchLoading"
            @click="handleAssignmentSearch"
          >
            搜索
          </el-button>
        </div>
      </div>

      <div class="class-assignment-scroll">
        <div v-if="assignmentLoading" class="assignment-skeletons">
          <el-skeleton v-for="i in 3" :key="i" animated />
        </div>

        <div v-else-if="assignments.length" class="class-assignment-list">
          <article
            v-for="assignment in assignments"
            :key="assignment._id || assignment.id"
            class="class-assignment-card"
            :class="{ disabled: assignment.hasSubmittedInOtherClass }"
            @click="handleAssignmentClick(assignment)"
          >
            <div class="class-assignment-card__accent"></div>
            <div class="class-assignment-card__main">
              <div class="class-assignment-card__heading">
                <h3>{{ assignment.title }}</h3>
                <div class="class-assignment-card__statuses">
                  <span
                    class="student-status"
                    :class="`student-status--${getSubmissionTone(assignment)}`"
                  >
                    {{ getSubmissionText(assignment) }}
                  </span>
                  <span
                    v-if="
                      assignment.hasSubmitted && assignment.submissionStatus
                    "
                    class="student-status"
                    :class="`student-status--${getReviewStatusType(
                      assignment.submissionStatus
                    )}`"
                  >
                    {{ getReviewStatusText(assignment.submissionStatus) }}
                  </span>
                </div>
              </div>

              <div class="class-assignment-card__dates">
                <span
                  ><el-icon><Clock /></el-icon>开始
                  {{ formatDate(assignment.startDate, "datetime") }}</span
                >
                <span :class="{ overdue: isAssignmentExpired(assignment) }">
                  <el-icon><Clock /></el-icon>截止
                  {{ formatDate(assignment.endDate, "datetime") }}
                </span>
              </div>

              <div
                v-if="
                  assignment.hasSubmittedInOtherClass &&
                  assignment.otherClassSubmission
                "
                class="other-class-tip"
              >
                已在「{{
                  assignment.otherClassSubmission.className
                }}」班级提交，当前班级不可重复作答。
              </div>
            </div>
            <el-icon class="class-assignment-card__arrow"
              ><ArrowRight
            /></el-icon>
          </article>
        </div>

        <div v-else class="class-assignments__empty small">
          <el-empty description="该班级暂无作业" :image-size="90" />
        </div>
      </div>

      <footer v-if="assignments.length" class="class-assignment-pagination">
        <el-pagination
          :current-page="assignmentPageState.page"
          :page-size="assignmentPageState.limit"
          :page-sizes="[5, 10, 20, 50]"
          layout="total, sizes, prev, pager, next"
          :total="assignmentPageState.total"
          background
          small
          @size-change="handleAssignmentSizeChange"
          @current-change="handleAssignmentPageChange"
        />
      </footer>
    </template>
  </section>
</template>

<script setup lang="ts">
import { inject, reactive, ref, watch, type Ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { ArrowRight, Clock, Delete, Search } from "@element-plus/icons-vue";
import {
  getMyAssignments,
  getMyAssignmentStatistics,
} from "../../../../api/assignments";
import { useAssignmentManagement } from "../composables/useAssignmentManagement";
import { useClassManagement } from "../composables/useClassManagement";

const router = useRouter();
const { formatDate, handleLeaveClass } = useClassManagement();
const { isAssignmentExpired } = useAssignmentManagement();

const selectedClass = inject<Ref<any>>("selectedClass")!;
const setSelectedClass = inject<(classItem: any) => void>("setSelectedClass")!;
const refreshClassList = inject<() => void>("refreshClassList")!;

const assignmentLoading = ref(false);
const assignmentSearchLoading = ref(false);
const assignments = ref<any[]>([]);
const assignmentSearchKeyword = ref("");
const assignmentFilter = ref("all");
const assignmentPageState = reactive({ page: 1, limit: 10, total: 0 });
const classStatistics = ref({
  totalAssignments: 0,
  submittedCount: 0,
  todoCount: 0,
  draftCount: 0,
  expiredCount: 0,
  reviewedCount: 0,
});

const filters = [
  { label: "全部", value: "all" },
  { label: "待办", value: "todo" },
  { label: "草稿", value: "draft" },
  { label: "已提交", value: "completed" },
  { label: "已过期", value: "expired" },
];

const loadClassStatistics = async (classId: string) => {
  if (!classId) return;
  try {
    classStatistics.value = await getMyAssignmentStatistics(classId);
  } catch (error) {
    console.error("加载班级统计失败:", error);
  }
};

const loadAssignments = async (
  classId: string,
  search?: string,
  businessStatus?: string
) => {
  if (!classId) return;
  assignmentLoading.value = true;
  try {
    const response = await getMyAssignments({
      classId,
      page: assignmentPageState.page,
      pageSize: assignmentPageState.limit,
      sort: "startDate",
      order: "desc",
      ...(search ? { search } : {}),
      ...(businessStatus && businessStatus !== "all" ? { businessStatus } : {}),
    });
    assignments.value = response.items || [];
    assignmentPageState.total = response.total || 0;
    await loadClassStatistics(classId);
  } catch (error) {
    console.error("加载作业列表失败:", error);
    ElMessage.error("加载作业列表失败");
  } finally {
    assignmentLoading.value = false;
    assignmentSearchLoading.value = false;
  }
};

const reloadAssignments = () => {
  if (!selectedClass.value) return;
  loadAssignments(
    selectedClass.value._id,
    assignmentSearchKeyword.value.trim(),
    assignmentFilter.value
  );
};

const handleAssignmentSizeChange = (value: number) => {
  assignmentPageState.limit = value;
  assignmentPageState.page = 1;
  reloadAssignments();
};

const handleAssignmentPageChange = (value: number) => {
  assignmentPageState.page = value;
  reloadAssignments();
};

const handleAssignmentSearch = async () => {
  if (assignmentSearchLoading.value || !selectedClass.value) return;
  assignmentSearchLoading.value = true;
  assignmentPageState.page = 1;
  reloadAssignments();
};

const handleAssignmentClearSearch = () => {
  assignmentSearchKeyword.value = "";
  assignmentPageState.page = 1;
  reloadAssignments();
};

const getReviewStatusType = (status: string) =>
  status === "teacher_reviewed"
    ? "success"
    : status === "ai_reviewed"
    ? "primary"
    : "warning";

const getReviewStatusText = (status: string) =>
  status === "teacher_reviewed"
    ? "已批改"
    : status === "ai_reviewed"
    ? "AI 已评"
    : "待批改";

const getSubmissionTone = (assignment: any) => {
  if (assignment.hasSubmitted) return "success";
  if (assignment.hasSubmittedInOtherClass || isAssignmentExpired(assignment))
    return "danger";
  if (assignment.hasDraft) return "warning";
  return "primary";
};

const getSubmissionText = (assignment: any) => {
  if (assignment.hasSubmitted) return "已提交";
  if (assignment.hasSubmittedInOtherClass) return "其他班级已交";
  if (assignment.hasDraft) return "草稿";
  if (isAssignmentExpired(assignment)) return "未提交";
  return "待提交";
};

const handleAssignmentClick = (assignment: any) => {
  if (assignment.hasSubmittedInOtherClass) {
    const className = assignment.otherClassSubmission?.className || "其他班级";
    ElMessage.warning(`该作业已在「${className}」班级提交，无法重复作答`);
    return;
  }
  router.push({
    path: "/student/submissions",
    query: {
      assignmentId: assignment.id || assignment._id,
      classId: selectedClass.value._id,
    },
  });
};

watch(assignmentFilter, () => {
  assignmentPageState.page = 1;
  reloadAssignments();
});

watch(
  selectedClass,
  (value) => {
    if (!value) return;
    assignmentPageState.page = 1;
    assignmentSearchKeyword.value = "";
    loadAssignments(value._id, "", assignmentFilter.value);
  },
  { immediate: true }
);

const handleLeaveClassClick = () => {
  if (!selectedClass.value) return;
  handleLeaveClass(selectedClass.value._id, () => {
    setSelectedClass(null);
    refreshClassList();
  });
};
</script>

<style scoped>
.class-assignments {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
  background: #f8f9fc;
}

.class-assignments__empty {
  display: grid;
  flex: 1;
  min-height: 420px;
  place-items: center;
  color: #8f96a8;
}
.class-assignments__empty p {
  margin: 0;
  color: #8f96a8;
}
.class-assignments__empty.small {
  min-height: 260px;
}

.selected-class-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  padding: 22px 24px 18px;
  border-bottom: 1px solid #e9eaf1;
  background: linear-gradient(115deg, #fff, #f8f7ff 70%, #eef7ff);
}

.selected-class-header__main > p {
  margin: 0 0 4px;
  color: #6c5fd4;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.12em;
}
.selected-class-header h2 {
  margin: 0;
  color: #292e44;
  font-size: 22px;
}
.selected-class-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 18px;
  margin-top: 9px;
  color: #80879b;
  font-size: 12px;
}

.class-statistics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  padding: 16px 24px 0;
}

.class-statistics > div {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  border: 1px solid #eaecf2;
  border-radius: 11px;
  background: #fff;
}
.class-statistics span {
  color: #888fa2;
  font-size: 11px;
}
.class-statistics strong {
  color: #353a50;
  font-size: 19px;
}
.class-statistics strong.warning {
  color: #bd7929;
}
.class-statistics strong.success {
  color: #268e68;
}
.class-statistics strong.primary {
  color: #5d50ce;
}

.assignment-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 24px;
}

.assignment-toolbar__filters {
  display: flex;
  gap: 4px;
  padding: 4px;
  border-radius: 10px;
  background: #eceef4;
}
.assignment-toolbar__filters button {
  padding: 7px 11px;
  border: 0;
  border-radius: 7px;
  background: transparent;
  color: #7e8599;
  cursor: pointer;
  font-size: 11px;
}
.assignment-toolbar__filters button.active {
  background: #fff;
  color: #5c4fcb;
  font-weight: 700;
  box-shadow: 0 3px 10px rgba(47, 50, 75, 0.08);
}

.assignment-toolbar__search {
  display: flex;
  width: min(310px, 42%);
  gap: 8px;
}
.assignment-toolbar__search :deep(.el-input__wrapper) {
  border-radius: 9px;
}

.class-assignment-scroll {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 0 24px 20px;
}
.assignment-skeletons,
.class-assignment-list {
  display: grid;
  gap: 11px;
}

.class-assignment-card {
  position: relative;
  display: flex;
  align-items: center;
  overflow: hidden;
  border: 1px solid #e7e9f0;
  border-radius: 13px;
  background: #fff;
  cursor: pointer;
  transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
}

.class-assignment-card:hover {
  transform: translateY(-1px);
  border-color: #d1ccf3;
  box-shadow: 0 9px 24px rgba(55, 49, 99, 0.075);
}
.class-assignment-card.disabled {
  cursor: not-allowed;
  opacity: 0.65;
}
.class-assignment-card__accent {
  width: 5px;
  align-self: stretch;
  background: linear-gradient(#7164df, #7fa8ee);
}
.class-assignment-card__main {
  display: grid;
  min-width: 0;
  flex: 1;
  gap: 12px;
  padding: 17px 18px;
}
.class-assignment-card__heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
}
.class-assignment-card h3 {
  margin: 0;
  color: #30354a;
  font-size: 15px;
}
.class-assignment-card__statuses {
  display: flex;
  flex: 0 0 auto;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 6px;
}
.class-assignment-card__dates {
  display: flex;
  flex-wrap: wrap;
  gap: 9px 20px;
  color: #848b9f;
  font-size: 11px;
}
.class-assignment-card__dates span {
  display: flex;
  align-items: center;
  gap: 5px;
}
.class-assignment-card__dates .overdue {
  color: #d35460;
}
.class-assignment-card__arrow {
  margin-right: 18px;
  color: #aaaebe;
}
.other-class-tip {
  padding: 8px 10px;
  border-radius: 8px;
  background: #fff6e9;
  color: #b57327;
  font-size: 11px;
}

.student-status {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 4px 8px;
  border-radius: 999px;
  background: #f0f1f5;
  color: #73798c;
  font-size: 10px;
  font-weight: 700;
  white-space: nowrap;
}
.student-status::before {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: currentColor;
  content: "";
}
.student-status--success {
  background: #eaf8f2;
  color: #268f68;
}
.student-status--warning {
  background: #fff5e6;
  color: #bd7621;
}
.student-status--danger {
  background: #fff0f1;
  color: #d5505c;
}
.student-status--primary {
  background: #f0edff;
  color: #5f51cf;
}

.class-assignment-pagination {
  display: flex;
  flex: 0 0 auto;
  justify-content: center;
  padding: 13px 18px;
  border-top: 1px solid #e7e9f0;
  background: #fff;
}
.class-assignment-scroll::-webkit-scrollbar {
  width: 5px;
}
.class-assignment-scroll::-webkit-scrollbar-thumb {
  border-radius: 5px;
  background: #cfd2dc;
}

@media (max-width: 680px) {
  .selected-class-header,
  .assignment-toolbar {
    align-items: stretch;
    flex-direction: column;
  }
  .class-statistics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    padding: 14px 16px 0;
  }
  .assignment-toolbar {
    padding: 14px 16px;
  }
  .assignment-toolbar__filters {
    overflow-x: auto;
  }
  .assignment-toolbar__filters button {
    flex: 0 0 auto;
  }
  .assignment-toolbar__search {
    width: 100%;
  }
  .class-assignment-scroll {
    padding: 0 16px 16px;
  }
  .class-assignment-card__heading {
    flex-direction: column;
    gap: 9px;
  }
  .class-assignment-card__statuses {
    justify-content: flex-start;
  }
  .class-assignment-card__arrow {
    display: none;
  }
}
</style>
