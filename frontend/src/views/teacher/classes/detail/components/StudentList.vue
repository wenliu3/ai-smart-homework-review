<template>
  <div class="student-management">
    <!-- 学生搜索和筛选 -->
    <div class="mb-4">
      <el-form
        :inline="true"
        :model="searchForm"
        class="flex flex-wrap items-center gap-4"
      >
        <!-- 学生总数 -->
        <el-form-item class="!mb-0">
          一共有<el-tag>{{ pagination.total }}</el-tag
          >名学生
        </el-form-item>
        <el-form-item label="学生姓名" class="!mb-0">
          <el-input
            v-model="searchForm.search"
            placeholder="搜索学生姓名"
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
            <el-option label="活跃" value="active" />
            <el-option label="暂停" value="inactive" />
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
        </el-form-item>
        <el-form-item class="!mb-0">
          <el-button
            type="primary"
            :icon="User"
            size="default"
            @click="showAddStudentDialog = true"
          >
            添加学生
          </el-button>
        </el-form-item>
        <el-form-item class="!mb-0">
          <el-dropdown>
            <el-button type="default">
              批量操作<el-icon class="el-icon--right"><arrow-down /></el-icon>
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item
                  :disabled="selectedStudents.length === 0"
                  @click="handleBatchUpdateStatus('active')"
                  >批量激活</el-dropdown-item
                >
                <el-dropdown-item
                  :disabled="selectedStudents.length === 0"
                  @click="handleBatchUpdateStatus('inactive')"
                  >批量暂停</el-dropdown-item
                >
                <el-dropdown-item
                  :disabled="selectedStudents.length === 0"
                  @click="handleBatchRemove"
                  >批量移除</el-dropdown-item
                >
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </el-form-item>
      </el-form>
    </div>

    <!-- 学生列表 -->
    <div
      v-loading="loading"
      element-loading-text="加载中..."
      class="bg-white rounded-lg border border-gray-200"
    >
      <!-- 空状态 -->
      <div v-if="studentData.length === 0" class="text-center py-8">
        <div class="text-5xl mb-3">👥</div>
        <h3 class="text-lg font-medium text-gray-900 mb-2">暂无学生</h3>
        <p class="text-gray-500 mb-4">点击"添加学生"按钮开始添加学生到班级</p>
        <el-button
          type="primary"
          :icon="User"
          @click="showAddStudentDialog = true"
        >
          添加学生
        </el-button>
      </div>

      <!-- 学生表格 -->
      <el-table
        v-else
        :data="studentData"
        style="width: 100%"
        size="default"
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="50" />

        <el-table-column label="学生信息" min-width="180">
          <template #default="{ row }">
            <div class="flex items-center space-x-3">
              <el-avatar :src="row.avatar" :size="36" class="flex-shrink-0">
                {{ row.studentName?.charAt(0) || "?" }}
              </el-avatar>
              <div>
                <div class="font-medium text-gray-900">
                  {{ row.studentName || "未知" }}
                </div>
                <div class="text-sm text-gray-500">
                  {{ row.studentNumber || "暂无学号" }}
                </div>
              </div>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-tag
              :type="row.status === 'active' ? 'success' : 'warning'"
              size="small"
            >
              {{ row.status === "active" ? "活跃" : "暂停" }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="作业统计" width="120">
          <template #default="{ row }">
            <div class="text-center">
              <div class="text-sm font-medium text-blue-600">
                {{ row.totalSubmissions || 0 }} 个
              </div>
              <div class="text-xs text-gray-500">累计提交</div>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="最后提交" width="140">
          <template #default="{ row }">
            <span class="text-sm text-gray-600">
              {{
                row.lastSubmissionTime
                  ? formatDate(row.lastSubmissionTime)
                  : "暂无提交"
              }}
            </span>
          </template>
        </el-table-column>

        <el-table-column label="加入方式" width="100">
          <template #default="{ row }">
            <span class="text-sm text-gray-600">
              {{ row.joinMethod === "teacher" ? "教师添加" : "自行加入" }}
            </span>
          </template>
        </el-table-column>

        <el-table-column label="加入时间" width="140">
          <template #default="{ row }">
            <span class="text-sm text-gray-600">
              {{ formatDate(row.joinedAt) }}
            </span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <div class="flex items-center space-x-1">
              <el-button
                v-if="row.status === 'active'"
                size="small"
                type="warning"
                @click="handleUpdateStatus([row.studentId], 'inactive')"
              >
                暂停
              </el-button>
              <el-button
                v-else
                size="small"
                type="success"
                @click="handleUpdateStatus([row.studentId], 'active')"
              >
                激活
              </el-button>
              <el-button
                size="small"
                type="danger"
                @click="handleRemove([row.studentId])"
              >
                移除
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 分页 -->
    <div v-if="pagination.total > 0" class="flex justify-center mt-4">
      <el-pagination
        :current-page="pagination.page"
        :page-size="pagination.limit"
        :page-sizes="[3, 5, 10, 20, 50, 100]"
        :total="pagination.total"
        background
        size="default"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="handleSizeChange"
        @current-change="handleCurrentChange"
      />
    </div>

    <!-- 添加学生对话框 -->
    <add-student-dialog
      v-model="showAddStudentDialog"
      :class-id="classId"
      @success="handleAddStudentSuccess"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { User, Refresh, Search } from "@element-plus/icons-vue";
import moment from "moment";
import { getClassStudents, updateStudentStatus } from "@/api/classes";
import type {
  ClassStudent,
  ClassStudentQueryParams,
  UpdateStudentStatusParams,
} from "@/types/classes";
import AddStudentDialog from "./AddStudentDialog.vue";

interface Props {
  classId: string;
}

interface Emits {
  (e: "student-count-change", count: number): void;
}

const props = defineProps<Props>();
const emit = defineEmits<Emits>();

// 数据状态
const loading = ref(false);
const studentData = ref<ClassStudent[]>([]);
const selectedStudents = ref<ClassStudent[]>([]);
const showAddStudentDialog = ref(false);

// 搜索表单
const searchForm = reactive<ClassStudentQueryParams>({
  search: "",
  status: undefined,
  sortField: "joinedAt",
  sortOrder: "desc",
});

// 分页数据
const pagination = reactive({
  page: 1,
  limit: 20,
  total: 0,
});

// 加载学生列表
const loadStudentList = async () => {
  loading.value = true;
  try {
    const params: ClassStudentQueryParams = {
      page: pagination.page,
      limit: pagination.limit,
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

    const response = await getClassStudents(props.classId, params);
    studentData.value = response.items;
    pagination.total = response.total;

    // 通知父组件学生数量变化
    emit("student-count-change", response.total);
  } catch (error) {
    console.error("加载学生列表失败:", error);
    ElMessage.error("加载学生列表失败");
  } finally {
    loading.value = false;
  }
};

// 格式化日期
const formatDate = (dateStr: string) => {
  return moment(dateStr).format("YYYY-MM-DD HH:mm:ss");
};

// 处理选择变化
const handleSelectionChange = (selection: ClassStudent[]) => {
  selectedStudents.value = selection;
};

// 搜索处理
const handleSearch = () => {
  pagination.page = 1;
  loadStudentList();
};

// 重置搜索
const resetSearch = () => {
  Object.assign(searchForm, {
    search: "",
    status: undefined,
    sortField: "joinedAt",
    sortOrder: "desc",
  });
  pagination.page = 1;
  loadStudentList();
};

// 分页处理
const handleSizeChange = (size: number) => {
  pagination.limit = size;
  loadStudentList();
};

const handleCurrentChange = (page: number) => {
  pagination.page = page;
  loadStudentList();
};

// 更新状态
const handleUpdateStatus = async (
  studentIds: string[],
  status: "active" | "inactive"
) => {
  try {
    const params: UpdateStudentStatusParams = {
      studentIds,
      status,
    };

    await updateStudentStatus(props.classId, params);
    ElMessage.success("学生状态更新成功");
    loadStudentList();
  } catch (error) {
    console.error("更新学生状态失败:", error);
    ElMessage.error("更新学生状态失败");
  }
};

// 移除学生
const handleRemove = async (studentIds: string[]) => {
  try {
    await ElMessageBox.confirm(
      `确定要移除选中的 ${studentIds.length} 名学生吗？移除后学生将不再显示在班级列表中。`,
      "确认移除",
      {
        confirmButtonText: "确定",
        cancelButtonText: "取消",
        type: "warning",
      }
    );

    const params: UpdateStudentStatusParams = {
      studentIds,
      status: "left",
    };

    await updateStudentStatus(props.classId, params);
    ElMessage.success("学生移除成功");
    loadStudentList();
  } catch (error) {
    if (error !== "cancel") {
      console.error("移除学生失败:", error);
      ElMessage.error("移除学生失败");
    }
  }
};

// 批量操作
const handleBatchUpdateStatus = (status: "active" | "inactive") => {
  const studentIds = selectedStudents.value.map((student) => student.studentId);
  handleUpdateStatus(studentIds, status);
  selectedStudents.value = [];
};

const handleBatchRemove = () => {
  const studentIds = selectedStudents.value.map((student) => student.studentId);
  handleRemove(studentIds);
  selectedStudents.value = [];
};

// 添加学生成功回调
const handleAddStudentSuccess = () => {
  showAddStudentDialog.value = false;
  loadStudentList();
};

// 初始化
onMounted(() => {
  loadStudentList();
});

// 组件名称
defineOptions({
  name: "StudentList",
});
</script>

<script lang="ts">
// 添加默认导出以支持常规导入
import { defineComponent } from "vue";

export default defineComponent({
  name: "StudentList",
});
</script>

<style scoped>
:deep(.el-table__body-wrapper) {
  border-radius: 0 0 8px 8px;
}

:deep(.el-table__header-wrapper) {
  border-radius: 8px 8px 0 0;
}
</style>
