<template>
  <el-dialog
    v-model="dialogVisible"
    title="AI规则详情"
    :width="isMobile ? '95%' : '900px'"
    :close-on-click-modal="false"
    @close="handleClose"
  >
    <div v-loading="loading" class="rule-detail">
      <el-descriptions :column="isMobile ? 1 : 2" border>
        <el-descriptions-item label="规则名称">
          <span class="font-medium">{{ ruleData.name }}</span>
        </el-descriptions-item>

        <el-descriptions-item label="模型类型">
          <el-tag
            :type="getModelTypeColor(ruleData.modelType)"
            size="small"
            effect="light"
          >
            {{ getModelTypeName(ruleData.modelType) }}
          </el-tag>
        </el-descriptions-item>

        <el-descriptions-item label="状态">
          <el-tag
            :type="ruleData.status === 'active' ? 'success' : 'danger'"
            size="small"
            effect="light"
          >
            {{ ruleData.status === "active" ? "启用" : "禁用" }}
          </el-tag>
        </el-descriptions-item>

        <el-descriptions-item label="可见性">
          <el-tag
            :type="getVisibilityColor(ruleData.visibility)"
            size="small"
            effect="light"
          >
            {{ getVisibilityName(ruleData.visibility) }}
          </el-tag>
        </el-descriptions-item>

        <el-descriptions-item label="创建者" v-if="ruleData.createdBy">
          {{ ruleData.createdBy.name }}
        </el-descriptions-item>

        <el-descriptions-item label="创建时间">
          {{
            ruleData.createdAt
              ? new Date(ruleData.createdAt).toLocaleString()
              : "-"
          }}
        </el-descriptions-item>

        <el-descriptions-item label="更新时间">
          {{
            ruleData.updatedAt
              ? new Date(ruleData.updatedAt).toLocaleString()
              : "-"
          }}
        </el-descriptions-item>

        <el-descriptions-item label="标签" :span="isMobile ? 1 : 2">
          <div class="flex flex-wrap gap-1">
            <el-tag
              v-for="tag in ruleData.tags"
              :key="tag"
              size="small"
              effect="plain"
              class="mr-1 mb-1"
            >
              {{ tag }}
            </el-tag>
            <span
              v-if="!ruleData.tags || ruleData.tags.length === 0"
              class="text-gray-400"
            >
              暂无标签
            </span>
          </div>
        </el-descriptions-item>

        <el-descriptions-item label="规则描述" :span="isMobile ? 1 : 2">
          <div class="description-content">
            {{ ruleData.description || "暂无描述" }}
          </div>
        </el-descriptions-item>
      </el-descriptions>

      <!-- 提示词内容 -->
      <div class="mt-6">
        <div class="flex items-center justify-between mb-3">
          <h3 class="text-lg font-medium text-gray-900">提示词内容</h3>
          <el-button
            size="small"
            type="primary"
            link
            @click="copyPrompt"
            :icon="CopyDocument"
          >
            复制
          </el-button>
        </div>

        <div class="prompt-container">
          <pre class="prompt-content">{{
            ruleData.prompt || "暂无提示词内容"
          }}</pre>
        </div>
      </div>
    </div>

    <template #footer>
      <div class="dialog-footer">
        <el-button @click="handleClose">关闭</el-button>
        <el-button type="primary" @click="handleEdit" v-if="canEdit">
          编辑规则
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, reactive, computed } from "vue";
import { ElMessage } from "element-plus";
import { getAiRuleById } from "@/api/ai-rule";
import { CopyDocument } from "@element-plus/icons-vue";
import { useStore } from "vuex";

const props = defineProps({
  isMobile: {
    type: Boolean,
    default: false,
  },
});

const emit = defineEmits(["success", "edit"]);

const store = useStore();

// 计算属性
const isAdmin = computed(() => {
  const userRole = store.getters["user/role"];
  return userRole === "super_admin";
});

const currentUserId = computed(() => {
  return store.getters["user/userId"];
});

const canEdit = computed(() => {
  if (!ruleData.id) return false;

  // 管理员可以编辑所有规则
  if (isAdmin.value) return true;

  // 普通用户只能编辑自己创建的规则
  return ruleData.createdBy?.id === currentUserId.value;
});

// 响应式数据
const dialogVisible = ref(false);
const loading = ref(false);
const currentRuleId = ref("");

// 规则数据
const ruleData = reactive({
  id: "",
  name: "",
  description: "",
  modelType: "",
  prompt: "",
  status: "",
  visibility: "",
  tags: [],
  createdBy: null,
  createdAt: "",
  updatedAt: "",
});

// 获取模型类型显示名称
const getModelTypeName = (modelType) => {
  const typeMap = {
    deepseek: "DeepSeek",
  };
  return typeMap[modelType] || modelType;
};

// 获取模型类型颜色
const getModelTypeColor = (modelType) => {
  const colorMap = {
    deepseek: "primary",
  };
  return colorMap[modelType] || "primary";
};

// 获取可见性显示名称
const getVisibilityName = (visibility) => {
  const nameMap = {
    private: "私有",
    public: "公开",
    system: "系统",
  };
  return nameMap[visibility] || visibility;
};

// 获取可见性颜色
const getVisibilityColor = (visibility) => {
  const colorMap = {
    private: "info",
    public: "success",
    system: "warning",
  };
  return colorMap[visibility] || "default";
};

// 重置数据
const resetData = () => {
  ruleData.id = "";
  ruleData.name = "";
  ruleData.description = "";
  ruleData.modelType = "";
  ruleData.prompt = "";
  ruleData.status = "";
  ruleData.visibility = "";
  ruleData.tags = [];
  ruleData.createdBy = null;
  ruleData.createdAt = "";
  ruleData.updatedAt = "";
};

// 打开详情
const openDetail = async (ruleId) => {
  currentRuleId.value = ruleId;
  dialogVisible.value = true;
  resetData();
  await loadRuleData(ruleId);
};

// 加载规则数据
const loadRuleData = async (ruleId) => {
  loading.value = true;
  try {
    const response = await getAiRuleById(ruleId);

    ruleData.id = response.id;
    ruleData.name = response.name;
    ruleData.description = response.description || "";
    ruleData.modelType = response.modelType;
    ruleData.prompt = response.prompt;
    ruleData.status = response.status;
    ruleData.visibility = response.visibility;
    ruleData.tags = response.tags || [];
    ruleData.createdBy = response.createdBy;
    ruleData.createdAt = response.createdAt;
    ruleData.updatedAt = response.updatedAt;
  } catch (error) {
    console.error("加载规则数据失败", error);
    ElMessage.error("加载规则数据失败");
  } finally {
    loading.value = false;
  }
};

// 复制提示词
const copyPrompt = async () => {
  if (!ruleData.prompt) {
    ElMessage.warning("暂无提示词内容可复制");
    return;
  }

  try {
    await navigator.clipboard.writeText(ruleData.prompt);
    ElMessage.success("提示词已复制到剪贴板");
  } catch (error) {
    console.error("复制失败", error);
    ElMessage.error("复制失败，请手动选择复制");
  }
};

// 编辑规则
const handleEdit = () => {
  emit("edit", ruleData);
  handleClose();
};

// 关闭对话框
const handleClose = () => {
  dialogVisible.value = false;
  resetData();
};

// 暴露方法给父组件
defineExpose({
  openDetail,
});
</script>

<style scoped>
.rule-detail {
  max-height: 70vh;
  overflow-y: auto;
}

.font-medium {
  font-weight: 500;
}

.text-gray-400 {
  color: #9ca3af;
}

.text-gray-900 {
  color: #111827;
}

.description-content {
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}

.prompt-container {
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  background-color: #f9fafb;
  padding: 16px;
  max-height: 300px;
  overflow-y: auto;
}

.prompt-content {
  margin: 0;
  font-family: "Consolas", "Monaco", "Courier New", monospace;
  font-size: 14px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
  color: #374151;
}

.dialog-footer {
  text-align: right;
}

.flex {
  display: flex;
}

.flex-wrap {
  flex-wrap: wrap;
}

.items-center {
  align-items: center;
}

.justify-between {
  justify-content: space-between;
}

.gap-1 {
  gap: 0.25rem;
}

.mr-1 {
  margin-right: 0.25rem;
}

.mb-1 {
  margin-bottom: 0.25rem;
}

.mb-3 {
  margin-bottom: 0.75rem;
}

.mt-6 {
  margin-top: 1.5rem;
}

.text-lg {
  font-size: 1.125rem;
}
</style>
