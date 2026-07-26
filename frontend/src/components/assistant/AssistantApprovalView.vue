<template>
  <div class="approval-view">
    <div class="toolbar">
      <el-button text size="small" @click="$emit('back')">返回</el-button>
      <el-button text size="small" :loading="loading" @click="load">
        刷新
      </el-button>
    </div>

    <div v-if="error" class="error-state">
      <span>{{ error }}</span>
      <el-button text type="primary" @click="load">重试</el-button>
    </div>

    <div class="approval-list">
      <el-empty
        v-if="!loading && !error && approvals.length === 0"
        description="暂无待审批操作"
        :image-size="80"
      />

      <article
        v-for="approval in approvals"
        :key="approval.approvalId"
        class="approval-card"
      >
        <div class="approval-heading">
          <strong>{{ approval.summary }}</strong>
          <span :class="['risk', `risk-${approval.riskLevel}`]">
            {{ riskLabel(approval.riskLevel) }}
          </span>
        </div>
        <dl>
          <dt>操作类型</dt><dd>{{ approval.actionType }}</dd>
          <dt>目标</dt><dd>{{ approval.targetType }} {{ approval.targetId || "" }}</dd>
          <dt>有效期至</dt><dd>{{ formatTime(approval.expiresAt) }}</dd>
        </dl>
        <pre>{{ safeJson(approval.parameters) }}</pre>

        <textarea
          v-model="reasons[approval.approvalId]"
          rows="2"
          maxlength="1000"
          placeholder="拒绝时请填写原因"
        ></textarea>
        <p v-if="validationErrors[approval.approvalId]" class="validation-error">
          {{ validationErrors[approval.approvalId] }}
        </p>

        <div class="actions">
          <el-button
            :data-testid="`reject-${approval.approvalId}`"
            :disabled="busyIds.has(approval.approvalId)"
            @click="reject(approval)"
          >
            拒绝
          </el-button>
          <el-button
            :data-testid="`approve-${approval.approvalId}`"
            type="primary"
            :disabled="busyIds.has(approval.approvalId)"
            @click="approve(approval)"
          >
            {{
              confirmingId === approval.approvalId
                ? "再次点击确认批准"
                : "批准并执行"
            }}
          </el-button>
        </div>
      </article>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";

import {
  approveAction,
  listApprovals,
  rejectAction,
  type AssistantApproval,
} from "@/api/assistant";

defineEmits<{ (event: "back"): void }>();

const approvals = ref<AssistantApproval[]>([]);
const loading = ref(false);
const error = ref("");
// 在途审批 ID 集合：并发审批时各卡片独立禁用，任一请求结束只解禁自己
const busyIds = ref(new Set<string>());
const confirmingId = ref<string | null>(null);
const reasons = reactive<Record<string, string>>({});
const validationErrors = reactive<Record<string, string>>({});

function safeJson(value: Record<string, unknown>): string {
  return JSON.stringify(value, null, 2);
}

function formatTime(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function riskLabel(risk: AssistantApproval["riskLevel"]): string {
  return { low: "低风险", medium: "中风险", high: "高风险" }[risk];
}

function errorMessage(cause: unknown): string {
  const responseMessage = (
    cause as { response?: { data?: { message?: unknown } } }
  )?.response?.data?.message;
  if (typeof responseMessage === "string" && responseMessage) {
    return responseMessage;
  }
  return cause instanceof Error && cause.message
    ? cause.message
    : "审批请求失败，请稍后重试";
}

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const result = await listApprovals("pending");
    approvals.value = result.items || [];
  } catch (cause) {
    approvals.value = [];
    error.value = errorMessage(cause);
  } finally {
    loading.value = false;
  }
}

async function approve(approval: AssistantApproval) {
  if (confirmingId.value !== approval.approvalId) {
    confirmingId.value = approval.approvalId;
    return;
  }
  busyIds.value.add(approval.approvalId);
  error.value = "";
  try {
    await approveAction(approval.approvalId, approval.parameters);
    confirmingId.value = null;
    await load();
  } catch (cause) {
    const message = errorMessage(cause);
    await load();
    error.value = message;
  } finally {
    busyIds.value.delete(approval.approvalId);
  }
}

async function reject(approval: AssistantApproval) {
  const reason = (reasons[approval.approvalId] || "").trim();
  if (!reason) {
    validationErrors[approval.approvalId] = "请输入拒绝原因";
    return;
  }
  validationErrors[approval.approvalId] = "";
  busyIds.value.add(approval.approvalId);
  error.value = "";
  try {
    await rejectAction(approval.approvalId, reason);
    await load();
  } catch (cause) {
    const message = errorMessage(cause);
    await load();
    error.value = message;
  } finally {
    busyIds.value.delete(approval.approvalId);
  }
}

onMounted(load);
</script>

<style scoped>
.approval-view { flex: 1; min-height: 0; display: flex; flex-direction: column; background: #f7f8fb; }
.toolbar { display: flex; justify-content: space-between; padding: 10px 12px; background: white; border-bottom: 1px solid #ebeef5; }
.approval-list { flex: 1; overflow-y: auto; padding: 12px; }
.approval-card { background: white; border: 1px solid #ebeef5; border-radius: 10px; padding: 14px; margin-bottom: 12px; }
.approval-heading { display: flex; justify-content: space-between; gap: 8px; }
.risk { border-radius: 10px; padding: 2px 8px; font-size: 12px; white-space: nowrap; }
.risk-low { background: #f0f9eb; color: #529b2e; }
.risk-medium { background: #fdf6ec; color: #b88230; }
.risk-high { background: #fef0f0; color: #c45656; }
dl { display: grid; grid-template-columns: 72px 1fr; gap: 5px 8px; font-size: 12px; }
dt { color: #909399; }
dd { margin: 0; color: #606266; overflow-wrap: anywhere; }
pre { max-height: 150px; overflow: auto; padding: 10px; border-radius: 6px; background: #f4f4f5; font-size: 12px; white-space: pre-wrap; }
textarea { width: 100%; box-sizing: border-box; resize: vertical; border: 1px solid #dcdfe6; border-radius: 6px; padding: 8px; font: inherit; }
.actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 9px; }
.validation-error, .error-state { color: #c45656; font-size: 12px; }
.error-state { margin: 12px; padding: 12px; background: #fef0f0; display: flex; justify-content: space-between; }
</style>
