<template>
  <div class="ai-rule-selector">
    <!-- 没有选中规则时：显示配置提示 -->
    <div v-if="!selectedRule" class="config-prompt">
      <div class="prompt-card" @click="showRuleSelector = true">
        <div class="prompt-icon">
          <el-icon size="24" color="#3b82f6">
            <Setting />
          </el-icon>
        </div>
        <div class="prompt-content">
          <h4 class="prompt-title">配置AI批改规则</h4>
          <p class="prompt-desc">
            选择一个AI规则来自动批改学生作业，确保批改标准的一致性
          </p>
        </div>
        <el-button
          type="primary"
          size="default"
          @click.stop="showRuleSelector = true"
          class="config-btn"
        >
          选择规则
        </el-button>
      </div>
    </div>

    <!-- 已选中规则时：显示提示词预览 -->
    <div v-else class="rule-preview">
      <div class="preview-header">
        <div class="rule-actions">
          <el-button
            size="small"
            text
            type="primary"
            @click="showRuleSelector = true"
            class="action-btn"
          >
            切换
          </el-button>
          <el-button
            size="small"
            text
            type="primary"
            @click="showFullPrompt = true"
            class="action-btn"
          >
            查看完整
          </el-button>
          <el-button
            size="small"
            text
            type="danger"
            @click="handleClearRule"
            class="action-btn"
          >
            清除
          </el-button>
        </div>
      </div>

      <div class="prompt-preview">
        <div class="preview-text">
          {{ getPromptPreview(selectedRule.prompt) }}
        </div>
      </div>
    </div>

    <!-- 规则选择弹框 -->
    <el-dialog
      v-model="showRuleSelector"
      title="选择AI批改规则"
      width="400px"
      class="rule-selector-dialog"
    >
      <div class="selector-content">
        <el-select
          v-model="tempSelectedRuleId"
          placeholder="请选择AI规则"
          style="width: 100%"
          :loading="loading"
          filterable
          size="default"
        >
          <el-option
            v-for="rule in ruleList"
            :key="rule.id"
            :label="rule.name"
            :value="rule.id"
          >
            <div class="rule-option">
              <div class="rule-main">
                <span class="rule-name">{{ rule.name }}</span>
                <el-tag
                  :type="rule.visibility === 'system' ? 'success' : 'info'"
                  size="small"
                >
                  {{ getVisibilityText(rule.visibility) }}
                </el-tag>
              </div>
              <div v-if="rule.description" class="rule-desc">
                {{ rule.description }}
              </div>
            </div>
          </el-option>
        </el-select>
      </div>

      <template #footer>
        <div class="dialog-footer">
          <el-button @click="showRuleSelector = false">取消</el-button>
          <el-button
            type="primary"
            @click="confirmRuleSelection"
            :disabled="!tempSelectedRuleId"
          >
            确定
          </el-button>
        </div>
      </template>
    </el-dialog>

    <!-- 完整提示词对话框 -->
    <el-dialog
      v-model="showFullPrompt"
      :title="`AI规则详情：${selectedRule?.name || ''}`"
      width="70%"
      class="prompt-dialog"
    >
      <div v-if="selectedRule" class="full-prompt-content">
        <div class="prompt-meta">
          <div class="meta-item">
            <span class="meta-label">规则名称：</span>
            <span class="meta-value">{{ selectedRule.name }}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">模型类型：</span>
            <el-tag type="info" size="small">{{
              selectedRule.modelType
            }}</el-tag>
          </div>
          <div class="meta-item">
            <span class="meta-label">提示词长度：</span>
            <span class="meta-value"
              >{{ selectedRule.prompt.length }} 字符</span
            >
          </div>
        </div>
        <div class="prompt-text">
          <div class="text-label">完整提示词：</div>
          <pre class="text-content">{{ selectedRule.prompt }}</pre>
        </div>
      </div>

      <template #footer>
        <el-button @click="showFullPrompt = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { Setting } from "@element-plus/icons-vue";
import { getAvailableAiRules } from "@/api/ai-rule";

// 从API获取的完整AI规则信息
interface AiRuleItem {
  id: string;
  name: string;
  description?: string;
  modelType: string;
  prompt: string;
  visibility: string;
  tags: string[];
}

// 简化的AI规则快照（用于作业存储）
interface AiRuleSnapshot {
  id: string;
  name: string;
  modelType: string;
  prompt: string;
}

interface Props {
  modelValue: AiRuleSnapshot | null;
}

interface Emits {
  (e: "update:modelValue", value: AiRuleSnapshot | null): void;
}

const props = defineProps<Props>();
const emit = defineEmits<Emits>();

const loading = ref(false);
const ruleList = ref<AiRuleItem[]>([]);
const showFullPrompt = ref(false);
const showRuleSelector = ref(false);
const tempSelectedRuleId = ref("");

// 计算属性
const selectedRule = computed(() => props.modelValue);

// 获取AI规则列表（只显示使用活跃模型的规则）
const loadAiRuleList = async () => {
  loading.value = true;
  try {
    const response = await getAvailableAiRules("active");
    // 这里后端API应该已经过滤了使用禁用模型的规则
    ruleList.value = response;
  } catch (error) {
    console.error("获取AI规则列表失败:", error);
  } finally {
    loading.value = false;
  }
};

// 获取可见性文本
const getVisibilityText = (visibility: string) => {
  switch (visibility) {
    case "system":
      return "系统";
    case "public":
      return "公开";
    case "private":
      return "私有";
    default:
      return "未知";
  }
};

// 获取提示词预览（截取前100个字符）
const getPromptPreview = (prompt: string) => {
  if (!prompt) return "";
  return prompt.length > 100 ? prompt.substring(0, 100) + "..." : prompt;
};

// 确认规则选择
const confirmRuleSelection = () => {
  if (!tempSelectedRuleId.value) return;

  const selectedRule = ruleList.value.find(
    (rule) => rule.id === tempSelectedRuleId.value
  );
  if (selectedRule) {
    // 将完整的AI规则信息转换为简化的快照格式
    const ruleSnapshot: AiRuleSnapshot = {
      id: selectedRule.id,
      name: selectedRule.name,
      modelType: selectedRule.modelType,
      prompt: selectedRule.prompt,
    };
    emit("update:modelValue", ruleSnapshot);
    showRuleSelector.value = false;
    tempSelectedRuleId.value = "";
  }
};

// 清除规则
const handleClearRule = () => {
  emit("update:modelValue", null);
  tempSelectedRuleId.value = "";
};

// 初始化
onMounted(() => {
  loadAiRuleList();
});

// 添加默认导出
defineOptions({
  name: "AiRuleSelector",
});
</script>

<script lang="ts">
// 添加默认导出以支持常规导入
import { defineComponent } from "vue";

export default defineComponent({
  name: "AiRuleSelector",
});
</script>

<style scoped>
.ai-rule-selector {
  width: 100%;
}

/* 配置提示样式 */
.config-prompt {
  width: 100%;
}

.prompt-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 10px;
  border: 2px dashed #d1d5db;
  border-radius: 8px;
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
  transition: all 0.3s ease;
  cursor: pointer;
}

.prompt-card:hover {
  border-color: #3b82f6;
  background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
}

.prompt-icon {
  flex-shrink: 0;
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(59, 130, 246, 0.1);
  border-radius: 50%;
}

.prompt-content {
  flex: 1;
}

.prompt-title {
  font-size: 16px;
  font-weight: 600;
  color: #1f2937;
  margin: 0 0 4px 0;
}

.prompt-desc {
  font-size: 14px;
  color: #6b7280;
  margin: 0;
  line-height: 1.4;
}

.config-btn {
  flex-shrink: 0;
}

/* 规则预览样式 */
.rule-preview {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #ffffff;
  overflow: hidden;
  box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1);
}

.preview-header {
  padding: 10px;
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
  border-bottom: 1px solid #e5e7eb;
  display: flex;
  justify-content: flex-end;
  align-items: center;
}

.rule-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

.action-btn {
  font-size: 12px;
  padding: 4px 8px !important;
  height: auto !important;
}

.prompt-preview {
  padding: 10px;
}

.preview-text {
  font-size: 13px;
  color: #374151;
  line-height: 1.6;
  font-family: "SF Mono", "Monaco", "Inconsolata", "Roboto Mono", monospace;
  background: #f9fafb;
  padding: 12px;
  border-radius: 6px;
  border: 1px solid #f3f4f6;
  min-height: 60px;
}

/* 规则选择弹框样式 */
.rule-selector-dialog :deep(.el-dialog__body) {
  padding: 20px;
}

.selector-content {
  margin-bottom: 20px;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

/* 下拉选项样式 */
.rule-option {
  padding: 8px 0;
}

.rule-main {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.rule-option .rule-name {
  font-weight: 500;
  color: #303133;
  font-size: 14px;
}

.rule-desc {
  font-size: 12px;
  color: #909399;
  line-height: 1.4;
  margin-top: 2px;
}

/* 完整提示词对话框样式 */
.prompt-dialog :deep(.el-dialog__body) {
  padding: 20px;
}

.full-prompt-content {
  max-height: 60vh;
  overflow-y: auto;
}

.prompt-meta {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid #f0f2f5;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.meta-label {
  font-size: 13px;
  font-weight: 500;
  color: #6b7280;
  min-width: 80px;
}

.meta-value {
  font-size: 13px;
  color: #374151;
}

.prompt-text {
  background: #f8fafc;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  overflow: hidden;
}

.text-label {
  font-size: 13px;
  font-weight: 500;
  color: #6b7280;
  padding: 12px 16px 8px;
  background: #f1f5f9;
  border-bottom: 1px solid #e5e7eb;
}

.text-content {
  margin: 0;
  padding: 16px;
  font-family: "SF Mono", "Monaco", "Inconsolata", "Roboto Mono", monospace;
  font-size: 13px;
  line-height: 1.6;
  color: #374151;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 400px;
  overflow-y: auto;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .prompt-card {
    flex-direction: column;
    text-align: center;
    gap: 12px;
    padding: 16px;
  }

  .preview-header {
    flex-direction: column;
    align-items: stretch;
    gap: 12px;
  }

  .rule-actions {
    justify-content: flex-end;
  }

  .rule-selector-dialog :deep(.el-dialog) {
    width: 90% !important;
    margin: 5vh auto;
  }

  .meta-item {
    flex-direction: column;
    align-items: flex-start;
    gap: 4px;
  }

  .meta-label {
    min-width: auto;
  }
}

/* 滚动条样式 */
.full-prompt-content::-webkit-scrollbar,
.text-content::-webkit-scrollbar {
  width: 6px;
}

.full-prompt-content::-webkit-scrollbar-track,
.text-content::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 3px;
}

.full-prompt-content::-webkit-scrollbar-thumb,
.text-content::-webkit-scrollbar-thumb {
  background: #c1c1c1;
  border-radius: 3px;
}

.full-prompt-content::-webkit-scrollbar-thumb:hover,
.text-content::-webkit-scrollbar-thumb:hover {
  background: #a8a8a8;
}
</style>
