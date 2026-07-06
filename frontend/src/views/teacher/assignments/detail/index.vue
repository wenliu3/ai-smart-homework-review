<template>
  <div class="assignment-detail-page">
    <!-- 作业头部信息 -->
    <assignment-header
      :assignment-detail="assignmentDetail"
      @go-back="goBack"
      @publish="handlePublish"
      @terminate="handleTerminate"
      @edit="handleEdit"
      @export="handleExport"
    />

    <!-- 统计卡片 -->
    <assignment-stats-cards :assignment-detail="assignmentDetail" />

    <!-- 详情Tab -->
    <assignment-detail-tabs
      :assignment-id="assignmentId"
      :submission-stats="assignmentDetail?.submissionStats"
    >
      <!-- 搜索表单 -->
      <template #search>
        <student-search-form
          :classes="assignmentDetail?.classes"
          :submission-stats="assignmentDetail?.submissionStats"
          :total-students="assignmentDetail?.totalStudents"
          :total="pagination.total"
          :loading="loading"
          @search="handleSearch"
          @reset="handleReset"
          ref="searchFormRef"
        />
      </template>

      <!-- 表格 -->
      <template #table>
        <assignment-detail-table
          :submission-data="submissionList"
          :assignment-id="assignmentId"
          :auto-open-first-pending="openFirstPending"
          @refresh="handleRefresh"
          @auto-opened="clearAutoOpenParam"
        />
      </template>

      <!-- 分页 -->
      <template #pagination>
        <el-pagination
          :current-page="pagination.page"
          :page-size="pagination.limit"
          :page-sizes="[10, 20, 50, 100]"
          :background="true"
          layout="total, sizes, prev, pager, next, jumper"
          :total="pagination.total"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        />
      </template>
    </assignment-detail-tabs>
  </div>
</template>

<script lang="ts" setup>
import { ref, reactive, computed, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";

// 导入组件
import AssignmentHeader from "./components/AssignmentHeader.vue";
import AssignmentStatsCards from "./components/AssignmentStatsCards.vue";
import AssignmentDetailTabs from "./components/AssignmentDetailTabs.vue";
import StudentSearchForm from "./components/StudentSearchForm.vue";
import AssignmentDetailTable from "./components/AssignmentDetailTable.vue";

// 导入API和类型
import {
  getAssignmentDetail,
  getAssignmentStudents,
  publishAssignment,
  terminateAssignment,
  AssignmentStatus,
} from "@/api/assignments";
import type {
  AssignmentSubmissionsQueryParams,
  AssignmentDetail,
} from "@/api/assignments";

// 路由
const route = useRoute();
const router = useRouter();

// 作业ID和其他查询参数
const assignmentId = computed(() => route.query.id as string);
// 作业是否自动打开第一个待批改作业
const openFirstPending = computed(
  () => route.query.openFirstPending === "true"
);

// 响应式数据
const loading = ref(true);
const assignmentDetail = ref<AssignmentDetail | null>(null);
const submissionList = ref<any[]>([]);

// 分页数据
const pagination = reactive({
  page: 1,
  limit: 20,
  total: 0,
});

// 组件引用
const searchFormRef = ref<InstanceType<typeof StudentSearchForm> | null>(null);

// 返回上一页
const goBack = () => {
  router.back();
};

// 加载作业详情
const loadAssignmentDetail = async () => {
  try {
    assignmentDetail.value = await getAssignmentDetail(assignmentId.value);
  } catch (error) {
    console.error("加载作业详情失败", error);
    ElMessage.error("加载作业详情失败");
  }
};

// 加载学生提交数据（包含所有学生）
const loadSubmissionData = async (searchParams?: any) => {
  loading.value = true;
  try {
    // 构建查询参数
    const params: AssignmentSubmissionsQueryParams = {
      page: pagination.page,
      limit: pagination.limit,
      ...searchParams,
    };

    const response = await getAssignmentStudents(assignmentId.value, params);

    if (response && response.items) {
      submissionList.value = response.items || [];
      pagination.total = response.total || 0;
    } else {
      submissionList.value = [];
      pagination.total = 0;
    }
  } catch (error) {
    console.error("加载学生提交数据失败", error);
    ElMessage.error("加载学生提交列表失败");
  } finally {
    loading.value = false;
  }
};

// 处理搜索
const handleSearch = (searchParams: any) => {
  pagination.page = 1;
  loadSubmissionData(searchParams);
};

// 重置搜索
const handleReset = () => {
  pagination.page = 1;
  loadSubmissionData();
};

// 处理分页变化
const handleSizeChange = (val: number) => {
  pagination.limit = val;
  // 获取当前搜索条件
  const searchParams = searchFormRef.value?.searchForm || {};
  loadSubmissionData(searchParams);
};

const handleCurrentChange = (val: number) => {
  pagination.page = val;
  // 获取当前搜索条件
  const searchParams = searchFormRef.value?.searchForm || {};
  loadSubmissionData(searchParams);
};

// 处理刷新数据（批改完成后）
const handleRefresh = () => {
  // 重新加载作业详情（更新统计数据）
  loadAssignmentDetail();
  // 获取当前搜索条件
  const searchParams = searchFormRef.value?.searchForm || {};
  loadSubmissionData(searchParams);
};

// 清除自动打开参数（避免后续操作重复触发）
const clearAutoOpenParam = () => {
  if (route.query.openFirstPending) {
    router.replace({
      path: route.path,
      query: {
        ...route.query,
        openFirstPending: undefined,
      },
    });
  }
};

// 作业操作处理
const handlePublish = async () => {
  try {
    await ElMessageBox.confirm("确认发布此作业吗？", "确认操作", {
      confirmButtonText: "确认发布",
      cancelButtonText: "取消",
      type: "warning",
    });

    await publishAssignment(assignmentId.value);
    ElMessage.success("作业发布成功");
    await loadAssignmentDetail();
  } catch (error: any) {
    if (error !== "cancel") {
      console.error("发布作业失败", error);
      ElMessage.error("发布作业失败");
    }
  }
};

const handleTerminate = async () => {
  try {
    const { value: reason } = await ElMessageBox.prompt(
      "请输入终止原因",
      "终止作业",
      {
        confirmButtonText: "确认终止",
        cancelButtonText: "取消",
        inputPattern: /.+/,
        inputErrorMessage: "请输入终止原因",
      }
    );

    await terminateAssignment(assignmentId.value, reason);
    ElMessage.success("作业已终止");
    await loadAssignmentDetail();
  } catch (error: any) {
    if (error !== "cancel") {
      console.error("终止作业失败", error);
      ElMessage.error("终止作业失败");
    }
  }
};

const handleEdit = () => {
  router.push(`/teacher/assignments/edit?id=${assignmentId.value}`);
};

const handleExport = () => {
  ElMessage.info("导出功能开发中...");
};

// 组件挂载时加载数据
onMounted(async () => {
  if (assignmentId.value) {
    await loadAssignmentDetail();
    await loadSubmissionData();
  }
});

// 组件名称
defineOptions({
  name: "AssignmentDetail",
});
</script>

<style scoped>
.assignment-detail-page {
  background: #f8fafc;
  min-height: 100%;
  width: 100%;
  width: 100%;
  overflow-x: hidden;
  box-sizing: border-box;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .assignment-detail-page {
    padding: 0 8px;
  }
}
</style>
