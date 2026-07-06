<template>
  <div class="assignments-container">
    <!-- 页面头部 -->
    <page-header title="我的作业">
      <template #actions>
        <el-select
          v-model="queryParams.businessStatus"
          placeholder="状态筛选"
          style="width: 150px"
          @change="handleFilterChange"
        >
          <el-option label="全部" value="all" />
          <el-option label="待完成" value="todo" />
          <el-option label="已提交" value="completed" />
          <el-option label="草稿" value="draft" />
          <el-option label="已过期" value="expired" />
        </el-select>
        <el-button
          @click="loadData"
          :loading="loading"
          style="margin-left: 10px"
        >
          刷新
        </el-button>
      </template>
    </page-header>

    <!-- 自适应表格容器 -->
    <adaptive-table-container
      :loading="loading"
      loading-text="加载中..."
      :recalculate-trigger="recalculateTrigger"
      ref="adaptiveTableRef"
    >
      <!-- 搜索区域（统计信息） -->
      <template #search>
        <el-card class="stats-card" v-if="!loading">
          <div class="stats-info">
            <div class="stat-item">
              <span class="stat-label">总计</span>
              <span class="stat-value">{{ statistics.totalAssignments }}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">已提交</span>
              <span class="stat-value">{{ statistics.submittedCount }}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">待办</span>
              <span class="stat-value">{{ statistics.todoCount }}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">草稿</span>
              <span class="stat-value">{{ statistics.draftCount }}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">过期</span>
              <span class="stat-value text-danger">{{
                statistics.expiredCount
              }}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">已批改</span>
              <span class="stat-value">{{ statistics.reviewedCount }}</span>
            </div>
          </div>
        </el-card>
      </template>

      <!-- 表格区域 -->
      <template #table="{ tableHeight }">
        <div class="empty-tip" v-if="!loading && assignments.length === 0">
          <el-empty description="暂无作业信息" />
        </div>
        <div v-else>
          <el-table
            :data="assignments"
            :style="{ width: '100%', height: tableHeight }"
            :max-height="tableHeight"
          >
            <el-table-column prop="title" label="作业标题" min-width="200" />
            <el-table-column prop="className" label="班级" width="120" />
            <el-table-column prop="teacherName" label="教师" width="100" />
            <el-table-column prop="endDate" label="截止日期" width="180">
              <template #default="scope">
                {{ formatDate(scope.row.endDate) }}
              </template>
            </el-table-column>
            <el-table-column label="提交状态" width="120">
              <template #default="scope">
                <el-tag :type="getSubmissionStatusType(scope.row)">
                  {{ getSubmissionStatusText(scope.row) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="批改状态" width="120">
              <template #default="scope">
                <el-tag
                  v-if="scope.row.hasSubmitted"
                  :type="getReviewStatusType(scope.row.submissionStatus)"
                >
                  {{ getReviewStatusText(scope.row.submissionStatus) }}
                </el-tag>
                <span v-else class="text-gray-400">-</span>
              </template>
            </el-table-column>
            <el-table-column label="作业状态" width="100">
              <template #default="scope">
                <el-tag
                  :type="scope.row.isExpired ? 'danger' : 'success'"
                  size="small"
                >
                  {{ scope.row.isExpired ? "已过期" : "进行中" }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="120" fixed="right">
              <template #default="scope">
                <el-button
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
      </template>

      <!-- 分页区域 -->
      <template #pagination>
        <el-pagination
          v-if="total > 0"
          :current-page="queryParams.page"
          :page-size="queryParams.pageSize"
          :page-sizes="[10, 20, 50]"
          :total="total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        />
      </template>
    </adaptive-table-container>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, reactive } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import {
  getMyAssignments,
  getMyAssignmentStatistics,
} from "../../../api/assignments";
import type { StudentAssignmentListItem } from "../../../types/assignments";
import AdaptiveTableContainer from "@/components/AdaptiveTableContainer.vue";
import PageHeader from "@/components/PageHeader.vue";

const router = useRouter();

// 响应式数据
const loading = ref(false);
const assignments = ref<StudentAssignmentListItem[]>([]);
const total = ref(0);

// 组件引用
const adaptiveTableRef = ref(null);

// 触发重新计算容器高度的计数器
const recalculateTrigger = ref(0);

// 查询参数
const queryParams = reactive({
  page: 1,
  pageSize: 10,
  businessStatus: "all" as "all" | "todo" | "completed" | "draft" | "expired",
});

// 统计数据
const statistics = ref({
  totalAssignments: 0,
  submittedCount: 0,
  todoCount: 0,
  draftCount: 0,
  expiredCount: 0,
  reviewedCount: 0,
});

// 加载作业列表
const loadAssignments = async () => {
  try {
    loading.value = true;
    const params = {
      ...queryParams,
      businessStatus:
        queryParams.businessStatus === "all"
          ? undefined
          : queryParams.businessStatus,
    };
    const data = await getMyAssignments(params);
    assignments.value = data.items;
    total.value = data.total;

    // 触发容器高度重新计算
    recalculateTrigger.value++;
  } catch (error) {
    console.error("加载作业列表失败:", error);
    ElMessage.error("加载作业列表失败");
  } finally {
    loading.value = false;
  }
};

// 加载统计数据
const loadStatistics = async () => {
  try {
    const data = await getMyAssignmentStatistics();
    statistics.value = data;
  } catch (error) {
    console.error("加载统计数据失败:", error);
  }
};

// 加载所有数据
const loadData = async () => {
  await Promise.all([loadAssignments(), loadStatistics()]);
};

// 格式化日期
const formatDate = (dateStr: string) => {
  const date = new Date(dateStr);
  return date.toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
};

// 获取提交状态类型
const getSubmissionStatusType = (row: StudentAssignmentListItem) => {
  if (row.hasDraft && !row.hasSubmitted) return "warning";
  if (row.hasSubmitted) return "success";
  if (row.isExpired) return "danger";
  return "info";
};

// 获取提交状态文本
const getSubmissionStatusText = (row: StudentAssignmentListItem) => {
  if (row.hasDraft && !row.hasSubmitted) return "草稿";
  if (row.hasSubmitted) return "已提交";
  if (row.isExpired) return "未提交";
  return "待提交";
};

// 获取批改状态类型
const getReviewStatusType = (status?: string) => {
  switch (status) {
    case "teacher_reviewed":
      return "success";
    case "ai_reviewed":
      return "warning";
    case "submitted":
      return "info";
    default:
      return "info";
  }
};

// 获取批改状态文本
const getReviewStatusText = (status?: string) => {
  switch (status) {
    case "teacher_reviewed":
      return "已批改";
    case "ai_reviewed":
      return "AI已评";
    case "submitted":
      return "待批改";
    default:
      return "待批改";
  }
};

// 获取操作按钮文本
const getActionText = (row: StudentAssignmentListItem) => {
  if (row.hasSubmitted) return "查看详情";
  if (row.hasDraft) return "继续编辑";
  return "开始作业";
};

// 查看作业详情
const viewAssignment = (assignment: StudentAssignmentListItem) => {
  const classId = assignment.classId || assignment.classes?.[0]?.id || '';
  if (assignment.hasSubmitted || assignment.hasDraft) {
    // 跳转到提交页面
    router.push({
      path: "/student/submissions",
      query: {
        assignmentId: assignment.id,
        classId,
      },
    });
  } else {
    // 跳转到作业详情页面
    router.push({
      path: `/student/assignments/${assignment.id}`,
      query: {
        classId,
      },
    });
  }
};

// 筛选变化
const handleFilterChange = () => {
  queryParams.page = 1;
  loadAssignments();
};

// 分页大小变化
const handleSizeChange = (size: number) => {
  queryParams.pageSize = size;
  queryParams.page = 1;
  loadAssignments();
};

// 当前页变化
const handleCurrentChange = (page: number) => {
  queryParams.page = page;
  loadAssignments();
};

onMounted(() => {
  loadData();
});
</script>

<style scoped>
.assignments-container {
  background: #f5f7fa;
}

/* 统计卡片样式 */
.stats-card {
  margin-bottom: 16px;
  border-radius: 8px;
  border: 1px solid #e4e7ed;
}

.stats-info {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 16px;
}

.stat-item {
  text-align: center;
  padding: 16px;
  background: #f8f9fa;
  border-radius: 6px;
}

.stat-label {
  display: block;
  font-size: 12px;
  color: #909399;
  margin-bottom: 4px;
}

.stat-value {
  display: block;
  font-size: 20px;
  font-weight: 600;
  color: #303133;
}

.text-danger {
  color: #f56c6c !important;
}

.empty-tip {
  text-align: center;
  padding: 40px 0;
}

.pagination-container {
  display: flex;
  justify-content: center;
  margin-top: 20px;
}

.text-gray-400 {
  color: #9ca3af;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .card-header {
    flex-direction: column;
    gap: 12px;
    align-items: stretch;
  }

  .stats-info {
    gap: 8px;
  }

  .stat-item {
    font-size: 11px;
    padding: 3px 6px;
  }

  .header-controls {
    justify-content: flex-end;
  }
}
</style>
