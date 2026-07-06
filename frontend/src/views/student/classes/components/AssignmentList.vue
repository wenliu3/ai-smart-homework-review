<template>
  <div class="flex-1 bg-gray-50 flex flex-col">
    <!-- 未选择班级状态 -->
    <div v-if="!selectedClass" class="h-full flex items-center justify-center">
      <div class="text-center">
        <el-empty description="请选择班级查看作业" :image-size="120">
          <template #description>
            <p class="text-gray-500 mb-4">请从左侧选择一个班级来查看相关作业</p>
          </template>
        </el-empty>
      </div>
    </div>

    <!-- 选中班级的作业区域 -->
    <div v-else class="flex-1 flex flex-col min-h-0">
      <!-- 班级信息头部 -->
      <div class="bg-white px-6 py-4 border-b border-gray-200 flex-shrink-0">
        <div class="flex items-center justify-between">
          <div class="flex-1">
            <h2 class="text-lg font-semibold text-gray-900 mb-2">
              {{ selectedClass.name }}
            </h2>
            <div class="flex items-center text-sm text-gray-600 space-x-4 mb-3">
              <span>教师：{{ selectedClass.teacherName }}</span>
              <span
                >{{ selectedClass.studentCount || 0 }}/{{
                  selectedClass.maxStudents || 60
                }}人</span
              >
              <span>班级码：{{ selectedClass.code }}</span>
            </div>

            <!-- 作业统计信息 -->
            <div class="flex items-center space-x-3 text-xs">
              <template v-if="assignmentLoading">
                <!-- 只有一行骨架屏 -->
                <el-skeleton
                  :rows="0"
                  :count="1"
                  animated
                  style="width: 100%"
                />
              </template>
              <template v-else>
                <el-tag type="primary" size="small"
                  >总计: {{ classStatistics.totalAssignments }}</el-tag
                >
                <el-tag type="success" size="small"
                  >已提交: {{ classStatistics.submittedCount }}</el-tag
                >
                <el-tag type="warning" size="small"
                  >待办: {{ classStatistics.todoCount }}</el-tag
                >
                <el-tag type="info" size="small"
                  >草稿: {{ classStatistics.draftCount }}</el-tag
                >
                <el-tag type="danger" size="small"
                  >过期: {{ classStatistics.expiredCount }}</el-tag
                >

                <el-tag size="small"
                  >已批改: {{ classStatistics.reviewedCount }}</el-tag
                >
              </template>
            </div>
          </div>

          <!-- 退出班级按钮 -->
          <el-button
            type="danger"
            plain
            :icon="Delete"
            @click="handleLeaveClassClick"
          >
            退出班级
          </el-button>
        </div>
      </div>

      <!-- 作业筛选和搜索区域 -->
      <div class="bg-white px-6 py-3 border-b border-gray-200 flex-shrink-0">
        <div class="flex items-center justify-between">
          <!-- 作业业务状态筛选 -->
          <el-radio-group v-model="assignmentFilter" size="default">
            <el-radio-button value="all">全部</el-radio-button>
            <el-radio-button value="todo">待办</el-radio-button>
            <el-radio-button value="draft">草稿</el-radio-button>
            <el-radio-button value="completed">已提交</el-radio-button>
            <!-- <el-radio-button value="submitted_elsewhere">其他班级已提交</el-radio-button> -->
            <el-radio-button value="expired">已过期</el-radio-button>
          </el-radio-group>

          <!-- 搜索框 -->
          <div class="flex items-center space-x-2">
            <el-input
              v-model="assignmentSearchKeyword"
              placeholder="搜索作业"
              size="default"
              style="width: 220px"
              clearable
              @keyup.enter="handleAssignmentSearch"
              @clear="handleAssignmentClearSearch"
            />
            <el-button
              :icon="Search"
              @click="handleAssignmentSearch"
              size="default"
              :loading="assignmentSearchLoading"
            />
          </div>
        </div>
      </div>

      <!-- 作业列表内容区域 - 自适应布局 -->
      <div class="flex-1 min-h-0 flex flex-col">
        <!-- 作业列表 - 可滚动区域 -->
        <div class="flex-1 min-h-0 overflow-y-auto p-4">
          <!-- 作业加载中 -->
          <div v-if="assignmentLoading" class="space-y-3">
            <el-skeleton v-for="i in 3" :key="i" animated>
              <template #template>
                <el-card :body-style="{ padding: '20px' }">
                  <el-skeleton-item variant="h3" style="width: 60%" />
                  <el-skeleton-item
                    variant="text"
                    style="width: 100%; margin-top: 8px"
                  />
                </el-card>
              </template>
            </el-skeleton>
          </div>

          <!-- 作业列表 -->
          <div v-else-if="assignments.length > 0" class="space-y-3">
            <el-card
              v-for="assignment in assignments"
              :key="assignment._id"
              :class="[
                'transition-all duration-200',
                assignment.hasSubmittedInOtherClass
                  ? 'cursor-not-allowed opacity-60 bg-gray-50'
                  : 'cursor-pointer hover:shadow-md',
              ]"
              :body-style="{ padding: '20px' }"
              @click="handleAssignmentClick(assignment)"
            >
              <div class="flex items-center justify-between">
                <div class="flex-1 pr-6">
                  <!-- 作业标题和状态 -->
                  <div class="flex items-center mb-2">
                    <h3 class="font-medium text-gray-900 text-base mr-3">
                      {{ assignment.title }}
                    </h3>

                    <!-- 提交状态标签 - 根据实际状态显示 -->
                    <el-tag
                      v-if="assignment.hasSubmitted"
                      type="success"
                      size="small"
                      effect="light"
                      class="mr-2"
                    >
                      已提交
                    </el-tag>
                    <el-tag
                      v-else-if="assignment.hasSubmittedInOtherClass"
                      type="danger"
                      size="small"
                      effect="light"
                      class="mr-2"
                    >
                      已在其他班级提交
                    </el-tag>
                    <el-tag
                      v-else-if="assignment.hasDraft"
                      type="info"
                      size="small"
                      effect="light"
                      class="mr-2"
                    >
                      有草稿
                    </el-tag>
                    <el-tag
                      v-else
                      type="warning"
                      size="small"
                      effect="light"
                      class="mr-2"
                    >
                      未提交
                    </el-tag>

                    <!-- 批改状态标签 - 只有已提交时才显示 -->
                    <el-tag
                      v-if="
                        assignment.hasSubmitted && assignment.submissionStatus
                      "
                      :type="getReviewStatusType(assignment.submissionStatus)"
                      size="small"
                      effect="light"
                      class="mr-2"
                    >
                      {{ getReviewStatusText(assignment.submissionStatus) }}
                    </el-tag>

                    <!-- 过期状态标签 - 过期时显示，优先于作业状态 -->
                    <el-tag
                      v-if="isAssignmentExpired(assignment)"
                      type="danger"
                      size="small"
                      effect="light"
                      class="mr-2"
                    >
                      已过期
                    </el-tag>

                    <!-- 作业状态标签 - 未过期时显示 -->
                    <el-tag
                      v-else
                      :type="getAssignmentStatusType(assignment.status)"
                      size="small"
                      effect="light"
                    >
                      {{ getAssignmentStatusText(assignment.status) }}
                    </el-tag>
                  </div>

                  <!-- 作业信息 -->
                  <div
                    class="flex items-center text-sm text-gray-500 space-x-4"
                  >
                    <!-- 开始时间 -->
                    <div class="flex items-center">
                      <el-icon class="mr-1" :size="14"><Clock /></el-icon>
                      <span>开始：{{ formatDate(assignment.startDate) }}</span>
                    </div>

                    <!-- 截止时间 -->
                    <div class="flex items-center">
                      <el-icon class="mr-1" :size="14"><Clock /></el-icon>
                      <span>截止：{{ formatDate(assignment.endDate) }}</span>
                    </div>
                  </div>

                  <!-- 其他班级提交信息 -->
                  <div
                    v-if="
                      assignment.hasSubmittedInOtherClass &&
                      assignment.otherClassSubmission
                    "
                    class="mt-2 text-xs text-orange-600 bg-orange-50 p-2 rounded"
                  >
                    <el-icon class="mr-1"><InfoFilled /></el-icon>
                    已在「{{
                      assignment.otherClassSubmission.className
                    }}」班级提交
                    <span v-if="assignment.otherClassSubmission.submittedAt">
                      （{{
                        formatDate(assignment.otherClassSubmission.submittedAt)
                      }}）
                    </span>
                  </div>
                </div>

                <!-- 右侧状态图标 -->
                <div class="flex items-center">
                  <el-icon
                    :size="20"
                    :color="getAssignmentIconColor(assignment)"
                    class="status-icon"
                  >
                    <component :is="getAssignmentIcon(assignment)" />
                  </el-icon>
                </div>
              </div>
            </el-card>
          </div>

          <!-- 空状态 -->
          <div v-else class="h-full flex items-center justify-center">
            <el-empty description="该班级暂无作业" :image-size="120">
              <template #description>
                <p class="text-gray-500">该班级目前还没有发布任何作业</p>
              </template>
            </el-empty>
          </div>
        </div>

        <!-- 分页 - 固定在底部 -->
        <div
          v-if="assignments.length > 0"
          class="flex-shrink-0 bg-white border-t border-gray-200 px-4 py-3"
        >
          <div class="flex justify-center">
            <el-pagination
              :current-page="assignmentPageState.page"
              :page-size="assignmentPageState.limit"
              :page-sizes="[5, 10, 20, 50]"
              layout="total, sizes, prev, pager, next"
              :total="assignmentPageState.total"
              @size-change="handleAssignmentSizeChange"
              @current-change="handleAssignmentPageChange"
              background
              small
            />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, inject, watch, type Ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import {
  Search,
  Delete,
  Clock,
  SuccessFilled,
  CircleCheck,
  Edit,
  DocumentCopy,
  Timer,
  InfoFilled,
} from "@element-plus/icons-vue";
import { useRouter } from "vue-router";

import {
  getMyAssignments,
  getMyAssignmentStatistics,
} from "../../../../api/assignments";
import { useClassManagement } from "../composables/useClassManagement";
import { useAssignmentManagement } from "../composables/useAssignmentManagement";

const router = useRouter();

// 使用组合函数
const { formatDate, handleLeaveClass } = useClassManagement();
const {
  getAssignmentStatusType,
  getAssignmentStatusText,
  isAssignmentExpired,
  getAssignmentIcon,
  getAssignmentIconColor,
} = useAssignmentManagement();

// 通过 inject 获取共享状态
const selectedClass = inject<Ref<any>>("selectedClass")!;
const setSelectedClass = inject<(classItem: any) => void>("setSelectedClass")!;
const refreshClassList = inject<() => void>("refreshClassList")!;

// 组件内部状态
const assignmentLoading = ref(false);
const assignmentSearchLoading = ref(false);
const assignments = ref([]);
const assignmentSearchKeyword = ref("");
const assignmentFilter = ref("all");
const assignmentPageState = reactive({
  page: 1,
  limit: 10,
  total: 0,
});

// 班级作业统计数据
const classStatistics = ref({
  totalAssignments: 0,
  submittedCount: 0,
  todoCount: 0,
  draftCount: 0,
  expiredCount: 0,
  reviewedCount: 0,
});

// 加载班级统计数据
const loadClassStatistics = async (classId: string) => {
  if (!classId) return;

  try {
    const data = await getMyAssignmentStatistics(classId);
    classStatistics.value = data;
  } catch (error) {
    console.error("加载班级统计失败:", error);
    // 不显示错误消息，避免干扰用户体验
  }
};

// 加载作业列表
const loadAssignments = async (
  classId: string,
  search?: string,
  businessStatus?: string
) => {
  if (!classId) return;

  assignmentLoading.value = true;
  try {
    const params: any = {
      classId,
      page: assignmentPageState.page,
      pageSize: assignmentPageState.limit,
      sort: "startDate",
      order: "desc",
    };

    if (search) {
      params.search = search;
    }

    if (businessStatus && businessStatus !== "all") {
      params.businessStatus = businessStatus;
    }

    const response = await getMyAssignments(params);
    assignments.value = response.items || [];
    assignmentPageState.total = response.total || 0;

    // 同时加载统计数据
    await loadClassStatistics(classId);
  } catch (error) {
    console.error("加载作业列表失败:", error);
    ElMessage.error("加载作业列表失败");
  } finally {
    assignmentLoading.value = false;
    assignmentSearchLoading.value = false;
  }
};

// 作业分页大小变化处理
const handleAssignmentSizeChange = (val: number) => {
  assignmentPageState.limit = val;
  assignmentPageState.page = 1;
  loadAssignments(
    selectedClass.value._id,
    assignmentSearchKeyword.value.trim(),
    assignmentFilter.value
  );
};

// 作业分页页码变化处理
const handleAssignmentPageChange = (val: number) => {
  assignmentPageState.page = val;
  loadAssignments(
    selectedClass.value._id,
    assignmentSearchKeyword.value.trim(),
    assignmentFilter.value
  );
};

// 作业搜索处理
const handleAssignmentSearch = async () => {
  if (assignmentSearchLoading.value || !selectedClass.value) return;

  assignmentSearchLoading.value = true;
  assignmentPageState.page = 1;
  try {
    await loadAssignments(
      selectedClass.value._id,
      assignmentSearchKeyword.value.trim(),
      assignmentFilter.value
    );
  } catch (error) {
    ElMessage.error("搜索作业失败");
  }
};

// 清空作业搜索
const handleAssignmentClearSearch = async () => {
  if (!selectedClass.value) return;

  assignmentSearchKeyword.value = "";
  assignmentPageState.page = 1;
  await loadAssignments(selectedClass.value._id, "", assignmentFilter.value);
};

// 获取批改状态类型
const getReviewStatusType = (status: string) => {
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
const getReviewStatusText = (status: string) => {
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

// 处理作业点击
const handleAssignmentClick = (assignment) => {
  // 如果已在其他班级提交，显示提示并阻止进入
  if (assignment.hasSubmittedInOtherClass) {
    const className = assignment.otherClassSubmission?.className || "其他班级";
    ElMessage.warning(
      `该作业已在「${className}」班级提交，无法在当前班级重复作答`
    );
    return;
  }

  // 正常跳转到作业详情
  viewAssignment(assignment.id);
};

// 查看作业详情
const viewAssignment = (assignmentId) => {
  console.log(
    "🔍 查看作业详情 - assignmentId:",
    assignmentId,
    "classId:",
    selectedClass.value._id
  );
  console.log("📏 classId长度:", selectedClass.value._id?.length);

  router.push({
    path: "/student/submissions",
    query: {
      assignmentId: assignmentId,
      classId: selectedClass.value._id,
    },
  });
};

// 监听筛选条件变化
watch(assignmentFilter, () => {
  if (selectedClass.value) {
    assignmentPageState.page = 1;
    loadAssignments(
      selectedClass.value._id,
      assignmentSearchKeyword.value.trim(),
      assignmentFilter.value
    );
  }
});

// 监听选中班级变化
watch(
  selectedClass,
  (newClass) => {
    if (newClass) {
      assignmentPageState.page = 1;
      assignmentSearchKeyword.value = "";
      loadAssignments(newClass._id, "", assignmentFilter.value);
    }
  },
  { immediate: true }
);

// 退出班级
const handleLeaveClassClick = () => {
  if (!selectedClass.value) {
    ElMessage.warning("请先选择要退出的班级");
    return;
  }

  handleLeaveClass(selectedClass.value._id, () => {
    // 重置选中的班级
    setSelectedClass(null);
    // 刷新班级列表
    refreshClassList();
  });
};
</script>

<style scoped>
.status-icon {
  transition: all 0.2s ease;
}

.overflow-y-auto::-webkit-scrollbar {
  width: 6px;
}

.overflow-y-auto::-webkit-scrollbar-track {
  background: #f8fafc;
  border-radius: 3px;
}

.overflow-y-auto::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 3px;
  transition: background 0.2s ease;
}

.overflow-y-auto::-webkit-scrollbar-thumb:hover {
  background: #94a3b8;
}
</style>
