<template>
  <div class="assignments-management">
    <!-- 页面头部 -->
    <page-header
      title="作业管理"
      description="管理和发布作业，跟踪学生提交情况"
    >
      <template #actions>
        <el-button
          type="primary"
          :icon="Plus"
          @click="handleCreate"
          size="default"
        >
          创建作业
        </el-button>
        <el-button
          :icon="Refresh"
          @click="refreshData"
          :loading="loading"
          size="default"
        >
          刷新
        </el-button>
      </template>
    </page-header>

    <!-- 内容容器 -->
    <div class="assignments-container" ref="containerRef">
      <!-- 搜索和筛选区域 -->
      <div class="search-section" ref="searchRef">
        <el-form :inline="true" :model="searchForm" class="search-form">
          <div class="search-row">
            <el-form-item label="作业标题">
              <el-input
                v-model="searchForm.search"
                placeholder="请输入作业标题"
                clearable
                style="width: 180px"
                @keyup.enter="handleSearch"
              />
            </el-form-item>
            <el-form-item label="状态">
              <el-select
                v-model="searchForm.status"
                placeholder="请选择状态"
                clearable
                style="width: 110px"
              >
                <el-option label="草稿" :value="AssignmentStatus.DRAFT" />
                <el-option label="已发布" :value="AssignmentStatus.PUBLISHED" />
                <el-option
                  label="已终止"
                  :value="AssignmentStatus.TERMINATED"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="班级">
              <el-input
                v-model="searchForm.className"
                placeholder="请输入班级名称"
                clearable
                style="width: 140px"
                @keyup.enter="handleSearch"
              />
            </el-form-item>
            <el-form-item label="是否过期">
              <el-select
                v-model="searchForm.isExpired"
                placeholder="请选择"
                clearable
                style="width: 100px"
              >
                <el-option label="未过期" :value="false" />
                <el-option label="已过期" :value="true" />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="handleSearch" :icon="Search">
                搜索
              </el-button>
              <el-button @click="handleReset" :icon="Refresh"> 重置 </el-button>
            </el-form-item>

            <!-- 视图切换 -->
            <el-form-item class="view-controls">
              <el-radio-group
                v-model="viewMode"
                @change="handleViewModeChange"
                size="small"
              >
                <el-radio-button label="网格" value="grid">
                  <el-icon><Grid /></el-icon>
                </el-radio-button>
                <el-radio-button label="列表" value="list">
                  <el-icon><List /></el-icon>
                </el-radio-button>
              </el-radio-group>
            </el-form-item>
          </div>
        </el-form>
      </div>

      <!-- 作业列表内容区域 -->
      <div
        class="content-section"
        ref="contentRef"
        :style="{ height: contentHeight }"
        v-loading="loading"
        element-loading-text="加载中..."
      >
        <!-- 空状态 -->
        <div v-if="assignmentList.length === 0" class="empty-state">
          <div class="empty-icon">📝</div>
          <h3 class="empty-title">暂无作业</h3>
          <p class="empty-desc">点击"创建作业"按钮开始创建您的第一个作业</p>
          <el-button
            type="primary"
            :icon="Plus"
            @click="handleCreate"
            class="empty-action"
          >
            创建作业
          </el-button>
        </div>

        <!-- 网格视图 -->
        <div v-else-if="viewMode === 'grid'" class="assignments-grid">
          <assignment-card
            v-for="assignment in assignmentList"
            :key="assignment.id"
            :assignment="assignment"
            @view="handleView"
            @edit="handleEdit"
            @delete="handleDelete"
            @publish="handlePublish"
            @terminate="handleTerminate"
            @republish="handleRepublish"
          />
        </div>

        <!-- 列表视图 -->
        <div v-else class="assignments-list">
          <el-table
            :data="assignmentList"
            stripe
            style="width: 100%"
            @sort-change="handleSortChange"
            height="100%"
          >
            <el-table-column
              prop="title"
              label="作业标题"
              min-width="200"
              show-overflow-tooltip
            >
              <template #default="{ row }">
                <div class="assignment-title-cell">
                  <el-button link @click="handleView(row)">
                    {{ row.title }}
                  </el-button>
                  <el-tag
                    v-if="row.isExpired"
                    type="danger"
                    size="small"
                    class="ml-2"
                  >
                    已过期
                  </el-tag>
                </div>
              </template>
            </el-table-column>

            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="getStatusType(row.status)" size="small">
                  {{ getStatusText(row.status) }}
                </el-tag>
              </template>
            </el-table-column>

            <el-table-column label="班级" min-width="150">
              <template #default="{ row }">
                <div class="class-list">
                  <el-tag
                    v-for="cls in row.classes.slice(0, 2)"
                    :key="cls.id"
                    size="small"
                    class="mr-1 mb-1"
                  >
                    {{ cls.name }}
                  </el-tag>
                  <el-tag
                    v-if="row.classes.length > 2"
                    size="small"
                    type="info"
                  >
                    +{{ row.classes.length - 2 }}
                  </el-tag>
                </div>
              </template>
            </el-table-column>

            <el-table-column label="老师" width="100">
              <template #default="{ row }">
                <div class="teacher-info">
                  <span class="teacher-name">{{
                    row.teacherName || "未知"
                  }}</span>
                </div>
              </template>
            </el-table-column>

            <el-table-column label="提交情况" width="120">
              <template #default="{ row }">
                <div class="submission-stats">
                  <div class="stats-text">
                    {{ row.submissionCount }}/{{ row.totalStudents }}
                  </div>
                  <el-progress
                    :percentage="getSubmissionPercentageForList(row)"
                    :stroke-width="6"
                    :show-text="false"
                    class="stats-progress"
                  />
                </div>
              </template>
            </el-table-column>

            <el-table-column
              prop="startDate"
              label="开始时间"
              width="110"
              sortable="custom"
            >
              <template #default="{ row }">
                {{ formatDate(row.startDate) }}
              </template>
            </el-table-column>

            <el-table-column
              prop="endDate"
              label="截止时间"
              width="110"
              sortable="custom"
            >
              <template #default="{ row }">
                <div :class="{ 'text-danger': row.isExpired }">
                  {{ formatDate(row.endDate) }}
                </div>
              </template>
            </el-table-column>

            <el-table-column label="操作" width="200" fixed="right">
              <template #default="{ row }">
                <div class="action-buttons">
                  <el-button
                    type="primary"
                    size="small"
                    link
                    @click="handleView(row)"
                    :icon="View"
                  >
                    查看
                  </el-button>
                  <el-button
                    type="primary"
                    size="small"
                    link
                    @click="handleEdit(row)"
                    :icon="Edit"
                  >
                    编辑
                  </el-button>
                  <el-dropdown
                    @command="(command) => handleStatusAction(command, row)"
                  >
                    <el-button type="primary" size="small" link>
                      状态
                      <el-icon class="el-icon--right"><arrow-down /></el-icon>
                    </el-button>
                    <template #dropdown>
                      <el-dropdown-menu>
                        <el-dropdown-item
                          v-if="row.status === AssignmentStatus.DRAFT"
                          command="publish"
                        >
                          发布
                        </el-dropdown-item>
                        <el-dropdown-item
                          v-if="row.status === AssignmentStatus.PUBLISHED"
                          command="terminate"
                        >
                          终止
                        </el-dropdown-item>
                        <el-dropdown-item
                          v-if="row.status === AssignmentStatus.TERMINATED"
                          command="republish"
                        >
                          重新发布
                        </el-dropdown-item>
                      </el-dropdown-menu>
                    </template>
                  </el-dropdown>
                  <el-button
                    type="danger"
                    size="small"
                    link
                    @click="handleDelete(row)"
                    :icon="Delete"
                  >
                    删除
                  </el-button>
                </div>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>

      <!-- 分页区域 -->
      <div
        v-if="pagination.total > 0"
        class="pagination-section"
        ref="paginationRef"
      >
        <el-pagination
          :current-page="pagination.page"
          :page-size="pagination.pageSize"
          :page-sizes="[5, 10, 15, 50]"
          :total="pagination.total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        />
      </div>
    </div>

    <!-- 作业详情抽屉 -->
    <el-drawer v-model="detailVisible" title="作业详情" size="50%">
      <assignment-detail
        v-if="detailVisible && currentAssignment"
        :assignment="currentAssignment"
        @edit="handleEditFromDetail"
        @close="detailVisible = false"
      />
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted, nextTick } from "vue";
import { useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import {
  Plus,
  Refresh,
  Search,
  Grid,
  List,
  View,
  Edit,
  Delete,
  ArrowDown,
} from "@element-plus/icons-vue";
import { assignmentApi, AssignmentStatus } from "../../../api/assignments";
import type {
  Assignment,
  AssignmentListItem,
  AssignmentQueryParams,
} from "../../../types/assignments";
import AssignmentCard from "./components/AssignmentCard.vue";
import AssignmentDetail from "./components/AssignmentDetail.vue";
import PageHeader from "../../../components/PageHeader.vue";
import moment from "moment";

const router = useRouter();

// 响应式数据
const loading = ref(false);
const assignmentList = ref<AssignmentListItem[]>([]);
const detailVisible = ref(false);
const currentAssignment = ref<Assignment | null>(null);
const viewMode = ref<"grid" | "list">("grid");

// 自适应高度相关
const containerRef = ref<HTMLElement>();
const searchRef = ref<HTMLElement>();
const contentRef = ref<HTMLElement>();
const paginationRef = ref<HTMLElement>();
const contentHeight = ref("400px");

// 搜索表单
const searchForm = reactive<AssignmentQueryParams>({
  search: "",
  status: undefined,
  className: "",
  isExpired: undefined,
});

// 分页数据
const pagination = reactive({
  page: 1,
  pageSize: 10,
  total: 0,
});

// 排序数据
const sortData = reactive({
  sort: "createdAt",
  order: "desc" as "asc" | "desc",
});

// 动态高度计算
const calculateContentHeight = () => {
  if (!containerRef.value || !searchRef.value) return;

  try {
    const containerRect = containerRef.value.getBoundingClientRect();
    const searchRect = searchRef.value.getBoundingClientRect();

    // 容器总高度
    const containerHeight = containerRect.height;

    // 计算已用高度
    let usedHeight = 0;
    usedHeight += 32; // 容器padding (16px * 2)
    usedHeight += searchRect.height + 24; // 搜索区域 + margin

    // 如果有分页区域，计算分页高度
    if (paginationRef.value) {
      const paginationRect = paginationRef.value.getBoundingClientRect();
      usedHeight += paginationRect.height + 32; // 分页区域 + margin
    } else {
      usedHeight += 32; // 预留分页区域高度
    }

    // 计算内容可用高度
    const availableHeight = containerHeight - usedHeight;
    const minHeight = 300;
    const finalHeight = Math.max(availableHeight, minHeight);

    contentHeight.value = `${finalHeight}px`;

    console.log("🔍 作业管理页面高度计算:", {
      容器总高度: containerHeight,
      搜索区域高度: searchRect.height,
      分页区域高度: paginationRef.value?.getBoundingClientRect().height || 0,
      已用高度: usedHeight,
      内容可用高度: availableHeight,
      最终内容高度: contentHeight.value,
    });
  } catch (error) {
    console.error("❌ 计算内容高度失败:", error);
    contentHeight.value = "400px";
  }
};

const debounce = (func: Function, wait: number) => {
  let timeout: number | null = null;
  return (...args: any[]) => {
    if (timeout) clearTimeout(timeout);
    timeout = setTimeout(() => func.apply(null, args), wait);
  };
};

const debouncedCalculate = debounce(calculateContentHeight, 100);

const handleResize = () => {
  debouncedCalculate();
};

// 获取作业列表
const getAssignmentList = async () => {
  loading.value = true;
  try {
    const params: AssignmentQueryParams = {
      page: pagination.page,
      pageSize: pagination.pageSize,
      sort: sortData.sort,
      order: sortData.order,
      ...searchForm,
    };

    // 过滤空值
    Object.keys(params).forEach((key) => {
      if (
        params[key] === "" ||
        params[key] === undefined ||
        params[key] === null
      ) {
        delete params[key];
      }
    });

    const response = await assignmentApi.getAssignments(params);
    assignmentList.value = response.items;
    pagination.total = response.total;

    // 重新计算高度
    nextTick(() => {
      setTimeout(() => {
        calculateContentHeight();
      }, 50);
    });
  } catch (error) {
    console.error("获取作业列表失败:", error);
    ElMessage.error("获取作业列表失败");
  } finally {
    loading.value = false;
  }
};

// 刷新数据
const refreshData = () => {
  getAssignmentList();
};

// 搜索
const handleSearch = () => {
  pagination.page = 1;
  getAssignmentList();
};

// 重置搜索
const handleReset = () => {
  Object.assign(searchForm, {
    search: "",
    status: undefined,
    className: "",
    isExpired: undefined,
  });
  pagination.page = 1;
  getAssignmentList();
};

// 视图模式切换
const handleViewModeChange = (mode: "grid" | "list") => {
  viewMode.value = mode;
  // 调整分页大小
  if (mode === "grid") {
    pagination.pageSize = 18;
  } else {
    pagination.pageSize = 20;
  }
  pagination.page = 1;
  getAssignmentList();
};

// 排序变化
const handleSortChange = ({ prop, order }: any) => {
  if (order) {
    sortData.sort = prop;
    sortData.order = order === "ascending" ? "asc" : "desc";
  } else {
    sortData.sort = "createdAt";
    sortData.order = "desc";
  }
  getAssignmentList();
};

// 分页变化
const handleSizeChange = (size: number) => {
  pagination.pageSize = size;
  pagination.page = 1;
  getAssignmentList();
};

const handleCurrentChange = (page: number) => {
  pagination.page = page;
  getAssignmentList();
};

// 创建作业
const handleCreate = () => {
  router.push("/teacher/assignmentsEdit");
};

// 编辑作业
const handleEdit = (assignment: AssignmentListItem) => {
  router.push(`/teacher/assignmentsEdit?id=${assignment.id}`);
};

// 查看作业详情 - 跳转到详情页面
const handleView = (assignment: AssignmentListItem) => {
  router.push({
    path: "/teacher/assignments/detail",
    query: { id: assignment.id },
  });
};

// 从详情页编辑
const handleEditFromDetail = () => {
  detailVisible.value = false;
  if (currentAssignment.value) {
    router.push({
      path: "/teacher/assignmentsEdit",
      query: { id: currentAssignment.value.id },
    });
  }
};

// 发布作业
const handlePublish = async (assignment: AssignmentListItem) => {
  try {
    await ElMessageBox.confirm("确定要发布这个作业吗？", "确认发布", {
      type: "warning",
    });

    await assignmentApi.updateAssignmentStatus(assignment.id, {
      status: AssignmentStatus.PUBLISHED,
    });

    ElMessage.success("作业发布成功");
    getAssignmentList();
  } catch (error: any) {
    if (error !== "cancel") {
      console.error("发布失败:", error);
      ElMessage.error("发布失败");
    }
  }
};

// 终止作业
const handleTerminate = async (assignment: AssignmentListItem) => {
  try {
    await ElMessageBox.confirm("确定要终止这个作业吗？", "确认终止", {
      type: "warning",
    });

    const { value } = await ElMessageBox.prompt(
      "请输入终止原因（可选）",
      "终止作业",
      {
        inputType: "textarea",
        inputPlaceholder: "请输入终止原因",
      }
    );

    await assignmentApi.updateAssignmentStatus(assignment.id, {
      status: AssignmentStatus.TERMINATED,
      terminatedReason: value || "",
    });

    ElMessage.success("作业终止成功");
    getAssignmentList();
  } catch (error: any) {
    if (error !== "cancel") {
      console.error("终止失败:", error);
      ElMessage.error("终止失败");
    }
  }
};

// 重新发布作业
const handleRepublish = async (assignment: AssignmentListItem) => {
  try {
    await ElMessageBox.confirm("确定要重新发布这个作业吗？", "确认重新发布", {
      type: "warning",
    });

    await assignmentApi.updateAssignmentStatus(assignment.id, {
      status: AssignmentStatus.PUBLISHED,
    });

    ElMessage.success("作业重新发布成功");
    getAssignmentList();
  } catch (error: any) {
    if (error !== "cancel") {
      console.error("重新发布失败:", error);
      ElMessage.error("重新发布失败");
    }
  }
};

// 状态操作（表格视图）
const handleStatusAction = async (
  command: string,
  assignment: AssignmentListItem
) => {
  switch (command) {
    case "publish":
      await handlePublish(assignment);
      break;
    case "terminate":
      await handleTerminate(assignment);
      break;
    case "republish":
      await handleRepublish(assignment);
      break;
  }
};

// 删除作业
const handleDelete = async (assignment: AssignmentListItem) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除作业"${assignment.title}"吗？此操作不可恢复。`,
      "确认删除",
      {
        type: "warning",
        confirmButtonText: "确定删除",
        confirmButtonClass: "el-button--danger",
      }
    );

    await assignmentApi.deleteAssignment(assignment.id);
    ElMessage.success("删除成功");
    getAssignmentList();
  } catch (error: any) {
    if (error !== "cancel") {
      console.error("删除失败:", error);
      ElMessage.error("删除失败");
    }
  }
};

// 工具函数
const getStatusType = (status: AssignmentStatus) => {
  switch (status) {
    case AssignmentStatus.DRAFT:
      return "info";
    case AssignmentStatus.PUBLISHED:
      return "success";
    case AssignmentStatus.TERMINATED:
      return "warning";
    default:
      return "info";
  }
};

const getStatusText = (status: AssignmentStatus) => {
  switch (status) {
    case AssignmentStatus.DRAFT:
      return "草稿";
    case AssignmentStatus.PUBLISHED:
      return "已发布";
    case AssignmentStatus.TERMINATED:
      return "已终止";
    default:
      return "未知";
  }
};

const getSubmissionPercentage = (stats: Assignment["submissionStats"]) => {
  if (stats.total === 0) return 0;
  return Math.round((stats.submitted / stats.total) * 100);
};

const getSubmissionPercentageForList = (assignment: AssignmentListItem) => {
  if (assignment.submissionCount === 0 || assignment.totalStudents === 0)
    return 0;
  return Math.round(
    (assignment.submissionCount / assignment.totalStudents) * 100
  );
};

const formatDate = (dateString: string) => {
  // 使用moment格式化为 YYYY/MM/DD HH:mm
  return moment(dateString).format("YYYY/MM/DD HH:mm");
};

// 初始化
onMounted(() => {
  getAssignmentList();
  nextTick(() => {
    setTimeout(() => {
      calculateContentHeight();
    }, 100);
  });
  window.addEventListener("resize", handleResize);
});

onUnmounted(() => {
  window.removeEventListener("resize", handleResize);
});
</script>

<style scoped>
.assignments-management {
  height: 100%;
  display: flex;
  flex-direction: column;
  background-color: #f8fafc;
}

/* 内容容器 */
.assignments-container {
  display: flex;
  flex-direction: column;
  width: 100%;
  margin: 0 auto;
  box-sizing: border-box;
  overflow: hidden;
}

/* 搜索区域 */
.search-section {
  flex-shrink: 0;
  margin-bottom: 24px;
}

.search-form {
  background: white;
  padding: 20px 24px;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  border: 1px solid #e5e7eb;
}

.search-row {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  align-items: end;
}

.view-controls {
  margin-left: auto;
}

:deep(.el-form-item) {
  margin-bottom: 0;
}

:deep(.el-form-item__label) {
  font-weight: 500;
  color: #374151;
  font-size: 14px;
}

/* 内容区域 */
.content-section {
  flex: 1;
  overflow-y: auto;
  background: white;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  display: flex;
  flex-direction: column;
}

/* 作业网格 */
.assignments-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 20px;
}

/* 作业列表 */
.assignments-list {
  flex: 1;
  display: flex;
  flex-direction: column;
}

/* 空状态 */
.empty-state {
  text-align: center;
  padding: 80px 20px;
}

.empty-icon {
  font-size: 64px;
  margin-bottom: 20px;
}

.empty-title {
  font-size: 20px;
  font-weight: 600;
  color: #1f2937;
  margin: 0 0 12px 0;
}

.empty-desc {
  font-size: 14px;
  color: #6b7280;
  margin: 0 0 24px 0;
}

.empty-action {
  margin-top: 8px;
}

/* 分页区域 */
.pagination-section {
  flex-shrink: 0;
  margin-top: 24px;
  display: flex;
  justify-content: center;
}

/* 表格和卡片相关样式 */
.assignment-title-cell {
  display: flex;
  align-items: center;
}

.class-list {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.teacher-info {
  display: flex;
  align-items: center;
}

.teacher-name {
  color: #606266;
  font-size: 13px;
  font-weight: 500;
}

.submission-stats {
  text-align: center;
}

.stats-text {
  font-size: 12px;
  color: #606266;
  margin-bottom: 4px;
}

.stats-progress {
  width: 80px;
}

.action-buttons {
  display: flex;
  align-items: center;
  gap: 8px;
}

.text-danger {
  color: #f56c6c;
}

/* 工具类 */
.mr-1 {
  margin-right: 4px;
}

.mb-1 {
  margin-bottom: 4px;
}

.ml-2 {
  margin-left: 8px;
}

/* Element Plus 样式重写 */
:deep(.el-table) {
  border-radius: 0;
}

:deep(.el-input__wrapper) {
  border-radius: 6px;
}

:deep(.el-select .el-input__wrapper) {
  border-radius: 6px;
}

:deep(.el-radio-group) {
  border-radius: 6px;
}

:deep(.el-radio-button__inner) {
  border-radius: 0;
  padding: 8px 12px;
  font-size: 13px;
}

:deep(.el-radio-button:first-child .el-radio-button__inner) {
  border-radius: 6px 0 0 6px;
}

:deep(.el-radio-button:last-child .el-radio-button__inner) {
  border-radius: 0 6px 6px 0;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .assignments-container {
    padding-left: 16px;
    padding-right: 16px;
  }

  .search-row {
    flex-direction: column;
    align-items: stretch;
  }

  .search-row .el-form-item {
    width: 100%;
  }

  .assignments-grid {
    grid-template-columns: 1fr;
    gap: 16px;
  }
}

/* 优化卡片悬浮效果 */
:deep(.el-card) {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}
</style>
