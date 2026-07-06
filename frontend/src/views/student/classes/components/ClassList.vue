<template>
  <div class="w-[320px] bg-white border-r border-gray-200 flex flex-col">
    <!-- 标题区域 -->
    <div class="p-4 border-b border-gray-100">
      <div class="flex items-center justify-between">
        <div>
          <h1 class="text-lg font-semibold text-gray-900 mb-1">我的班级</h1>
          <p class="text-xs text-gray-500">管理您参与的所有班级和作业</p>
        </div>
        <!-- 加入班级图标按钮 -->
        <el-tooltip content="加入班级" placement="bottom">
          <el-button
            type="primary"
            :icon="Plus"
            @click="handleJoinClass"
            circle
            size="default"
          />
        </el-tooltip>
      </div>
    </div>

    <!-- 搜索框 -->
    <div class="p-4 border-b border-gray-100">
      <div class="flex items-center space-x-2">
        <el-input
          v-model="searchKeyword"
          placeholder="搜索班级..."
          clearable
          size="default"
          @keyup.enter="handleSearch"
          @clear="handleClearSearch"
          class="flex-1"
        />
        <el-button
          :icon="Search"
          @click="handleSearch"
          size="default"
          :loading="searchLoading"
        />
      </div>
    </div>

    <!-- 班级列表区域 -->
    <div class="flex-1 overflow-y-auto">
      <!-- 加载状态 -->
      <div v-if="classLoading" class="p-4">
        <el-skeleton v-for="i in 4" :key="i" animated class="mb-4">
          <template #template>
            <div class="h-20 bg-gray-100 rounded-lg"></div>
          </template>
        </el-skeleton>
      </div>

      <!-- 空状态 -->
      <div v-else-if="classes.length === 0" class="p-4">
        <el-empty description="暂无班级" :image-size="80">
          <el-button type="primary" @click="handleJoinClass">
            加入班级
          </el-button>
        </el-empty>
      </div>

      <!-- 班级卡片列表 -->
      <div v-else class="p-4">
        <div class="space-y-3">
          <el-card
            v-for="classItem in classes"
            :key="classItem._id"
            :class="[
              'cursor-pointer transition-all duration-200',
              selectedClassId === classItem._id
                ? 'border-blue-400 shadow-md'
                : 'hover:border-blue-300 hover:shadow-sm',
            ]"
            :body-style="{ padding: '16px' }"
            @click="handleSelectClass(classItem)"
          >
            <!-- 班级名称和状态 -->
            <div class="flex items-center justify-between mb-2">
              <h3
                class="font-medium text-gray-900 text-sm truncate flex-1 mr-2"
              >
                {{ classItem.name }}
              </h3>
              <el-tag
                :type="getClassStatusType(classItem.status)"
                size="small"
                effect="light"
              >
                {{ getClassStatusText(classItem.status) }}
              </el-tag>
            </div>

            <!-- 班级信息 -->
            <div class="text-xs text-gray-500 space-y-1">
              <div class="flex items-center justify-between">
                <div class="flex items-center">
                  <el-icon class="mr-1"><User /></el-icon>
                  <span>{{ classItem.teacherName || "未知教师" }}</span>
                </div>
                <div class="flex items-center">
                  <el-icon class="mr-1"><UserFilled /></el-icon>
                  <span>{{ classItem.studentCount || 0 }}人</span>
                </div>
              </div>
            </div>

            <!-- 选中指示器 -->
            <div
              v-if="selectedClassId === classItem._id"
              class="absolute left-0 top-0 w-1 h-full bg-blue-500 rounded-r"
            ></div>
          </el-card>
        </div>

        <!-- 底部操作区 -->
        <div class="pt-4 mt-4 border-t border-gray-100">
          <!-- 加载更多 -->
          <div
            v-if="!pageState.isAllLoaded && classes.length > 0"
            class="text-center"
          >
            <el-button
              type="primary"
              text
              size="small"
              @click="loadMore"
              :loading="loadingMore"
            >
              {{ loadingMore ? "加载中..." : "加载更多" }}
            </el-button>
          </div>

          <!-- 加载完成提示 -->
          <div
            v-else-if="pageState.isAllLoaded && classes.length > 0"
            class="text-center"
          >
            <span class="text-gray-400 text-xs">已显示全部班级</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, inject, onMounted, nextTick, type Ref } from "vue";
import { ElMessage } from "element-plus";
import { Plus, Search, User, UserFilled } from "@element-plus/icons-vue";
import { getClassList } from "../../../../api/classes";
import { useClassManagement } from "../composables/useClassManagement";

// 通过 inject 获取共享状态
const selectedClassId = inject<Ref<string | null>>("selectedClassId")!;
const setSelectedClass = inject<(classItem: any) => void>("setSelectedClass")!;
const showJoinDialog = inject<Ref<boolean>>("showJoinDialog")!;

// 组件内部状态
const classLoading = ref(true);
const loadingMore = ref(false);
const searchLoading = ref(false);
const classes = ref([]);
const searchKeyword = ref("");
const pageState = reactive({
  page: 1,
  limit: 10,
  total: 0,
  isAllLoaded: false,
});

// 使用组合函数
const { getClassStatusType, getClassStatusText } = useClassManagement();

// 加载班级列表
const loadClasses = async (type: string = "initData", search?: string) => {
  if (type === "initData") {
    classLoading.value = true;
    pageState.page = 1;
    pageState.isAllLoaded = false;
  } else {
    loadingMore.value = true;
  }

  try {
    const params: any = {
      page: pageState.page,
      limit: pageState.limit,
    };

    if (search) {
      params.search = search;
    }

    const response = await getClassList(params);
    const { items, total } = response;
    pageState.total = total;

    if (type !== "loadMore") {
      classes.value = items || [];
    } else {
      classes.value = classes.value.concat(items) || [];
    }

    if (classes.value.length >= total) {
      pageState.isAllLoaded = true;
    } else {
      pageState.page++;
    }

    // 如果有班级且没有选中的班级，默认选中第一个
    if (classes.value.length > 0 && !selectedClassId.value) {
      handleSelectClass(classes.value[0]);
    }
  } catch (error) {
    ElMessage.error("加载班级列表失败");
  } finally {
    classLoading.value = false;
    loadingMore.value = false;
    searchLoading.value = false;

    if (type !== "loadMore") return;

    nextTick(() => {
      const scrollContainer = document.querySelector(
        ".w-\\[320px\\] .flex-1.overflow-y-auto"
      );
      if (scrollContainer) {
        scrollContainer.scrollTo({
          top: scrollContainer.scrollHeight,
          behavior: "smooth",
        });
      }
    });
  }
};

// 搜索处理
const handleSearch = async () => {
  if (searchLoading.value) return;

  searchLoading.value = true;
  try {
    await loadClasses("initData", searchKeyword.value.trim());
  } catch (error) {
    ElMessage.error("搜索失败");
  }
};

// 清空搜索
const handleClearSearch = async () => {
  searchKeyword.value = "";
  await loadClasses("initData");
};

// 加载更多
const loadMore = () => {
  loadClasses("loadMore", searchKeyword.value.trim());
};

// 选择班级
const handleSelectClass = (classItem) => {
  setSelectedClass(classItem);
};

// 加入班级
const handleJoinClass = () => {
  showJoinDialog.value = true;
};

// 刷新班级列表（暴露给父组件）
const refresh = () => {
  loadClasses("initData", searchKeyword.value.trim());
};

// 暴露方法给父组件
defineExpose({
  refresh,
});

// 初始化
onMounted(() => {
  loadClasses();
});
</script>

<style scoped>
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

:deep(.el-card) {
  position: relative;
}
</style>
