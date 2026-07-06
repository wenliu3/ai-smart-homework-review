<template>
  <div class="assignment-management">
    <!-- 作业搜索和筛选 -->
    <div class="mb-4">
      <el-form
        :inline="true"
        :model="searchForm"
        class="flex flex-wrap items-center gap-4"
      >
        <el-form-item class="!mb-0">
          一共有<el-tag>{{ pagination.total }}</el-tag
          >个作业
        </el-form-item>
        <el-form-item label="作业标题" class="!mb-0">
          <el-input
            v-model="searchForm.search"
            placeholder="搜索作业标题"
            :prefix-icon="Search"
            clearable
            size="default"
            class="w-48"
            @keyup.enter="handleSearch"
          />
        </el-form-item>
        <el-form-item label="状态" class="!mb-0 w-32">
          <el-select
            v-model="searchForm.status"
            placeholder="选择状态"
            clearable
            size="default"
            class="w-32"
          >
            <el-option label="草稿" value="draft" />
            <el-option label="已发布" value="published" />
            <el-option label="已终止" value="terminated" />
          </el-select>
        </el-form-item>
        <el-form-item class="!mb-0">
          <el-button
            type="primary"
            :icon="Search"
            size="default"
            @click="handleSearch"
          >
            搜索
          </el-button>
          <el-button size="default" @click="resetSearch">重置</el-button>
          <el-button
            type="primary"
            :icon="Plus"
            @click="handleCreateAssignment"
          >
            创建作业
          </el-button>
        </el-form-item>
      </el-form>
    </div>

    <!-- 作业列表 -->
    <div v-loading="loading" element-loading-text="加载中..." class="space-y-3">
      <!-- 空状态 -->
      <el-empty v-if="assignments.length === 0 && !loading" :image-size="120">
        <template #description>
          <div class="text-center">
            <h3 class="text-lg font-medium text-gray-900 mb-2">暂无作业</h3>
            <p class="text-gray-500 mb-4">
              点击"创建作业"按钮开始创建第一个作业
            </p>
          </div>
        </template>
        <el-button type="primary" :icon="Plus" @click="handleCreateAssignment">
          创建作业
        </el-button>
      </el-empty>

      <!-- 作业卡片列表 -->
      <div v-else class="assignment-grid">
        <el-card
          v-for="assignment in assignments"
          :key="assignment.id"
          shadow="hover"
          class="assignment-card !border-gray-200"
        >
          <template #header>
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2">
                <el-tag
                  :type="getStatusTagType(assignment.status)"
                  size="default"
                >
                  {{ getStatusText(assignment.status) }}
                </el-tag>
                <el-tag
                  v-if="isAssignmentExpired(assignment)"
                  type="danger"
                  size="default"
                >
                  已过期
                </el-tag>
              </div>
              <el-dropdown
                @command="
                  (command) => handleAssignmentCommand(command, assignment)
                "
              >
                <el-button
                  :icon="MoreFilled"
                  size="default"
                  text
                  class="text-gray-400 hover:text-gray-600"
                />
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="view">
                      查看详情
                    </el-dropdown-item>
                    <el-dropdown-item command="submissions">
                      查看提交
                    </el-dropdown-item>
                    <el-dropdown-item command="edit" divided>
                      编辑作业
                    </el-dropdown-item>
                    <el-dropdown-item
                      v-if="assignment.status === 'published'"
                      command="terminate"
                    >
                      终止作业
                    </el-dropdown-item>
                    <el-dropdown-item
                      v-if="assignment.status === 'draft'"
                      command="publish"
                    >
                      发布作业
                    </el-dropdown-item>
                    <el-dropdown-item
                      command="delete"
                      divided
                      class="text-red-600"
                    >
                      删除作业
                    </el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
            <el-tooltip
              :content="assignment.title"
              placement="top"
              :show-after="1000"
            >
              <h4
                class="text-[14px] font-medium text-gray-900 truncate flex-1 mt-2"
              >
                {{ assignment.title }}
              </h4>
            </el-tooltip>
          </template>

          <!-- 作业描述 -->
          <div
            v-if="assignment.description"
            class="text-[14px] text-gray-600 mb-3 line-clamp-2"
            v-html="assignment.description"
          ></div>

          <!-- 时间信息 -->
          <div
            class="flex items-center text-[14px] mb-3"
            :class="
              isAssignmentExpired(assignment) ? 'text-red-600' : 'text-gray-600'
            "
          >
            <el-icon class="mr-2 text-gray-500">
              <Clock />
            </el-icon>
            <span
              >{{ formatDate(assignment.startDate) }} -
              {{ formatDate(assignment.endDate) }}</span
            >
          </div>

          <!-- 作业统计 -->
          <el-row :gutter="12" class="mb-3">
            <el-col :span="8">
              <div class="bg-blue-50 rounded-lg p-3 text-center">
                <div class="text-[16px] font-medium text-blue-600">
                  {{ assignment.totalSubmissions || 0 }}
                </div>
                <div class="text-[14px] text-blue-500">总提交</div>
              </div>
            </el-col>
            <el-col :span="8">
              <div class="bg-emerald-50 rounded-lg p-3 text-center">
                <div class="text-[16px] font-medium text-emerald-600">
                  {{ assignment.gradedSubmissions || 0 }}
                </div>
                <div class="text-[14px] text-emerald-500">已批改</div>
              </div>
            </el-col>
            <el-col :span="8">
              <div class="bg-amber-50 rounded-lg p-3 text-center">
                <div class="text-[16px] font-medium text-amber-600">
                  {{ assignment.pendingSubmissions || 0 }}
                </div>
                <div class="text-[14px] text-amber-500">待批改</div>
              </div>
            </el-col>
          </el-row>
        </el-card>
      </div>
    </div>

    <!-- 分页 -->
    <div v-if="pagination.total > 0" class="flex justify-center mt-4">
      <el-pagination
        :current-page="pagination.page"
        :page-size="pagination.pageSize"
        :page-sizes="[12, 24, 48]"
        :total="pagination.total"
        background
        size="default"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="handleSizeChange"
        @current-change="handleCurrentChange"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from "vue";
import { useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import {
  Plus,
  Refresh,
  Search,
  MoreFilled,
  Clock,
} from "@element-plus/icons-vue";
import {
  getAssignmentList,
  deleteAssignment,
  updateAssignmentStatus,
  AssignmentStatus,
} from "@/api/assignments";
import type { Assignment, AssignmentQueryParams } from "@/types/assignments";
import moment from "moment";

interface Props {
  classId: string;
}

const props = defineProps<Props>();
const router = useRouter();
const emit = defineEmits<{
  (e: "assignmentCountChange", count: number): void;
}>();

// 数据状态
const loading = ref(false);
const assignments = ref<Assignment[]>([]);

// 搜索表单
const searchForm = reactive<AssignmentQueryParams>({
  search: "",
  status: undefined,
  sort: "createdAt",
  order: "desc",
});

// 分页数据
const pagination = reactive({
  page: 1,
  pageSize: 12,
  total: 0,
});

// 加载作业列表
const loadAssignments = async () => {
  loading.value = true;
  try {
    const params: AssignmentQueryParams = {
      page: pagination.page,
      pageSize: pagination.pageSize,
      className: "", // 通过classId来筛选，需要后端支持或前端过滤
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

    const response = await getAssignmentList(params);

    // 过滤当前班级的作业
    const filteredAssignments = response.items.filter((assignment) =>
      assignment.classes.some((cls) => cls.id === props.classId)
    );

    assignments.value = filteredAssignments;
    pagination.total = filteredAssignments.length;
    emit("assignmentCountChange", filteredAssignments.length);
  } catch (error) {
    console.error("加载作业列表失败:", error);
    ElMessage.error("加载作业列表失败");
  } finally {
    loading.value = false;
  }
};

// 状态标签类型
const getStatusTagType = (status: AssignmentStatus) => {
  switch (status) {
    case AssignmentStatus.PUBLISHED:
      return "success";
    case AssignmentStatus.DRAFT:
      return "info";
    case AssignmentStatus.TERMINATED:
      return "danger";
    default:
      return "info";
  }
};

// 状态文本
const getStatusText = (status: AssignmentStatus) => {
  switch (status) {
    case AssignmentStatus.PUBLISHED:
      return "已发布";
    case AssignmentStatus.DRAFT:
      return "草稿";
    case AssignmentStatus.TERMINATED:
      return "已终止";
    default:
      return "未知";
  }
};

// 判断作业是否过期
const isAssignmentExpired = (assignment: any) => {
  return moment().isAfter(moment(assignment.endDate));
};

// 格式化日期
const formatDate = (dateStr: string) => {
  return moment(dateStr).format("YYYY-MM-DD HH:mm");
};

// 事件处理
const handleCreateAssignment = () => {
  router.push(`/teacher/assignmentsEdit`);
};

const handleSearch = () => {
  pagination.page = 1;
  loadAssignments();
};

const resetSearch = () => {
  Object.assign(searchForm, {
    search: "",
    status: undefined,
    sort: "createdAt",
    order: "desc",
  });
  pagination.page = 1;
  loadAssignments();
};

const handleSizeChange = (size: number) => {
  pagination.pageSize = size;
  pagination.page = 1;
  loadAssignments();
};

const handleCurrentChange = (page: number) => {
  pagination.page = page;
  loadAssignments();
};

const handleAssignmentCommand = async (
  command: string,
  assignment: Assignment
) => {
  switch (command) {
    case "view":
      router.push(`/teacher/assignments/${assignment.id}`);
      break;
    case "submissions":
      router.push(`/teacher/assignments/${assignment.id}/submissions`);
      break;
    case "edit":
      router.push(`/teacher/assignmentsEdit?id=${assignment.id}`);
      break;
    case "publish":
      await handlePublishAssignment(assignment);
      break;
    case "terminate":
      await handleTerminateAssignment(assignment);
      break;
    case "delete":
      await handleDeleteAssignment(assignment);
      break;
  }
};

// 发布作业
const handlePublishAssignment = async (assignment: Assignment) => {
  try {
    await ElMessageBox.confirm(
      `确定要发布作业"${assignment.title}"吗？发布后学生将能够看到并提交作业。`,
      "确认发布",
      { type: "warning" }
    );

    await updateAssignmentStatus(assignment.id, {
      status: AssignmentStatus.PUBLISHED,
    });

    ElMessage.success("作业发布成功");
    loadAssignments();
  } catch (error: any) {
    if (error !== "cancel") {
      console.error("发布作业失败:", error);
      ElMessage.error("发布作业失败");
    }
  }
};

// 终止作业
const handleTerminateAssignment = async (assignment: Assignment) => {
  try {
    const { value: reason } = await ElMessageBox.prompt(
      `确定要终止作业"${assignment.title}"吗？终止后学生将无法继续提交作业。`,
      "确认终止",
      {
        confirmButtonText: "确定",
        cancelButtonText: "取消",
        inputPlaceholder: "请输入终止原因（可选）",
      }
    );

    await updateAssignmentStatus(assignment.id, {
      status: AssignmentStatus.TERMINATED,
      terminatedReason: reason || undefined,
    });

    ElMessage.success("作业已终止");
    loadAssignments();
  } catch (error: any) {
    if (error !== "cancel") {
      console.error("终止作业失败:", error);
      ElMessage.error("终止作业失败");
    }
  }
};

// 删除作业
const handleDeleteAssignment = async (assignment: Assignment) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除作业"${assignment.title}"吗？此操作不可撤销。`,
      "确认删除",
      {
        confirmButtonText: "确定",
        cancelButtonText: "取消",
        type: "warning",
      }
    );

    await deleteAssignment(assignment.id);
    ElMessage.success("作业删除成功");
    loadAssignments();
  } catch (error: any) {
    if (error !== "cancel") {
      console.error("删除作业失败:", error);
      ElMessage.error("删除作业失败");
    }
  }
};

// 初始化
onMounted(() => {
  loadAssignments();
});

// 组件名称
defineOptions({
  name: "AssignmentManagement",
});
</script>

<script lang="ts">
// 添加默认导出以支持常规导入
import { defineComponent } from "vue";

export default defineComponent({
  name: "AssignmentManagement",
});
</script>

<style scoped>
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.assignment-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 14px;
  min-height: 200px;
}

.assignment-card {
  transition: all 0.3s ease;
  width: 100%;
}

.assignment-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 25px rgba(0, 0, 0, 0.12) !important;
}

:deep(.el-descriptions__cell) {
  padding-bottom: 0 !important;
}

:deep(.el-descriptions__label) {
  width: auto;
  color: #666;
  font-weight: normal;
  font-size: 14px;
}

:deep(.el-descriptions__content) {
  font-size: 14px;
}

:deep(.el-dropdown-menu__item) {
  font-size: 14px;
}

:deep(.el-card__header) {
  padding: 16px 20px;
  border-bottom: 1px solid #f0f0f0;
  background: #fafafa;
}

:deep(.el-card__body) {
  padding: 10px 20px;
}
</style>
