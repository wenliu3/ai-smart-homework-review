<template>
  <div class="student-classes-page">
    <!-- 搜索和筛选 -->
    <div class="filter-section mb-6">
      <el-form
        :inline="true"
        :model="searchForm"
        class="flex flex-wrap items-center gap-4"
      >
        <el-form-item label="班级名称" class="mb-0 w-64">
          <el-input
            v-model="searchForm.search"
            placeholder="搜索班级名称"
            :prefix-icon="Search"
            clearable
            size="default"
            @keyup.enter="handleSearch"
          />
        </el-form-item>
        <el-form-item label="班级状态" class="mb-0 w-64">
          <el-select
            v-model="searchForm.status"
            placeholder="选择状态"
            clearable
            size="default"
            class="w-full"
          >
            <el-option label="活跃" value="active" />
            <el-option label="暂停" value="inactive" />
          </el-select>
        </el-form-item>
        <el-form-item class="mb-0">
          <el-button
            type="primary"
            :icon="Search"
            size="default"
            @click="handleSearch"
          >
            搜索
          </el-button>
          <el-button size="default" @click="resetSearch"> 重置 </el-button>
        </el-form-item>
        <el-form-item class="mb-0 ml-auto">
          <!-- 布局切换 -->
          <el-button-group class="mr-3">
            <el-button
              :type="viewMode === 'grid' ? 'primary' : 'default'"
              :icon="Operation"
              size="default"
              @click="viewMode = 'grid'"
              title="网格模式"
            />
            <el-button
              :type="viewMode === 'list' ? 'primary' : 'default'"
              :icon="Menu"
              size="default"
              @click="viewMode = 'list'"
              title="列表模式"
            />
          </el-button-group>
          <el-button
            type="primary"
            :icon="Plus"
            size="default"
            @click="showJoinDialog = true"
          >
            加入班级
          </el-button>
        </el-form-item>
      </el-form>
    </div>

    <!-- 班级列表 -->
    <div
      v-loading="loading"
      element-loading-text="加载中..."
      class="classes-list"
    >
      <!-- 空状态 -->
      <div v-if="classList.length === 0" class="empty-state text-center py-12">
        <div class="text-6xl mb-4">📚</div>
        <h3 class="text-lg font-medium text-gray-900 mb-2">暂无班级</h3>
        <p class="text-gray-500 mb-6">
          您还没有加入任何班级，点击"加入班级"按钮通过邀请码加入班级
        </p>
        <el-button type="primary" :icon="Plus" @click="showJoinDialog = true">
          加入班级
        </el-button>
      </div>

      <!-- 网格模式 -->
      <div
        v-else-if="viewMode === 'grid'"
        class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4"
      >
        <ClassCard
          v-for="classItem in classList"
          :key="classItem._id"
          :class-data="classItem"
          view-mode="grid"
          @view="handleViewClass"
          @leave="handleLeaveClass"
        />
      </div>

      <!-- 列表模式 -->
      <div v-else class="space-y-3">
        <ClassCard
          v-for="classItem in classList"
          :key="classItem._id"
          :class-data="classItem"
          view-mode="list"
          @view="handleViewClass"
          @leave="handleLeaveClass"
        />
      </div>
    </div>

    <!-- 分页 -->
    <div v-if="pagination.total > 0" class="flex justify-center mt-6">
      <el-pagination
        :current-page="pagination.page"
        :page-size="pagination.limit"
        :page-sizes="[6, 12, 18, 24]"
        :total="pagination.total"
        background
        size="default"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="handleSizeChange"
        @current-change="handleCurrentChange"
      />
    </div>

    <!-- 加入班级对话框 -->
    <JoinClassDialog v-model="showJoinDialog" @success="handleJoinSuccess" />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { Plus, Search, Operation, Menu } from "@element-plus/icons-vue";
import { useRouter } from "vue-router";
import { getClassList, leaveClass } from "../../../api/classes";
import type { Class, ClassQueryParams } from "../../../types/classes";
import ClassCard from "./components/ClassCard.vue";
import JoinClassDialog from "../../../components/JoinClassDialog.vue";

const router = useRouter();

// 数据状态
const loading = ref(false);
const classList = ref<Class[]>([]);
const showJoinDialog = ref(false);
const viewMode = ref<"grid" | "list">("grid");

// 搜索表单
const searchForm = reactive<ClassQueryParams>({
  search: "",
  status: undefined,
  sortField: "createdAt",
  sortOrder: "desc",
});

// 分页数据
const pagination = reactive({
  page: 1,
  limit: 12,
  total: 0,
});

// 加载班级列表
const loadClassList = async () => {
  loading.value = true;
  try {
    const params: ClassQueryParams = {
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

    const response = await getClassList(params);
    classList.value = response.items;
    pagination.total = response.total;
  } catch (error) {
    console.error("加载班级列表失败:", error);
    // 错误提示已在统一请求层处理，此处不重复弹出
  } finally {
    loading.value = false;
  }
};

// 搜索处理
const handleSearch = () => {
  pagination.page = 1;
  loadClassList();
};

// 重置搜索
const resetSearch = () => {
  Object.assign(searchForm, {
    search: "",
    status: undefined,
    sortField: "createdAt",
    sortOrder: "desc",
  });
  pagination.page = 1;
  loadClassList();
};

// 分页处理
const handleSizeChange = (size: number) => {
  pagination.limit = size;
  loadClassList();
};

const handleCurrentChange = (page: number) => {
  pagination.page = page;
  loadClassList();
};

// 查看班级详情
const handleViewClass = (classItem: Class) => {
  router.push(`/student/classes/${classItem._id}`);
};

// 退出班级
const handleLeaveClass = async (classItem: Class) => {
  try {
    await ElMessageBox.confirm(
      `确定要退出班级"${classItem.name}"吗？退出后将无法查看班级内容。`,
      "确认退出",
      {
        confirmButtonText: "确定",
        cancelButtonText: "取消",
        type: "warning",
      }
    );

    await leaveClass(classItem._id);
    ElMessage.success("已成功退出班级");
    loadClassList();
  } catch (error) {
    if (error !== "cancel") {
      console.error("退出班级失败:", error);
      // 错误提示已在统一请求层处理，此处不重复弹出
    }
  }
};

// 加入班级成功回调
const handleJoinSuccess = () => {
  loadClassList();
};

// 初始化
onMounted(() => {
  loadClassList();
});
</script>

<style scoped>
.student-classes-page {
  background-color: #f8fafc;
}

.filter-section {
  background: white;
  padding: 20px;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.classes-list {
  min-height: 400px;
}

.empty-state {
  background: white;
  border-radius: 8px;
  padding: 48px 24px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}
</style>
