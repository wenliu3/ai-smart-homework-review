<template>
  <el-dialog
    v-model="dialogVisible"
    :title="formMode === 'add' ? '新增AI规则' : '编辑AI规则'"
    :width="isMobile ? '95%' : '800px'"
    :close-on-click-modal="false"
    :close-on-press-escape="false"
    @close="handleClose"
  >
    <el-form
      ref="formRef"
      :model="formData"
      :rules="formRules"
      label-width="100px"
      v-loading="loading"
    >
      <el-row :gutter="20">
        <el-col :span="24">
          <el-form-item label="规则名称" prop="name">
            <el-input
              v-model="formData.name"
              placeholder="请输入规则名称"
              maxlength="50"
              show-word-limit
            />
          </el-form-item>
        </el-col>

        <el-col :span="24">
          <el-form-item label="规则描述" prop="description">
            <el-input
              v-model="formData.description"
              type="textarea"
              :rows="3"
              placeholder="请输入规则描述"
              maxlength="200"
              show-word-limit
            />
          </el-form-item>
        </el-col>

        <el-col :span="isMobile ? 24 : 12">
          <el-form-item label="模型类型" prop="modelType">
            <el-select
              v-model="formData.modelType"
              placeholder="请选择模型类型"
              style="width: 100%"
              :loading="modelsLoading"
            >
              <el-option
                v-for="model in availableModels"
                :key="model.code"
                :label="`${getModelIcon(model.code)} ${model.name}`"
                :value="model.code"
              />
              <template #empty>
                <div class="empty-models">
                  <el-empty description="暂无可用模型" :image-size="60" />
                  <p style="color: #999; font-size: 12px">
                    请联系管理员配置AI模型
                  </p>
                </div>
              </template>
            </el-select>
          </el-form-item>
        </el-col>

        <el-col :span="isMobile ? 24 : 12">
          <el-form-item label="状态" prop="status">
            <el-select
              v-model="formData.status"
              placeholder="请选择状态"
              style="width: 100%"
            >
              <el-option label="启用" value="active" />
              <el-option label="禁用" value="inactive" />
            </el-select>
          </el-form-item>
        </el-col>

        <el-col :span="isMobile ? 24 : 12">
          <el-form-item label="可见性" prop="visibility">
            <el-select
              v-model="formData.visibility"
              placeholder="请选择可见性"
              style="width: 100%"
            >
              <el-option label="私有" value="private" />
              <el-option label="公开" value="public" />
              <el-option label="系统" value="system" v-if="isAdmin" />
            </el-select>
          </el-form-item>
        </el-col>

        <el-col :span="isMobile ? 24 : 12">
          <el-form-item label="标签">
            <el-select
              v-model="formData.tags"
              multiple
              filterable
              allow-create
              default-first-option
              placeholder="请输入或选择标签"
              style="width: 100%"
            >
              <el-option
                v-for="tag in commonTags"
                :key="tag"
                :label="tag"
                :value="tag"
              />
            </el-select>
          </el-form-item>
        </el-col>

        <el-col :span="24">
          <el-form-item label="提示词" prop="prompt">
            <el-input
              v-model="formData.prompt"
              type="textarea"
              :rows="8"
              placeholder="请输入AI提示词内容"
              maxlength="2000"
              show-word-limit
            />
          </el-form-item>
        </el-col>
      </el-row>
    </el-form>

    <template #footer>
      <div class="dialog-footer">
        <el-button @click="handleClose">取消</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="loading">
          {{ formMode === "add" ? "创建" : "更新" }}
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, reactive, computed, nextTick, onMounted } from "vue";
import { ElMessage } from "element-plus";
import { createAiRule, updateAiRule, getAiRuleById } from "@/api/ai-rule";
import { aiModelApi } from "@/api/ai-models";
import { useStore } from "vuex";

const props = defineProps({
  isMobile: {
    type: Boolean,
    default: false,
  },
});

const emit = defineEmits(["success"]);

const store = useStore();

// 计算属性
const isAdmin = computed(() => {
  const userRole = store.getters["user/role"];
  return userRole === "super_admin";
});

// 响应式数据
const dialogVisible = ref(false);
const loading = ref(false);
const modelsLoading = ref(false);
const formMode = ref("add"); // 'add' | 'edit'
const currentRuleId = ref("");
const availableModels = ref([]);

// 表单引用
const formRef = ref(null);

// 表单数据
const formData = reactive({
  name: "",
  description: "",
  modelType: "deepseek",
  prompt: "",
  status: "active",
  visibility: "private",
  tags: [],
});

// 常用标签
const commonTags = ref([
  "作业批改",
  "代码审查",
  "文本分析",
  "创意写作",
  "数学解题",
  "英语翻译",
  "学习辅导",
  "问答系统",
]);

// 获取模型图标
const getModelIcon = (modelCode) => {
  const icons = {
    deepseek: "🤖",
    mimo: "📱",
  };
  return icons[modelCode] || "🔮";
};

// 加载活跃模型列表
const loadAvailableModels = async () => {
  modelsLoading.value = true;
  try {
    const models = await aiModelApi.getActiveModels();
    availableModels.value = models;

    // 如果当前选择的模型不在活跃列表中，清空选择
    if (
      formData.modelType &&
      !models.find((m) => m.code === formData.modelType)
    ) {
      formData.modelType = models.length > 0 ? models[0].code : "";
      if (!models.length) {
        ElMessage.warning("暂无可用的AI模型，请联系管理员");
      }
    }

    // 如果还没有选择模型且有可用模型，选择第一个
    if (!formData.modelType && models.length > 0) {
      formData.modelType = models[0].code;
    }
  } catch (error) {
    console.error("获取可用模型失败:", error);
    ElMessage.error("获取可用模型失败");
    availableModels.value = [];
  } finally {
    modelsLoading.value = false;
  }
};

// 表单验证规则
const formRules = {
  name: [
    { required: true, message: "请输入规则名称", trigger: "blur" },
    {
      min: 2,
      max: 50,
      message: "规则名称长度在 2 到 50 个字符",
      trigger: "blur",
    },
  ],
  description: [
    { max: 200, message: "规则描述长度不能超过200个字符", trigger: "blur" },
  ],
  modelType: [{ required: true, message: "请选择模型类型", trigger: "change" }],
  prompt: [
    { required: true, message: "请输入提示词内容", trigger: "blur" },
    {
      min: 10,
      max: 2000,
      message: "提示词长度在 10 到 2000 个字符",
      trigger: "blur",
    },
  ],
  status: [{ required: true, message: "请选择状态", trigger: "change" }],
  visibility: [{ required: true, message: "请选择可见性", trigger: "change" }],
};

// 重置表单
const resetForm = () => {
  formData.name = "";
  formData.description = "";
  formData.modelType = "deepseek";
  formData.prompt = "";
  formData.status = "active";
  formData.visibility = "private";
  formData.tags = [];

  if (formRef.value) {
    formRef.value.clearValidate();
  }
};

// 打开表单
const openForm = async (mode, ruleId = "") => {
  formMode.value = mode;
  currentRuleId.value = ruleId;
  dialogVisible.value = true;

  await nextTick();
  resetForm();

  // 每次打开表单时都重新加载可用模型
  await loadAvailableModels();

  if (mode === "edit" && ruleId) {
    await loadRuleData(ruleId);
  }
};

// 加载规则数据
const loadRuleData = async (ruleId) => {
  loading.value = true;
  try {
    const response = await getAiRuleById(ruleId);

    formData.name = response.name;
    formData.description = response.description || "";
    formData.modelType = response.modelType;
    formData.prompt = response.prompt;
    formData.status = response.status;
    formData.visibility = response.visibility;
    formData.tags = response.tags || [];
  } catch (error) {
    console.error("加载规则数据失败", error);
    ElMessage.error("加载规则数据失败");
  } finally {
    loading.value = false;
  }
};

// 提交表单
const handleSubmit = async () => {
  if (!formRef.value) return;

  try {
    await formRef.value.validate();

    loading.value = true;

    const submitData = {
      name: formData.name.trim(),
      modelType: formData.modelType,
      prompt: formData.prompt.trim(),
      status: formData.status,
      visibility: formData.visibility,
      tags: formData.tags,
    };

    // 只有当description不为空时才添加到提交数据中
    if (formData.description && formData.description.trim()) {
      submitData.description = formData.description.trim();
    }

    if (formMode.value === "add") {
      await createAiRule(submitData);
      ElMessage.success("AI规则创建成功");
    } else {
      await updateAiRule(currentRuleId.value, submitData);
      ElMessage.success("AI规则更新成功");
    }

    handleClose();
    emit("success");
  } catch (error) {
    console.error("提交失败", error);
    ElMessage.error("操作失败：" + (error.message || "未知错误"));
  } finally {
    loading.value = false;
  }
};

// 关闭对话框
const handleClose = () => {
  dialogVisible.value = false;
  resetForm();
};

// 暴露方法给父组件
defineExpose({
  openForm,
});

// 组件初始化
onMounted(() => {
  // 预加载可用模型列表
  loadAvailableModels();
});
</script>

<style scoped>
.dialog-footer {
  text-align: right;
}

:deep(.el-textarea__inner) {
  font-family: "Consolas", "Monaco", "Courier New", monospace;
}

.empty-models {
  padding: 10px;
  text-align: center;
}

.empty-models p {
  margin: 8px 0 0 0;
}
</style>
