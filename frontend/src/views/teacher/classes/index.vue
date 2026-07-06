<template>
  <div class="classes-management">
    <!-- 页面头部 -->
    <page-header title="班级管理" description="管理您的班级，查看学生信息">
      <template #actions>
        <el-button
          type="primary"
          :icon="Plus"
          @click="handleCreateClass"
          size="default"
        >
          创建班级
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
    <div class="classes-container" ref="containerRef">
      <!-- 搜索和筛选区域 -->
      <div class="search-section" ref="searchRef">
        <el-form :inline="true" :model="searchForm" class="search-form">
          <div class="search-row">
            <el-form-item label="班级名称">
              <el-input
                v-model="searchForm.search"
                placeholder="搜索班级名称"
                :prefix-icon="Search"
                clearable
                style="width: 200px"
                @keyup.enter="handleSearch"
              />
            </el-form-item>

            <el-form-item label="状态">
              <el-select
                v-model="searchForm.status"
                placeholder="选择状态"
                clearable
                style="width: 120px"
              >
                <el-option label="活跃" value="active" />
                <el-option label="暂停" value="inactive" />
                <el-option label="已解散" value="disbanded" />
              </el-select>
            </el-form-item>

            <el-form-item>
              <el-button type="primary" :icon="Search" @click="handleSearch">
                搜索
              </el-button>
              <el-button @click="resetSearch">重置</el-button>
            </el-form-item>

            <!-- 布局切换 -->
            <el-form-item class="ml-auto">
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
            </el-form-item>
          </div>
        </el-form>
      </div>

      <!-- 班级列表内容区域 -->
      <div
        class="content-section"
        ref="contentRef"
        :style="{ height: contentHeight }"
        v-loading="loading"
        element-loading-text="加载中..."
      >
        <!-- 空状态 -->
        <div v-if="classList.length === 0" class="empty-state">
          <div class="empty-icon">📚</div>
          <h3 class="empty-title">暂无班级</h3>
          <p class="empty-desc">点击"创建班级"按钮开始管理您的第一个班级</p>
          <el-button
            type="primary"
            :icon="Plus"
            @click="handleCreateClass"
            class="empty-action"
          >
            创建班级
          </el-button>
        </div>

        <!-- 网格模式 -->
        <div v-else-if="viewMode === 'grid'" class="classes-grid">
          <class-card
            v-for="classItem in classList"
            :key="classItem._id"
            :class-data="classItem"
            view-mode="grid"
            @view="handleViewClass"
            @edit="handleEditClass"
            @disband="handleDisbandClass"
            @regenerate-code="handleRegenerateCode"
          />
        </div>

        <!-- 列表模式 -->
        <div v-else class="classes-list">
          <class-card
            v-for="classItem in classList"
            :key="classItem._id"
            :class-data="classItem"
            view-mode="list"
            @view="handleViewClass"
            @edit="handleEditClass"
            @disband="handleDisbandClass"
            @regenerate-code="handleRegenerateCode"
          />
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
          :page-size="pagination.limit"
          :page-sizes="[3, 6, 10, 24, 48, 96]"
          :total="pagination.total"
          background
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        />
      </div>
    </div>

    <!-- 创建/编辑班级对话框 -->
    <create-class-dialog
      v-model="showCreateDialog"
      :class-data="editingClass"
      @success="handleCreateSuccess"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted, nextTick } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import {
  Plus,
  Refresh,
  Search,
  Operation,
  Menu,
} from "@element-plus/icons-vue";
import { useRouter } from "vue-router";
// 使用相对路径导入，避免导入问题
import {
  getClassList,
  disbandClass,
  regenerateClassCode,
} from "../../../api/classes";

// 本地定义类型，避免导入问题
interface Class {
  _id: string;
  name: string;
  code: string;
  teacherId: string;
  teacherName?: string;
  status: "active" | "inactive" | "disbanded";
  studentCount: number;
  description?: string;
  createdAt: string;
  updatedAt: string;
}

interface ClassQueryParams {
  page?: number;
  limit?: number;
  status?: "active" | "inactive" | "disbanded";
  search?: string;
}

// 导入组件
import PageHeader from "@/components/PageHeader.vue";
import ClassCard from "./components/ClassCard.vue";
import CreateClassDialog from "./components/CreateClassDialog.vue";

const router = useRouter();

// 数据状态
const loading = ref(false);
const classList = ref<Class[]>([]);
const showCreateDialog = ref(false);
const editingClass = ref<Class | null>(null);

// 自适应高度相关
const containerRef = ref<HTMLElement>();
const searchRef = ref<HTMLElement>();
const contentRef = ref<HTMLElement>();
const paginationRef = ref<HTMLElement>();
const contentHeight = ref("400px");

// 搜索表单（移除排序相关字段）
const searchForm = reactive<ClassQueryParams>({
  search: "",
  status: undefined,
});

// 分页数据
const pagination = reactive({
  page: 1,
  limit: 10,
  total: 0,
});

// 布局模式
const viewMode = ref<"grid" | "list">("grid");

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

    console.log("🔍 班级管理页面高度计算:", {
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
  let timeout: NodeJS.Timeout | null = null;
  return (...args: any[]) => {
    if (timeout) clearTimeout(timeout);
    timeout = setTimeout(() => func.apply(null, args), wait);
  };
};

const debouncedCalculate = debounce(calculateContentHeight, 100);

const handleResize = () => {
  debouncedCalculate();
};

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
    console.log(response, "---response");

    classList.value = response.items;
    pagination.total = response.total;

    // 重新计算高度
    nextTick(() => {
      setTimeout(() => {
        calculateContentHeight();
      }, 50);
    });
  } catch (error) {
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

// 重置搜索（移除排序相关字段）
const resetSearch = () => {
  Object.assign(searchForm, {
    search: "",
    status: undefined,
  });
  pagination.page = 1;
  loadClassList();
};

// 刷新数据
const refreshData = () => {
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

// 班级操作
const handleCreateClass = () => {
  editingClass.value = null;
  showCreateDialog.value = true;
};

const handleViewClass = (classData: Class) => {
  router.push({
    path: "/teacher/classes/detail",
    query: { id: classData._id },
  });
};

const handleEditClass = (classData: Class) => {
  editingClass.value = classData;
  showCreateDialog.value = true;
};

const handleDisbandClass = async (classData: Class) => {
  try {
    await ElMessageBox.confirm(
      `确定要解散班级"${classData.name}"吗？此操作不可撤销。`,
      "确认解散",
      {
        confirmButtonText: "确定",
        cancelButtonText: "取消",
        type: "warning",
      }
    );

    const response = await disbandClass(classData._id);
    ElMessage.success("班级已成功解散");
    loadClassList();
  } catch (error) {
    if (error !== "cancel") {
      console.error("解散班级失败:", error);
      // 错误提示已在统一请求层处理，此处不重复弹出
    }
  }
};

const handleRegenerateCode = async (classData: Class) => {
  try {
    await ElMessageBox.confirm(
      `确定要刷新班级"${classData.name}"的邀请码吗？旧的邀请码将失效。`,
      "确认刷新",
      {
        confirmButtonText: "确定",
        cancelButtonText: "取消",
        type: "warning",
      }
    );

    const response = await regenerateClassCode(classData._id);
    ElMessage.success(`新的邀请码：${response.inviteCode}`);
    loadClassList();
  } catch (error) {
    if (error !== "cancel") {
      console.error("刷新邀请码失败:", error);
      // 错误提示已在统一请求层处理，此处不重复弹出
    }
  }
};

const handleCreateSuccess = () => {
  showCreateDialog.value = false;
  editingClass.value = null;
  loadClassList();
};

// 初始化
onMounted(() => {
  loadClassList();
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
.classes-management {
  height: 100%;
  display: flex;
  flex-direction: column;
  background-color: #f8fafc;
}

/* 内容容器 */
.classes-container {
  display: flex;
  flex-direction: column;
  width: 100%;
  margin: 0 auto;
  /* padding: 0 24px; */
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

/* 班级网格 */
.classes-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 20px;
}

/* 班级列表 */
.classes-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
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

/* 响应式设计 */
@media (max-width: 768px) {
  .classes-container {
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

  .classes-grid {
    grid-template-columns: 1fr;
    gap: 16px;
  }
}

/* 优化卡片悬浮效果 */
:deep(.el-card) {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  border: 1px solid #e5e7eb;
}

:deep(.el-card:hover) {
  transform: translateY(-4px);
  box-shadow: 0 12px 24px rgba(0, 0, 0, 0.15);
  border-color: #d1d5db;
}

/* 分页组件样式优化 */
:deep(.el-pagination) {
  font-weight: 500;
}

:deep(.el-pagination .el-pager li.is-active) {
  background: #667eea;
  border-color: #667eea;
}
</style>
