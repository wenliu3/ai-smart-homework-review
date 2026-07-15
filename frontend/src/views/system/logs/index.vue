<!-- 操作日志页面 -->
<template>
  <div class="logs-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>操作日志</span>
          <el-button type="primary" :icon="Refresh" @click="loadData">刷新</el-button>
        </div>
      </template>

      <!-- 筛选栏 -->
      <div class="filter-bar">
        <el-input
          v-model="filterKeyword"
          placeholder="搜索关键词（描述/操作人）"
          clearable
          style="width: 220px"
          @keyup.enter="handleSearch"
        />
        <el-select
          v-model="filterAction"
          placeholder="操作类型"
          clearable
          style="width: 140px"
          @change="handleSearch"
        >
          <el-option label="创建" value="创建" />
          <el-option label="更新" value="更新" />
          <el-option label="删除" value="删除" />
          <el-option label="登录" value="登录" />
          <el-option label="退出" value="退出" />
        </el-select>
        <el-select
          v-model="filterModule"
          placeholder="操作模块"
          clearable
          style="width: 160px"
          @change="handleSearch"
        >
          <el-option label="用户管理" value="用户管理" />
          <el-option label="角色管理" value="角色管理" />
          <el-option label="菜单管理" value="菜单管理" />
          <el-option label="班级管理" value="班级管理" />
          <el-option label="作业管理" value="作业管理" />
          <el-option label="批改管理" value="批改管理" />
          <el-option label="文档查重" value="文档查重" />
          <el-option label="AI模型配置" value="AI模型配置" />
          <el-option label="AI批改规则" value="AI批改规则" />
          <el-option label="登录认证" value="登录认证" />
        </el-select>
        <el-button type="primary" :icon="Search" @click="handleSearch">搜索</el-button>
      </div>

      <el-table :data="tableData" v-loading="loading" stripe style="width: 100%">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="operator" label="操作人" width="120" />
        <el-table-column prop="action" label="操作类型" width="150">
          <template #default="{ row }">
            <el-tag :type="getActionTagType(row.action)">{{ row.action }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="module" label="模块" width="120" />
        <el-table-column prop="description" label="描述" show-overflow-tooltip />
        <el-table-column prop="ip" label="IP地址" width="140" />
        <el-table-column prop="createdAt" label="操作时间" width="180">
          <template #default="{ row }">
            {{ formatDate(row.createdAt) }}
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="loadData"
          @current-change="loadData"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import { Refresh, Search } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";
import { getLogs, type LogItem, type LogQueryParams } from "@/api/logs";

const tableData = ref<LogItem[]>([]);
const loading = ref(false);
const currentPage = ref(1);
const pageSize = ref(20);
const total = ref(0);

// 筛选条件
const filterAction = ref("");
const filterModule = ref("");
const filterKeyword = ref("");

const loadData = async () => {
  loading.value = true;
  try {
    const params: LogQueryParams = {
      page: currentPage.value,
      pageSize: pageSize.value,
    };
    if (filterAction.value) params.action = filterAction.value;
    if (filterModule.value) params.module = filterModule.value;
    if (filterKeyword.value) params.keyword = filterKeyword.value;

    const res = await getLogs(params);
    tableData.value = res.items;
    total.value = res.total;
  } catch (error: any) {
    ElMessage.error(error.message || "加载失败");
  } finally {
    loading.value = false;
  }
};

const handleSearch = () => {
  currentPage.value = 1;
  loadData();
};

const getActionTagType = (action: string) => {
  const map: Record<string, string> = {
    创建: "success",
    更新: "warning",
    删除: "danger",
    登录: "primary",
    退出: "info",
  };
  return map[action] || "info";
};

const formatDate = (date: string) => {
  if (!date) return "";
  return new Date(date).toLocaleString("zh-CN");
};

onMounted(() => {
  loadData();
});
</script>

<style scoped>
.logs-container {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.pagination-wrapper {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

.filter-bar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}
</style>
