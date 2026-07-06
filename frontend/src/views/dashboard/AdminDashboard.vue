<template>
  <div class="admin-dashboard">
    <!-- 页面头部 -->
    <div class="dashboard-header">
      <div class="header-content">
        <h1 class="dashboard-title">⚡ {{ userName }}的系统控制台</h1>
        <div class="header-actions">
          <el-button
            type="primary"
            :icon="UserFilled"
            @click="manageUsers"
            size="default"
          >
            用户管理
          </el-button>
          <el-button :icon="Setting" @click="systemSettings" size="default">
            大模型设置
          </el-button>
          <el-button
            :icon="Refresh"
            @click="refreshData"
            :loading="isRefreshing"
            size="default"
          >
            刷新
          </el-button>
        </div>
      </div>
    </div>

    <!-- 系统概览统计卡片 -->
    <div class="stats-grid">
      <StatCard
        title="总用户数"
        :value="adminStats?.totalUsers || 0"
        unit="人"
        subtitle="注册用户"
        icon="user"
        variant="primary"
        :loading="loading"
        :trend="userTrend"
        :trend-value="userTrendValue"
      />
      <StatCard
        title="总班级数"
        :value="adminStats?.totalClasses || 0"
        unit="个"
        subtitle="活跃班级"
        icon="school"
        variant="success"
        :loading="loading"
      />
      <StatCard
        title="总作业数"
        :value="adminStats?.totalAssignments || 0"
        unit="个"
        subtitle="已发布"
        icon="document"
        variant="info"
        :loading="loading"
      />
      <StatCard
        title="总提交数"
        :value="adminStats?.totalSubmissions || 0"
        unit="份"
        subtitle="学生提交"
        icon="list"
        variant="warning"
        :loading="loading"
      />
      <StatCard
        title="AI模型数"
        :value="adminStats?.aiModelCount || 0"
        unit="个"
        subtitle="可用模型"
        icon="robot"
        variant="danger"
        :loading="loading"
      />
    </div>

    <!-- AI模型状态监控 -->
    <div class="ai-models-section">
      <div class="section-header">
        <h2 class="section-title">🤖 AI模型状态监控</h2>
        <div class="model-status-summary">
          <el-tag :type="allModelsOnline ? 'success' : 'warning'" size="small">
            {{ allModelsOnline ? "✅ 所有模型正常" : "⚠️ 部分模型异常" }}
          </el-tag>
        </div>
      </div>

      <div class="ai-models-grid">
        <!-- DeepSeek 模型卡片 -->
        <div class="ai-model-card" v-if="aiModelStats?.deepseek">
          <div class="model-header">
            <div class="model-info">
              <h3 class="model-name">🧠 DeepSeek</h3>
              <el-tag
                :type="aiModelStats.deepseek.isOnline ? 'success' : 'danger'"
                size="small"
              >
                {{ aiModelStats.deepseek.isOnline ? "在线" : "离线" }}
              </el-tag>
            </div>
            <div class="model-balance">
              <span class="balance-label">余额</span>
              <span class="balance-value"
                >{{ aiModelStats.deepseek.balance
                }}{{ aiModelStats.deepseek.balanceCurrency || "" }}</span
              >
            </div>
          </div>
          <div class="model-stats">
            <div class="stat-item">
              <div class="stat-label">今日使用</div>
              <div class="stat-value">
                {{ aiModelStats.deepseek.todayUsage }}次
              </div>
            </div>
            <div class="stat-item">
              <div class="stat-label">总使用量</div>
              <div class="stat-value">
                {{ formatNumber(aiModelStats.deepseek.totalUsage) }}次
              </div>
            </div>
            <div class="stat-item">
              <div class="stat-label">总Token</div>
              <div class="stat-value">
                {{ formatNumber(aiModelStats.deepseek.totalTokens) }}
              </div>
            </div>
          </div>
        </div>

        <!-- 小米模型卡片 -->
        <div class="ai-model-card" v-if="aiModelStats?.mimo">
          <div class="model-header">
            <div class="model-info">
              <h3 class="model-name">📱 小米</h3>
              <el-tag
                :type="aiModelStats.mimo.isOnline ? 'success' : 'danger'"
                size="small"
              >
                {{ aiModelStats.mimo.isOnline ? "在线" : "离线" }}
              </el-tag>
            </div>
            <div class="model-balance">
              <span class="balance-label">余额</span>
              <span class="balance-value"
                >{{ aiModelStats.mimo.balance }}次</span
              >
            </div>
          </div>
          <div class="model-stats">
            <div class="stat-item">
              <div class="stat-label">今日使用</div>
              <div class="stat-value">
                {{ aiModelStats.mimo.todayUsage }}次
              </div>
            </div>
            <div class="stat-item">
              <div class="stat-label">总使用量</div>
              <div class="stat-value">
                {{ formatNumber(aiModelStats.mimo.totalUsage) }}次
              </div>
            </div>
            <div class="stat-item">
              <div class="stat-label">总Token</div>
              <div class="stat-value">
                {{ formatNumber(aiModelStats.mimo.totalTokens) }}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 统计图表区域 - 三个图表一行 -->
    <div class="charts-grid-three">
      <!-- 用户角色分布 -->
      <div class="chart-card">
        <div class="chart-header">
          <h3 class="chart-title">👥 用户角色分布</h3>
          <div class="chart-subtitle">
            总计: {{ adminStats?.totalUsers || 0 }}人
          </div>
        </div>
        <DonutChart :data="userRoleData" :height="240" :loading="loading" />
      </div>

      <!-- 班级状态分布 -->
      <div class="chart-card">
        <div class="chart-header">
          <h3 class="chart-title">🏫 班级状态分布</h3>
        </div>
        <DonutChart :data="classStatusData" :height="240" :loading="loading" />
      </div>

      <!-- 提交状态统计 -->
      <div class="chart-card">
        <div class="chart-header">
          <h3 class="chart-title">📊 提交状态统计</h3>
          <div class="chart-subtitle">系统整体提交情况</div>
        </div>
        <BarChart
          :data="submissionStatusData"
          :height="240"
          :loading="loading"
          unit="份"
          :show-value="true"
        />
      </div>
    </div>

    <!-- 用户注册和系统状态区域 - 两个模块一行 -->
    <div class="tables-grid-two">
      <!-- 最新用户注册 -->
      <div class="table-card">
        <div class="table-header">
          <h3 class="table-title">👤 最新用户注册</h3>
          <el-button type="primary" size="small" @click="viewAllUsers">
            查看全部
          </el-button>
        </div>
        <el-table
          :data="recentUsers"
          style="width: 100%"
          :loading="loading"
          empty-text="暂无新用户注册"
          table-layout="fixed"
        >
          <el-table-column
            prop="name"
            label="姓名"
            width="80"
            show-overflow-tooltip
          />
          <el-table-column
            prop="email"
            label="邮箱"
            min-width="120"
            show-overflow-tooltip
          />
          <el-table-column prop="role" label="角色" width="70">
            <template #default="{ row }">
              <el-tag :type="getRoleTagType(row.role)" size="small">
                {{ getRoleText(row.role) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="60">
            <template #default="{ row }">
              <el-tag
                :type="row.status === 'active' ? 'success' : 'warning'"
                size="small"
              >
                {{ row.status === "active" ? "激活" : "待激活" }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column
            prop="createdAt"
            label="注册时间"
            width="80"
            show-overflow-tooltip
          >
            <template #default="{ row }">
              {{ formatRelativeTime(row.createdAt) }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="60" fixed="right">
            <template #default="{ row }">
              <el-button type="primary" size="small" @click="viewUser(row.id)">
                查看
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <!-- 系统健康状态 -->
      <div class="table-card">
        <div class="table-header">
          <h3 class="table-title">💓 系统健康状态</h3>
          <div class="health-indicator">
            <div class="health-dot healthy"></div>
            <span>系统运行正常</span>
          </div>
        </div>

        <div class="health-metrics">
          <div class="metric-item">
            <div class="metric-icon">🚀</div>
            <div class="metric-content">
              <div class="metric-label">系统负载</div>
              <div class="metric-value">正常</div>
            </div>
          </div>
          <div class="metric-item">
            <div class="metric-icon">💾</div>
            <div class="metric-content">
              <div class="metric-label">数据库</div>
              <div class="metric-value">连接正常</div>
            </div>
          </div>
          <div class="metric-item">
            <div class="metric-icon">🔄</div>
            <div class="metric-content">
              <div class="metric-label">缓存服务</div>
              <div class="metric-value">运行正常</div>
            </div>
          </div>
          <div class="metric-item">
            <div class="metric-icon">📡</div>
            <div class="metric-content">
              <div class="metric-label">API响应</div>
              <div class="metric-value">&lt; 100ms</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { useStore } from "vuex";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { Refresh, UserFilled, Setting } from "@element-plus/icons-vue";
import StatCard from "./components/StatCard.vue";
import DonutChart from "./components/charts/DonutChart.vue";
import BarChart from "./components/charts/BarChart.vue";
import { formatRelativeTime } from "@/utils/date";
import { getRecentUsers } from "@/api/dashboard";

const store = useStore();
const router = useRouter();

// 响应式数据
const isRefreshing = ref(false);
const recentUsers = ref<any[]>([]);

// 计算属性
const loading = computed(() => store.getters["dashboard/isLoading"]("admin"));
const adminStats = computed(() => store.getters["dashboard/adminOverview"]);
const aiModelStats = computed(() => store.getters["dashboard/aiModelStats"]);
const userName = computed(() => store.getters["user/userName"] || "管理员");

// 用户角色分布数据转换
const userRoleData = computed(() => {
  if (!adminStats.value?.userRoleDistribution) return [];

  const roleMap: Record<string, { name: string; color: string }> = {
    SUPER_ADMIN: { name: "超级管理员", color: "#FF3B30" },
    TEACHER: { name: "教师", color: "#007AFF" },
    STUDENT: { name: "学生", color: "#34C759" },
  };

  return adminStats.value.userRoleDistribution.map((item) => ({
    name: roleMap[item.role]?.name || item.role,
    value: item.count,
    color: roleMap[item.role]?.color,
  }));
});

// 班级状态分布数据转换
const classStatusData = computed(() => {
  if (!adminStats.value?.classStatusDistribution) return [];

  const statusMap: Record<string, { name: string; color: string }> = {
    active: { name: "活跃", color: "#34C759" },
    inactive: { name: "非活跃", color: "#8E8E93" },
    disbanded: { name: "已解散", color: "#FF3B30" },
  };

  return adminStats.value.classStatusDistribution.map((item) => ({
    name: statusMap[item.status]?.name || item.status,
    value: item.count,
    color: statusMap[item.status]?.color,
  }));
});

// 提交状态分布数据转换
const submissionStatusData = computed(() => {
  if (!adminStats.value?.submissionStatusDistribution) return [];

  const statusMap: Record<string, { name: string; color: string }> = {
    draft: { name: "草稿", color: "#8E8E93" },
    submitted: { name: "已提交", color: "#007AFF" },
    ai_reviewed: { name: "AI批改", color: "#FF9F0A" },
    teacher_reviewed: { name: "教师批改", color: "#34C759" },
  };

  return adminStats.value.submissionStatusDistribution.map((item) => ({
    name: statusMap[item.status]?.name || item.status,
    value: item.count,
    color: statusMap[item.status]?.color,
  }));
});

// AI模型在线状态
const allModelsOnline = computed(() => {
  if (!aiModelStats.value) return false;

  const models = Object.values(aiModelStats.value);
  return models.length > 0 && models.every((model: any) => model?.isOnline);
});

// 用户趋势（模拟数据）
const userTrend = computed(() => "up");
const userTrendValue = computed(() => 15);

// 方法
const refreshData = async () => {
  isRefreshing.value = true;
  try {
    await Promise.all([
      store.dispatch("dashboard/fetchAdminDashboard", true),
      store.dispatch("dashboard/fetchAiModelStats", true),
      loadRecentUsers(),
    ]);
    ElMessage.success("数据刷新成功");
  } catch (error) {
    ElMessage.error("数据刷新失败");
  } finally {
    isRefreshing.value = false;
  }
};

const loadRecentUsers = async () => {
  try {
    const response = await getRecentUsers(5);
    recentUsers.value = response.users || [];

    console.log("最近用户数据:", response); // 调试日志
  } catch (error) {
    console.error("加载最新用户失败:", error);
    recentUsers.value = [];
  }
};

const manageUsers = () => {
  router.push("/system/users");
};

const systemSettings = () => {
  router.push("/system/ai_model");
};

const viewAllUsers = () => {
  router.push("/system/users");
};

const viewUser = (userId: string) => {
  router.push(`/system/users/${userId}`);
};

const formatNumber = (num: number) => {
  if (num >= 10000) {
    return (num / 10000).toFixed(1) + "万";
  } else if (num >= 1000) {
    return (num / 1000).toFixed(1) + "k";
  }
  return num.toString();
};

const getRoleTagType = (role: string) => {
  const typeMap: Record<
    string,
    "success" | "warning" | "info" | "primary" | "danger"
  > = {
    SUPER_ADMIN: "danger",
    TEACHER: "primary",
    STUDENT: "success",
  };
  return typeMap[role] || "info";
};

const getRoleText = (role: string) => {
  const textMap: Record<string, string> = {
    SUPER_ADMIN: "超级管理员",
    TEACHER: "教师",
    STUDENT: "学生",
  };
  return textMap[role] || role;
};

// 生命周期
onMounted(async () => {
  try {
    await Promise.all([
      store.dispatch("dashboard/fetchAdminDashboard"),
      store.dispatch("dashboard/fetchAiModelStats"),
      loadRecentUsers(),
    ]);
  } catch (error) {
    ElMessage.error("加载看板数据失败");
  }
});
</script>

<style scoped>
.admin-dashboard {
  padding: 24px;
  background: #f8f9fa;
  overflow-x: hidden; /* 防止页面级别的水平滚动 */
}

.dashboard-header {
  margin-bottom: 24px;
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 16px;
}

.dashboard-title {
  font-size: 24px;
  font-weight: 600;
  color: #1d1d1f;
  margin: 0;
}

.header-actions {
  display: flex;
  gap: 12px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}

.ai-models-section {
  margin-bottom: 24px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.section-title {
  font-size: 18px;
  font-weight: 600;
  color: #1d1d1f;
  margin: 0;
}

.model-status-summary {
  display: flex;
  align-items: center;
  gap: 8px;
}

.ai-models-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.ai-model-card {
  background: #ffffff;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  border: 1px solid #f0f0f0;
}

.model-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
}

.model-info {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.model-name {
  font-size: 16px;
  font-weight: 600;
  color: #1d1d1f;
  margin: 0;
}

.model-balance {
  text-align: right;
}

.balance-label {
  display: block;
  font-size: 12px;
  color: #666;
  margin-bottom: 4px;
}

.balance-value {
  font-size: 18px;
  font-weight: 600;
  color: #1d1d1f;
}

.model-stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.stat-item {
  text-align: center;
  padding: 12px;
  background: #f8f9fa;
  border-radius: 8px;
}

.stat-label {
  font-size: 11px;
  color: #666;
  margin-bottom: 4px;
}

.stat-value {
  font-size: 14px;
  font-weight: 600;
  color: #1d1d1f;
}

.charts-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}

.charts-grid-three {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}

.tables-grid-two {
  display: grid;
  grid-template-columns: 1.3fr 1fr;
  gap: 16px;
  margin-bottom: 24px;
  align-items: stretch;
}

.table-card {
  background: #ffffff;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  border: 1px solid #f0f0f0;
  overflow: hidden;
  min-width: 0;
}

.table-card :deep(.el-table) {
  overflow: hidden;
}

.table-card :deep(.el-table__body-wrapper) {
  overflow-x: auto;
}

.table-card :deep(.el-table__header-wrapper) {
  overflow-x: hidden;
}

.table-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.table-title {
  font-size: 16px;
  font-weight: 600;
  color: #1d1d1f;
  margin: 0;
}

.chart-card {
  background: #ffffff;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  border: 1px solid #f0f0f0;
  overflow: hidden; /* 防止内容溢出 */
  min-width: 0; /* 允许flex子元素收缩 */
}

.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.chart-title {
  font-size: 16px;
  font-weight: 600;
  color: #1d1d1f;
  margin: 0;
}

.chart-subtitle {
  font-size: 14px;
  color: #666;
}

.health-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: #34c759;
}

.health-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.health-dot.healthy {
  background: #34c759;
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
  100% {
    opacity: 1;
  }
}

.health-metrics {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
  background: #ffffff;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  border: 1px solid #f0f0f0;
  flex: 1;
  width: 100%;
  box-sizing: border-box;
}

.metric-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  background: #f8f9fa;
  border-radius: 8px;
  min-height: 60px;
  transition: all 0.3s ease;
  width: 100%;
  box-sizing: border-box;
}

.metric-item:hover {
  background: #e9ecef;
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.metric-icon {
  font-size: 32px;
  min-width: 40px;
}

.metric-content {
  flex: 1;
}

.metric-label {
  font-size: 14px;
  color: #666;
  margin-bottom: 6px;
  font-weight: 500;
}

.metric-value {
  font-size: 16px;
  font-weight: 600;
  color: #34c759;
  line-height: 1.2;
}

/* 响应式设计 */

/* 中等屏幕 - 平板横屏 */
@media (max-width: 1200px) {
  .stats-grid {
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
  }

  .ai-models-grid {
    grid-template-columns: 1fr;
    gap: 16px;
  }

  .charts-grid {
    grid-template-columns: 1fr;
    gap: 16px;
  }

  .charts-grid-three {
    grid-template-columns: repeat(2, 1fr);
    gap: 16px;
  }
}

/* 平板和小屏幕笔记本 */
@media (max-width: 1024px) {
  .tables-grid-two {
    grid-template-columns: 1fr;
    gap: 16px;
  }

  .charts-grid-three {
    grid-template-columns: 1fr;
    gap: 16px;
  }

  .ai-models-grid {
    grid-template-columns: 1fr;
    gap: 16px;
  }
}

/* 手机和小平板 */
@media (max-width: 768px) {
  .admin-dashboard {
    padding: 16px;
  }

  .dashboard-title {
    font-size: 20px;
  }

  .header-content {
    flex-direction: column;
    align-items: flex-start;
  }

  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
    gap: 12px;
  }

  .ai-models-grid {
    grid-template-columns: 1fr;
  }

  .charts-grid {
    grid-template-columns: 1fr;
    gap: 12px;
  }

  .charts-grid-three {
    grid-template-columns: 1fr;
    gap: 12px;
  }

  .tables-grid-two {
    grid-template-columns: 1fr;
    gap: 12px;
  }

  .health-metrics {
    grid-template-columns: 1fr;
  }

  .metric-item {
    min-height: 50px;
    padding: 12px;
  }

  .metric-icon {
    font-size: 24px;
  }

  .metric-label {
    font-size: 12px;
  }

  .metric-value {
    font-size: 14px;
  }

  .model-stats {
    grid-template-columns: 1fr;
  }

  /* 表格在中等屏幕上的优化 */
  .table-card :deep(.el-table__cell) {
    padding: 10px 6px;
  }

  .table-card :deep(.el-table) {
    font-size: 13px;
  }
}

/* 小屏手机 */
@media (max-width: 480px) {
  .admin-dashboard {
    padding: 12px;
  }

  .dashboard-title {
    font-size: 18px;
  }

  .header-actions {
    flex-direction: column;
    width: 100%;
    gap: 8px;
  }

  .header-actions .el-button {
    width: 100%;
  }

  .stats-grid {
    grid-template-columns: 1fr;
    gap: 8px;
  }

  .table-card,
  .health-metrics {
    padding: 12px;
  }

  /* 表格在小屏幕上的优化 */
  .table-card :deep(.el-table__cell) {
    padding: 8px 4px;
  }

  .table-card :deep(.el-table) {
    font-size: 12px;
  }

  .table-card :deep(.el-button) {
    padding: 4px 8px;
    font-size: 11px;
  }

  .metric-item {
    padding: 8px;
    min-height: 40px;
  }

  .metric-icon {
    font-size: 20px;
    min-width: 32px;
  }

  .metric-label {
    font-size: 11px;
  }

  .metric-value {
    font-size: 12px;
  }
}
</style>
