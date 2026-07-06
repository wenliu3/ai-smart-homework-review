<template>
  <div class="ai-model-config">
    <!-- 页面标题 -->
    <div class="page-header mb-6">
      <div class="header-content">
        <div>
          <h1 class="text-2xl font-bold text-gray-800">AI模型配置</h1>
          <p class="text-gray-600 mt-2">管理DeepSeek和小米两个AI模型的配置</p>
        </div>
        <div class="header-actions">
          <el-button
            :icon="RefreshIcon"
            @click="refreshData"
            :loading="loading"
            type="primary"
          >
            刷新数据
          </el-button>
        </div>
      </div>
    </div>

    <!-- 模型配置标签页 -->
    <el-tabs
      v-model="activeTab"
      type="card"
      class="model-tabs"
      @tab-change="handleTabChange"
    >
      <!-- DeepSeek 配置标签页 -->
      <el-tab-pane label="🤖 DeepSeek" name="deepseek">
        <div class="model-config-form" v-loading="loading">
          <!-- 基本信息展示 -->
          <div class="model-info-section mb-6">
            <h3 class="text-lg font-semibold mb-3">基本信息</h3>
            <el-descriptions :column="2" border v-if="deepseekModel">
              <el-descriptions-item label="模型名称">{{
                deepseekModel.name
              }}</el-descriptions-item>
              <el-descriptions-item label="提供商">{{
                deepseekModel.provider
              }}</el-descriptions-item>
              <el-descriptions-item label="模型版本">{{
                deepseekModel.modelName
              }}</el-descriptions-item>
              <el-descriptions-item label="API地址">{{
                deepseekModel.baseUrl
              }}</el-descriptions-item>
            </el-descriptions>
          </div>

          <!-- 配置表单 -->
          <div class="config-form-section mb-6">
            <h3 class="text-lg font-semibold mb-3">配置信息</h3>
            <el-form
              :model="deepseekForm"
              label-width="120px"
              v-if="deepseekModel"
            >
              <el-row :gutter="20">
                <el-col :span="12">
                  <el-form-item label="API密钥" required>
                    <el-input
                      v-model="deepseekForm.apiKey"
                      type="password"
                      show-password
                      placeholder="请输入DeepSeek API密钥"
                    />
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="状态">
                    <el-radio-group v-model="deepseekForm.status">
                      <el-radio value="active">启用</el-radio>
                      <el-radio value="inactive">禁用</el-radio>
                    </el-radio-group>
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="默认模型">
                    <el-switch
                      v-model="deepseekForm.isDefault"
                      active-text="是"
                      inactive-text="否"
                    />
                  </el-form-item>
                </el-col>
              </el-row>

              <!-- 操作按钮 -->
              <div class="form-actions mt-4">
                <el-button
                  type="primary"
                  @click="saveConfig('deepseek')"
                  :loading="saving"
                >
                  保存配置
                </el-button>
                <el-button
                  @click="refreshBalance('deepseek')"
                  :loading="balanceLoading.deepseek"
                >
                  刷新余额
                </el-button>
                <el-button
                  @click="testConnection('deepseek')"
                  :loading="testLoading.deepseek"
                >
                  测试连接
                </el-button>
              </div>
            </el-form>
          </div>

          <!-- 使用统计 -->
          <div class="stats-section">
            <h3 class="text-lg font-semibold mb-3">使用统计</h3>
            <el-row :gutter="20" v-if="deepseekModel">
              <el-col :span="6">
                <el-statistic
                  title="使用次数"
                  :value="deepseekModel.totalUsage"
                />
              </el-col>
              <el-col :span="6">
                <el-statistic
                  title="Token消耗"
                  :value="deepseekModel.totalTokens"
                />
              </el-col>
              <el-col :span="6">
                <el-statistic
                  title="账户余额"
                  :value="deepseekBalance?.balance || 0"
                  :precision="2"
                  suffix="元"
                >
                  <template #suffix>
                    <span :class="getBalanceClass(deepseekBalance)">
                      {{ deepseekBalance?.currency || "CNY" }}
                    </span>
                  </template>
                </el-statistic>
              </el-col>
              <el-col :span="6">
                <el-statistic
                  title="最后使用"
                  :value="0"
                  :format="() => formatDate(deepseekModel.lastUsedAt)"
                  :value-style="{ fontSize: '14px' }"
                />
              </el-col>
            </el-row>
          </div>
        </div>
      </el-tab-pane>

      <!-- 小米 配置标签页 -->
      <el-tab-pane label="📱 小米" name="mimo">
        <div class="model-config-form" v-loading="loading">
          <!-- 基本信息展示 -->
          <div class="model-info-section mb-6">
            <h3 class="text-lg font-semibold mb-3">基本信息</h3>
            <el-descriptions :column="2" border v-if="mimoModel">
              <el-descriptions-item label="模型名称">{{
                mimoModel.name
              }}</el-descriptions-item>
              <el-descriptions-item label="提供商">{{
                mimoModel.provider
              }}</el-descriptions-item>
              <el-descriptions-item label="模型版本">{{
                mimoModel.modelName
              }}</el-descriptions-item>
              <el-descriptions-item label="API地址">{{
                mimoModel.baseUrl
              }}</el-descriptions-item>
            </el-descriptions>
          </div>

          <!-- 配置表单 -->
          <div class="config-form-section mb-6">
            <h3 class="text-lg font-semibold mb-3">配置信息</h3>
            <el-form :model="mimoForm" label-width="120px" v-if="mimoModel">
              <el-row :gutter="20">
                <el-col :span="12">
                  <el-form-item label="API密钥" required>
                    <el-input
                      v-model="mimoForm.apiKey"
                      type="password"
                      show-password
                      placeholder="请输入小米API密钥"
                    />
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="状态">
                    <el-radio-group v-model="mimoForm.status">
                      <el-radio value="active">启用</el-radio>
                      <el-radio value="inactive">禁用</el-radio>
                    </el-radio-group>
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="默认模型">
                    <el-switch
                      v-model="mimoForm.isDefault"
                      active-text="是"
                      inactive-text="否"
                    />
                  </el-form-item>
                </el-col>
              </el-row>

              <!-- 操作按钮 -->
              <div class="form-actions mt-4">
                <el-button
                  type="primary"
                  @click="saveConfig('mimo')"
                  :loading="saving"
                >
                  保存配置
                </el-button>
                <el-button
                  @click="refreshBalance('mimo')"
                  :loading="balanceLoading.mimo"
                >
                  刷新余额
                </el-button>
                <el-button
                  @click="testConnection('mimo')"
                  :loading="testLoading.mimo"
                >
                  测试连接
                </el-button>
              </div>
            </el-form>
          </div>

          <!-- 使用统计 -->
          <div class="stats-section">
            <h3 class="text-lg font-semibold mb-3">使用统计</h3>
            <el-row :gutter="20" v-if="mimoModel">
              <el-col :span="6">
                <el-statistic
                  title="使用次数"
                  :value="mimoModel.totalUsage"
                />
              </el-col>
              <el-col :span="6">
                <el-statistic
                  title="Token消耗"
                  :value="mimoModel.totalTokens"
                />
              </el-col>
              <el-col :span="6">
                <el-statistic
                  title="账户余额"
                  :value="mimoBalance?.balance || 0"
                  :precision="2"
                  suffix="元"
                >
                  <template #suffix>
                    <span :class="getBalanceClass(mimoBalance)">
                      {{ mimoBalance?.currency || "CNY" }}
                    </span>
                  </template>
                </el-statistic>
              </el-col>
              <el-col :span="6">
                <el-statistic
                  title="最后使用"
                  :value="0"
                  :format="() => formatDate(mimoModel.lastUsedAt)"
                  :value-style="{ fontSize: '14px' }"
                />
              </el-col>
            </el-row>
          </div>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script lang="ts" setup>
import { ref, reactive, onMounted, onUnmounted, computed } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { Refresh as RefreshIcon } from "@element-plus/icons-vue";
import { aiModelApi, type AiModel, type ModelBalance } from "@/api/ai-models";
// 移除date-fns依赖，使用原生日期格式化

// 响应式数据
const activeTab = ref("deepseek");
const loading = ref(false);
const saving = ref(false);
const balanceLoading = reactive({ deepseek: false, mimo: false });
const testLoading = reactive({ deepseek: false, mimo: false });

const deepseekModel = ref<AiModel | null>(null);
const mimoModel = ref<AiModel | null>(null);
const deepseekBalance = ref<ModelBalance | null>(null);
const mimoBalance = ref<ModelBalance | null>(null);

// 表单数据
const deepseekForm = reactive({
  apiKey: "",
  status: "active" as "active" | "inactive",
  isDefault: false,
});

const mimoForm = reactive({
  apiKey: "",
  status: "active" as "active" | "inactive",
  isDefault: false,
});

// 计算属性
const currentModel = computed(() => {
  return activeTab.value === "deepseek"
    ? deepseekModel.value
    : mimoModel.value;
});

const currentForm = computed(() => {
  return activeTab.value === "deepseek" ? deepseekForm : mimoForm;
});

// 方法
const loadModelData = async () => {
  loading.value = true;
  try {
    const response = await aiModelApi.getList();

    // 分离DeepSeek和小米模型
    const deepseek = response.models.find((m) => m.code === "deepseek");
    const mimo = response.models.find((m) => m.code === "mimo");

    if (deepseek) {
      deepseekModel.value = deepseek;
      deepseekForm.apiKey = deepseek.apiKey;
      deepseekForm.status = deepseek.status;
      deepseekForm.isDefault = deepseek.isDefault;
    }

    if (mimo) {
      mimoModel.value = mimo;
      mimoForm.apiKey = mimo.apiKey;
      mimoForm.status = mimo.status;
      mimoForm.isDefault = mimo.isDefault;
    }

    // 加载余额信息
    await loadBalances();
  } catch (error) {
    console.error("加载模型数据失败:", error);
    ElMessage.error("加载模型数据失败");
  } finally {
    loading.value = false;
  }
};

const loadBalances = async () => {
  try {
    const [deepseekBalanceRes, mimoBalanceRes] = await Promise.allSettled([
      aiModelApi.getBalance("deepseek"),
      aiModelApi.getBalance("mimo"),
    ]);

    if (deepseekBalanceRes.status === "fulfilled") {
      deepseekBalance.value = deepseekBalanceRes.value;
    }

    if (mimoBalanceRes.status === "fulfilled") {
      mimoBalance.value = mimoBalanceRes.value;
    }
  } catch (error) {
    console.error("加载余额失败:", error);
  }
};

const saveConfig = async (code: "deepseek" | "mimo") => {
  const form = code === "deepseek" ? deepseekForm : mimoForm;

  if (!form.apiKey.trim()) {
    ElMessage.warning("请输入API密钥");
    return;
  }

  saving.value = true;
  try {
    const updateData: any = {
      apiKey: form.apiKey,
      status: form.status,
      isDefault: form.isDefault,
    };

    const updatedModel = await aiModelApi.updateConfig(code, updateData);

    // 更新本地数据
    if (code === "deepseek") {
      deepseekModel.value = updatedModel;
    } else {
      mimoModel.value = updatedModel;
    }

    ElMessage.success("配置保存成功");

    // 自动测试连接
    await testConnection(code);
  } catch (error: any) {
    console.error("保存配置失败:", error);
    ElMessage.error(error.message || "保存配置失败");
  } finally {
    saving.value = false;
  }
};

const refreshBalance = async (code: "deepseek" | "mimo") => {
  balanceLoading[code] = true;
  try {
    const balance = await aiModelApi.getBalance(code);

    if (code === "deepseek") {
      deepseekBalance.value = balance;
    } else {
      mimoBalance.value = balance;
    }

    if (balance.status === "success") {
      ElMessage.success(
        `${code === "deepseek" ? "DeepSeek" : "小米"}余额刷新成功`
      );
    } else {
      ElMessage.warning(balance.message || "余额查询失败");
    }
  } catch (error: any) {
    console.error("刷新余额失败:", error);
    ElMessage.error(error.message || "刷新余额失败");
  } finally {
    balanceLoading[code] = false;
  }
};

const testConnection = async (code: "deepseek" | "mimo") => {
  testLoading[code] = true;
  try {
    const result = await aiModelApi.testConnection(code);

    if (result.success) {
      ElMessage.success(
        `${code === "deepseek" ? "DeepSeek" : "小米"}连接测试成功 (${
          result.responseTime
        }ms)`
      );
    } else {
      ElMessage.error(`连接测试失败: ${result.message}`);
    }
  } catch (error: any) {
    console.error("连接测试失败:", error);
    ElMessage.error(error.message || "连接测试失败");
  } finally {
    testLoading[code] = false;
  }
};

const handleTabChange = (tabName: string) => {
  activeTab.value = tabName;
};

const refreshData = async () => {
  console.log("手动刷新AI模型数据...");
  await loadModelData();
  ElMessage.success("数据刷新成功");
};

const getBalanceClass = (balance: ModelBalance | null) => {
  if (!balance || balance.status === "error") {
    return "text-red-500";
  }

  if (balance.balance < 1) {
    return "text-red-500";
  } else if (balance.balance < 10) {
    return "text-orange-500";
  } else {
    return "text-green-500";
  }
};

const formatDate = (date: Date | string | undefined) => {
  if (!date) return "暂无";

  try {
    const dateObj = typeof date === "string" ? new Date(date) : date;
    const now = new Date();
    const diff = now.getTime() - dateObj.getTime();

    const minutes = Math.floor(diff / (1000 * 60));
    const hours = Math.floor(diff / (1000 * 60 * 60));
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));

    if (minutes < 1) return "刚刚";
    if (minutes < 60) return `${minutes}分钟前`;
    if (hours < 24) return `${hours}小时前`;
    if (days < 30) return `${days}天前`;

    // 超过30天显示具体日期
    return dateObj.toLocaleDateString("zh-CN");
  } catch {
    return "格式错误";
  }
};

// 生命周期
onMounted(() => {
  loadModelData();
});

// 定时刷新数据（每30秒）
let refreshInterval: any = null;

onMounted(() => {
  // 设置定时刷新
  refreshInterval = setInterval(() => {
    console.log("定时刷新AI模型数据...");
    loadModelData();
  }, 30000);

  // 监听页面可见性变化
  const handleVisibilityChange = () => {
    if (!document.hidden) {
      console.log("页面重新可见，刷新AI模型数据...");
      loadModelData();
    }
  };

  document.addEventListener("visibilitychange", handleVisibilityChange);
});

// 清理定时器
onUnmounted(() => {
  if (refreshInterval) {
    clearInterval(refreshInterval);
  }
});
</script>

<style scoped>
.ai-model-config {
  padding: 20px;
  background: #fff;
  border-radius: 8px;
}

.page-header {
  border-bottom: 1px solid #e4e7ed;
  padding-bottom: 16px;
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.header-actions {
  display: flex;
  gap: 12px;
  align-items: center;
}

.model-tabs {
  margin-top: 20px;
}

.model-config-form {
  padding: 20px 0;
}

.model-info-section,
.config-form-section,
.stats-section {
  background: #fafafa;
  padding: 16px;
  border-radius: 6px;
  border: 1px solid #e4e7ed;
}

.form-actions {
  display: flex;
  gap: 12px;
}

:deep(.el-tabs__content) {
  padding: 0;
}

:deep(.el-statistic__content) {
  font-size: 16px;
}

:deep(.el-descriptions__label) {
  font-weight: 500;
}
</style>
