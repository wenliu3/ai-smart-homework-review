<template>
  <div class="student-search-form">
    <el-form
      :inline="true"
      :model="searchForm"
      size="default"
      class="search-form"
    >
      <div class="form-container">
        <el-form-item label="班级筛选">
          <el-select
            v-model="searchForm.classId"
            placeholder="请选择班级"
            clearable
            style="width: 180px"
            @change="handleFormChange"
          >
            <el-option label="全部班级" value="" />
            <el-option
              v-for="cls in classes"
              :key="cls.id"
              :label="cls.name"
              :value="cls.id"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="学生姓名">
          <el-input
            v-model="searchForm.studentName"
            placeholder="请输入学生姓名"
            clearable
            style="width: 150px"
            @keyup.enter="handleSearch"
            @blur="trimAndSearch('studentName')"
          >
            <template #prefix>
              <el-icon><User /></el-icon>
            </template>
          </el-input>
        </el-form-item>

        <el-form-item label="学号">
          <el-input
            v-model="searchForm.studentNumber"
            placeholder="请输入学号"
            clearable
            style="width: 150px"
            @keyup.enter="handleSearch"
            @blur="trimAndSearch('studentNumber')"
          >
            <template #prefix>
              <el-icon><Postcard /></el-icon>
            </template>
          </el-input>
        </el-form-item>

        <el-form-item label="提交状态">
          <el-select
            v-model="searchForm.submissionStatus"
            placeholder="请选择提交状态"
            clearable
            style="width: 140px"
            @change="handleFormChange"
          >
            <el-option label="全部状态" value="" />
            <el-option label="已提交" value="submitted">
              <div class="option-with-badge">
                <span>已提交</span>
                <el-tag type="success" size="small">{{
                  submissionStats?.totalSubmissions || 0
                }}</el-tag>
              </div>
            </el-option>
            <el-option label="未提交" value="not_submitted">
              <div class="option-with-badge">
                <span>未提交</span>
                <el-tag type="info" size="small">{{
                  notSubmittedCount
                }}</el-tag>
              </div>
            </el-option>
            <el-option label="草稿状态" value="draft">
              <div class="option-with-badge">
                <span>草稿</span>
                <el-tag type="warning" size="small">{{
                  submissionStats?.draftSubmissions || 0
                }}</el-tag>
              </div>
            </el-option>
          </el-select>
        </el-form-item>

        <el-form-item label="批改状态">
          <el-select
            v-model="searchForm.gradingStatus"
            placeholder="请选择批改状态"
            clearable
            style="width: 140px"
            @change="handleFormChange"
          >
            <el-option label="全部状态" value="" />
            <el-option label="待批改" value="submitted">
              <div class="option-with-badge">
                <span>待批改</span>
                <el-tag type="warning" size="small">{{
                  submissionStats?.pendingSubmissions || 0
                }}</el-tag>
              </div>
            </el-option>
            <el-option label="AI已评" value="ai_reviewed">
              <div class="option-with-badge">
                <span>AI已评</span>
                <el-tag type="primary" size="small">{{
                  aiReviewedCount
                }}</el-tag>
              </div>
            </el-option>
            <el-option label="教师已批改" value="teacher_reviewed">
              <div class="option-with-badge">
                <span>已批改</span>
                <el-tag type="success" size="small">{{
                  submissionStats?.reviewedSubmissions || 0
                }}</el-tag>
              </div>
            </el-option>
          </el-select>
        </el-form-item>

        <div class="form-actions">
          <el-button type="primary" @click="handleSearch" :loading="loading">
            <el-icon><Search /></el-icon>
            搜索
          </el-button>
          <el-button @click="handleReset">
            <el-icon><Refresh /></el-icon>
            重置
          </el-button>
        </div>
      </div>
    </el-form>
  </div>
</template>

<script setup lang="ts">
import { reactive, computed } from "vue";
import { User, Postcard, Search, Refresh } from "@element-plus/icons-vue";

interface Props {
  classes?: Array<{ id: string; name: string }>;
  submissionStats?: {
    totalSubmissions: number;
    reviewedSubmissions: number;
    pendingSubmissions: number;
    draftSubmissions: number;
  } | null;
  totalStudents?: number;
  total?: number;
  loading?: boolean;
}

interface SearchForm {
  classId: string;
  studentName: string;
  studentNumber: string;
  submissionStatus: string;
  gradingStatus: string;
}

interface Emits {
  (e: "search", searchForm: SearchForm): void;
  (e: "reset"): void;
}

const props = withDefaults(defineProps<Props>(), {
  classes: () => [],
  total: 0,
  loading: false,
});

const emit = defineEmits<Emits>();

// 搜索表单
const searchForm = reactive<SearchForm>({
  classId: "",
  studentName: "",
  studentNumber: "",
  submissionStatus: "",
  gradingStatus: "",
});

// 计算未提交人数
const notSubmittedCount = computed(() => {
  const total = props.totalStudents || 0;
  const submitted = props.submissionStats?.totalSubmissions || 0;
  const draft = props.submissionStats?.draftSubmissions || 0;
  return Math.max(0, total - submitted - draft);
});

// 计算AI已评人数（总提交 - 教师已批改 - 待批改）
const aiReviewedCount = computed(() => {
  const total = props.submissionStats?.totalSubmissions || 0;
  const reviewed = props.submissionStats?.reviewedSubmissions || 0;
  const pending = props.submissionStats?.pendingSubmissions || 0;
  return Math.max(0, total - reviewed - pending);
});

// 自动清理输入框并搜索
const trimAndSearch = (field: keyof SearchForm) => {
  if (searchForm[field]) {
    searchForm[field] = (searchForm[field] as string).trim();
  }
  if (searchForm[field] !== "") {
    handleSearch();
  }
};

// 表单变化时自动搜索（下拉框）
const handleFormChange = () => {
  handleSearch();
};

// 搜索
const handleSearch = () => {
  emit("search", { ...searchForm });
};

// 重置
const handleReset = () => {
  Object.assign(searchForm, {
    classId: "",
    studentName: "",
    studentNumber: "",
    submissionStatus: "",
    gradingStatus: "",
  });
  emit("reset");
};

defineOptions({
  name: "StudentSearchForm",
});

defineExpose({
  searchForm,
});
</script>

<style scoped>
.student-search-form {
  background: white;
  border-radius: 8px;
}

.search-form {
  width: 100%;
}

.form-container {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 16px;
  width: 100%;
}

.form-container :deep(.el-form-item) {
  margin-bottom: 0;
  margin-right: 0;
  flex-shrink: 0;
}

.form-container :deep(.el-form-item__label) {
  font-weight: 500;
  color: #374151;
  font-size: 14px;
  margin-bottom: 4px;
}

.form-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
  margin-left: auto;
}

.option-with-badge {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.option-with-badge span {
  flex: 1;
}

.option-with-badge .el-tag {
  margin-left: 8px;
  flex-shrink: 0;
}

/* 响应式设计 */
@media (max-width: 1400px) {
  .form-actions {
    margin-left: 0;
  }
}

@media (max-width: 1200px) {
  .form-container {
    flex-direction: column;
    align-items: stretch;
    gap: 12px;
  }

  .form-container :deep(.el-form-item) {
    width: 100%;
  }

  .form-container :deep(.el-select),
  .form-container :deep(.el-input) {
    width: 100% !important;
  }

  .form-actions {
    margin-left: 0;
    justify-content: flex-start;
  }
}

@media (max-width: 768px) {
  .form-actions {
    flex-direction: column;
    align-items: stretch;
  }

  .form-actions .el-button {
    width: 100%;
  }
}
</style>
