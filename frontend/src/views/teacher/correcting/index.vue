<template>
  <adaptive-table-container
    :loading="loading"
    loading-text="加载中..."
    :recalculate-trigger="recalculateTrigger"
    ref="adaptiveTableRef"
  >
    <!-- 搜索区域 -->
    <template #search>
      <el-form
        :inline="true"
        :model="searchForm"
        size="default"
        class="flex flex-wrap items-center"
      >
        <el-form-item label="班级">
          <el-select
            v-model="searchForm.classId"
            placeholder="请选择班级"
            clearable
            style="width: 200px"
          >
            <el-option
              v-for="cls in classList"
              :key="cls._id"
              :label="cls.name"
              :value="cls._id"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="作业">
          <el-select
            v-model="searchForm.assignmentId"
            placeholder="请选择作业"
            clearable
            style="width: 200px"
            :disabled="!searchForm.classId"
          >
            <el-option
              v-for="assignment in assignmentList"
              :key="assignment.id || assignment._id"
              :label="assignment.title"
              :value="assignment.id || assignment._id"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="作业状态">
          <el-select
            v-model="searchForm.status"
            placeholder="请选择状态"
            clearable
            style="width: 150px"
            @change="handleSearch"
          >
            <el-option label="全部" value="" />
            <el-option label="草稿" value="draft" />
            <el-option label="已提交(待批改)" value="submitted" />
            <el-option label="AI已评(待人工批改)" value="ai_reviewed" />
            <el-option label="已批改" value="teacher_reviewed" />
          </el-select>
        </el-form-item>

        <el-form-item label="学生姓名">
          <el-input
            v-model="searchForm.studentName"
            placeholder="请输入学生姓名"
            clearable
            style="width: 150px"
            @keyup.enter="handleSearch"
            @blur="trimSearchField('studentName')"
          />
        </el-form-item>

        <el-form-item class="mb-0 flex-shrink-0">
          <el-button type="primary" @click="handleSearch">
            <el-icon><Search /></el-icon>搜索
          </el-button>
          <el-button @click="resetSearch">
            <el-icon><Refresh /></el-icon>重置
          </el-button>
        </el-form-item>
      </el-form>
    </template>

    <!-- 表格区域 -->
    <template #table="{ tableHeight }">
      <submission-table
        :submission-data="submissionList"
        :max-height="tableHeight"
      />
    </template>

    <!-- 分页区域 -->
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
  </adaptive-table-container>
</template>

<script lang="ts" setup>
import { ref, reactive, computed, onMounted, watch } from "vue";
import { ElMessage } from "element-plus";
import { useStore } from "vuex";
import { Search, Refresh } from "@element-plus/icons-vue";

// 导入组件
import AdaptiveTableContainer from "@/components/AdaptiveTableContainer.vue";
import SubmissionTable from "./components/SubmissionTable.vue";

// 导入API接口
import { getClassList } from "@/api/classes";
import { getAssignmentList } from "@/api/assignments";
import { getSubmissionList } from "@/api/correcting";
import type { SubmissionQueryParams, SubmissionRecord } from "@/api/correcting";

// Store
const store = useStore();

// 响应式设计 - 检测设备类型
const device = computed(() => store.getters["app/device"]);
const isMobile = computed(
  () => device.value === "mobile" || device.value === "tablet"
);

// 搜索表单数据
const searchForm = reactive({
  classId: "",
  assignmentId: "",
  status: "", // 统一使用status字段表示作业状态
  studentName: "",
});

// 分页数据
const pagination = reactive({
  page: 1,
  limit: 20,
  total: 0,
});

// 数据状态
const loading = ref(true);
const submissionList = ref<SubmissionRecord[]>([]);
const classList = ref([]);
const assignmentList = ref([]);

// 组件引用
const adaptiveTableRef = ref(null);

// 触发重新计算表格高度的计数器
const recalculateTrigger = ref(0);

// 监听班级变化，加载对应作业
watch(
  () => searchForm.classId,
  async (newClassId) => {
    if (newClassId) {
      await loadAssignmentList(newClassId);
      // 班级变化时清空作业选择
      searchForm.assignmentId = "";
      // 班级变化时自动搜索该班级的数据
      handleSearch();
    } else {
      assignmentList.value = [];
      searchForm.assignmentId = "";
      // 清空班级时重新搜索
      handleSearch();
    }
  }
);

// 监听作业变化
watch(
  () => searchForm.assignmentId,
  () => {
    // 作业变化时自动搜索
    handleSearch();
  }
);

// 自动清理输入框空格
const trimSearchField = (field: string) => {
  if (searchForm[field]) {
    searchForm[field] = searchForm[field].trim();
  }
};

// 加载班级列表
const loadClassList = async () => {
  try {
    const response = await getClassList({});
    classList.value = response.items || [];
  } catch (error) {
    console.error("加载班级列表失败", error);
    ElMessage.error("加载班级列表失败");
  }
};

// 加载作业列表
const loadAssignmentList = async (classId: string) => {
  try {
    const response = await getAssignmentList({
      classId,
      page: 1,
      pageSize: 100, // 获取足够多的作业用于下拉选择
    });
    assignmentList.value = response.items || [];
  } catch (error) {
    console.error("加载作业列表失败", error);
    ElMessage.error("加载作业列表失败");
  }
};

// 加载提交列表数据
const loadSubmissionData = async () => {
  loading.value = true;
  try {
    // 构建查询参数
    const params: SubmissionQueryParams = {
      page: pagination.page,
      limit: pagination.limit,
    };

    // 添加搜索条件（所有条件都是可选的）
    if (searchForm.assignmentId && searchForm.assignmentId.trim())
      params.assignmentId = searchForm.assignmentId;
    if (searchForm.classId && searchForm.classId.trim())
      params.classId = searchForm.classId;
    if (searchForm.status && searchForm.status.trim())
      params.status = searchForm.status;
    if (searchForm.studentName && searchForm.studentName.trim())
      params.studentName = searchForm.studentName;

    // 默认排序
    params.sortBy = "submittedAt";
    params.sortOrder = "desc";

    const response = await getSubmissionList(params);

    // 注意：request拦截器已经返回了data部分，所以直接访问response.items
    if (response && response.items) {
      submissionList.value = response.items || [];
      pagination.total = response.total || 0;
    } else {
      console.error("响应数据结构不正确:", response);
      submissionList.value = [];
      pagination.total = 0;
    }
  } catch (error) {
    console.error("加载提交数据失败", error);
    ElMessage.error("加载提交列表失败");
  } finally {
    loading.value = false;

    // 触发表格高度重新计算
    recalculateTrigger.value++;
  }
};

// 重置搜索
const resetSearch = () => {
  Object.assign(searchForm, {
    classId: "",
    assignmentId: "",
    status: "",
    studentName: "",
  });
  assignmentList.value = [];
  pagination.page = 1;
  loadSubmissionData();
};

// 处理搜索
const handleSearch = () => {
  pagination.page = 1;
  loadSubmissionData();
};

// 处理分页变化
const handleSizeChange = (val: number) => {
  pagination.limit = val;
  loadSubmissionData();
};

const handleCurrentChange = (val: number) => {
  pagination.page = val;
  loadSubmissionData();
};

// 注意：表格相关的函数已移至 SubmissionTable 组件中

// 组件挂载时加载数据
onMounted(async () => {
  await loadClassList();
  await loadSubmissionData();
});
</script>
