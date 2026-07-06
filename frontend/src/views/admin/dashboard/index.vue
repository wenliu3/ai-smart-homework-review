<template>
  <div class="admin-dashboard">
    <!-- 超级管理员控制台 -->
    <div class="dashboard-header">
      <h1 class="dashboard-title">
        <el-icon class="title-icon"><Setting /></el-icon>
        超级管理员控制台
      </h1>
      <p class="dashboard-subtitle">系统管理与监控中心</p>
    </div>

    <!-- 统计卡片区域 -->
    <el-row :gutter="20" class="stats-cards">
      <el-col :xs="24" :sm="12" :md="6">
        <el-card class="stat-card" shadow="hover">
          <div class="stat-content">
            <div class="stat-icon">
              <el-icon><User /></el-icon>
            </div>
            <div class="stat-info">
              <h3>用户总数</h3>
              <p class="stat-number">1,234</p>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :xs="24" :sm="12" :md="6">
        <el-card class="stat-card" shadow="hover">
          <div class="stat-content">
            <div class="stat-icon">
              <el-icon><Document /></el-icon>
            </div>
            <div class="stat-info">
              <h3>作业总数</h3>
              <p class="stat-number">5,678</p>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :xs="24" :sm="12" :md="6">
        <el-card class="stat-card" shadow="hover">
          <div class="stat-content">
            <div class="stat-icon">
              <el-icon><Monitor /></el-icon>
            </div>
            <div class="stat-info">
              <h3>AI模型</h3>
              <p class="stat-number">3</p>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :xs="24" :sm="12" :md="6">
        <el-card class="stat-card" shadow="hover">
          <div class="stat-content">
            <div class="stat-icon">
              <el-icon><Connection /></el-icon>
            </div>
            <div class="stat-info">
              <h3>系统状态</h3>
              <p class="stat-status">正常运行</p>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 功能快捷入口 -->
    <el-row :gutter="20" class="quick-actions">
      <el-col :xs="24" :md="12">
        <el-card class="action-card" shadow="hover">
          <template #header>
            <h3>
              <el-icon><UserFilled /></el-icon> 用户管理
            </h3>
          </template>
          <div class="action-content">
            <p>管理系统用户、角色和权限</p>
            <el-button
              type="primary"
              @click="handleNavigation('/system/users')"
            >
              进入管理
            </el-button>
          </div>
        </el-card>
      </el-col>

      <el-col :xs="24" :md="12">
        <el-card class="action-card" shadow="hover">
          <template #header>
            <h3>
              <el-icon><Setting /></el-icon> 系统设置
            </h3>
          </template>
          <div class="action-content">
            <p>配置AI模型、系统参数等</p>
            <el-button
              type="primary"
              @click="handleNavigation('/system/ai_model')"
            >
              进入设置
            </el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 系统监控区域 -->
    <el-row :gutter="20" class="monitoring-section">
      <el-col :span="24">
        <el-card shadow="hover">
          <template #header>
            <h3>
              <el-icon><Monitor /></el-icon> 系统监控
            </h3>
          </template>
          <div class="monitoring-content">
            <el-alert
              title="系统运行正常"
              type="success"
              :closable="false"
              show-icon
            />
            <div class="monitoring-items">
              <div class="monitoring-item">
                <span>服务器状态</span>
                <el-tag type="success">在线</el-tag>
              </div>
              <div class="monitoring-item">
                <span>数据库连接</span>
                <el-tag type="success">正常</el-tag>
              </div>
              <div class="monitoring-item">
                <span>AI服务</span>
                <el-tag type="success">运行中</el-tag>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from "vue-router";
import {
  Setting,
  User,
  Document,
  Monitor,
  Connection,
  UserFilled,
} from "@element-plus/icons-vue";

const router = useRouter();

// 导航处理
const handleNavigation = (path: string) => {
  router.push(path);
};
</script>

<style scoped>
.admin-dashboard {
  padding: 20px;
  min-height: 100vh;
  background: #f5f7fa;
}

.dashboard-header {
  margin-bottom: 30px;
  text-align: center;
}

.dashboard-title {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  font-size: 28px;
  color: #409eff;
  margin: 0 0 10px 0;
}

.title-icon {
  font-size: 32px;
}

.dashboard-subtitle {
  color: #606266;
  font-size: 16px;
  margin: 0;
}

.stats-cards {
  margin-bottom: 30px;
}

.stat-card {
  height: 120px;
}

.stat-content {
  display: flex;
  align-items: center;
  gap: 15px;
  height: 100%;
}

.stat-icon {
  font-size: 36px;
  color: #409eff;
  background: #ecf5ff;
  width: 60px;
  height: 60px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.stat-info h3 {
  margin: 0 0 8px 0;
  font-size: 14px;
  color: #606266;
}

.stat-number {
  margin: 0;
  font-size: 24px;
  font-weight: bold;
  color: #409eff;
}

.stat-status {
  margin: 0;
  font-size: 16px;
  font-weight: bold;
  color: #67c23a;
}

.quick-actions {
  margin-bottom: 30px;
}

.action-card {
  height: 150px;
}

.action-content {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  height: 80px;
}

.action-content p {
  margin: 0;
  color: #606266;
}

.monitoring-section {
  margin-bottom: 20px;
}

.monitoring-content {
  padding: 10px 0;
}

.monitoring-items {
  margin-top: 20px;
}

.monitoring-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 0;
  border-bottom: 1px solid #ebeef5;
}

.monitoring-item:last-child {
  border-bottom: none;
}

@media (max-width: 768px) {
  .dashboard-title {
    font-size: 24px;
  }

  .stats-cards {
    margin-bottom: 20px;
  }

  .quick-actions {
    margin-bottom: 20px;
  }
}
</style>
