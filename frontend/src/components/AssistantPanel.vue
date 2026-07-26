<template>
  <transition name="panel-slide">
    <div v-if="config" v-show="visible" class="assistant-panel">
      <header class="panel-header">
        <div class="header-title">
          <el-icon class="header-icon"><Promotion /></el-icon>
          <span>{{ config.title }}</span>
        </div>
        <div class="header-actions">
          <el-tooltip content="新建对话" placement="bottom">
            <el-button
              text
              circle
              size="small"
              :disabled="isGenerating"
              @click="newChat"
            >
              <el-icon><Plus /></el-icon>
            </el-button>
          </el-tooltip>
          <el-tooltip content="历史记录" placement="bottom">
            <el-button
              text
              circle
              size="small"
              data-testid="assistant-history"
              @click="currentView = 'history'"
            >
              <el-icon><Clock /></el-icon>
            </el-button>
          </el-tooltip>
          <el-tooltip
            v-if="config.canApprove"
            content="待审批操作"
            placement="bottom"
          >
            <el-button
              text
              circle
              size="small"
              data-testid="assistant-approvals"
              @click="currentView = 'approval'"
            >
              <el-icon><DocumentChecked /></el-icon>
            </el-button>
          </el-tooltip>
          <el-tooltip content="关闭" placement="bottom">
            <el-button text circle size="small" @click="$emit('close')">
              <el-icon><Close /></el-icon>
            </el-button>
          </el-tooltip>
        </div>
      </header>

      <AssistantChatView
        v-if="currentView === 'chat'"
        ref="chatView"
        :config="config"
        :messages="messages"
        :streaming-content="streamingContent"
        :is-generating="isGenerating"
        :current-phase="currentPhase"
        @send="sendMessage"
        @stop="stopGenerating"
        @open-approvals="currentView = 'approval'"
        @feedback="handleFeedback"
      />

      <AssistantHistoryView
        v-else-if="currentView === 'history'"
        :sessions="sessions"
        :loading="historyLoading"
        :error="historyError"
        @back="currentView = 'chat'"
        @retry="loadSessionList"
        @select="loadSession"
        @rename="handleRenameSession"
        @delete="handleDeleteSession"
      />

      <AssistantApprovalView
        v-else-if="currentView === 'approval' && config.canApprove"
        @back="currentView = 'chat'"
      />
    </div>
  </transition>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from "vue";
import {
  Clock,
  Close,
  DocumentChecked,
  Plus,
  Promotion,
} from "@element-plus/icons-vue";
import { ElMessage, ElMessageBox } from "element-plus";

import {
  cancelRun,
  createSession,
  deleteSession,
  getSessionMessages,
  listSessions,
  renameSession,
  streamAssistantRun,
  submitRunFeedback,
  type AssistantSession,
} from "@/api/assistant";
import { parseApprovalRequired } from "./assistant/approval";
import AssistantApprovalView from "./assistant/AssistantApprovalView.vue";
import AssistantChatView from "./assistant/AssistantChatView.vue";
import AssistantHistoryView from "./assistant/AssistantHistoryView.vue";
import { renderSafeMarkdown } from "./assistant/markdown";
import {
  getAssistantRoleConfig,
  type AssistantRole,
} from "./assistant/role-config";
import type {
  ApprovalCardData,
  RenderedAssistantMessage,
} from "./assistant/types";

type AssistantView = "chat" | "history" | "approval";
type ChatViewExposed = {
  focus: () => void;
  scrollToBottom: () => void;
};

const props = defineProps<{
  visible: boolean;
  role?: AssistantRole;
}>();

defineEmits<{ (event: "close"): void }>();

const config = computed(() => getAssistantRoleConfig(props.role));
const currentView = ref<AssistantView>("chat");
const messages = ref<RenderedAssistantMessage[]>([]);
const isGenerating = ref(false);
const streamingContent = ref("");
const sessionId = ref<string | null>(null);
const sessions = ref<AssistantSession[]>([]);
const historyLoading = ref(false);
const historyError = ref("");
const currentPhase = ref("");
const currentRunId = ref<string | null>(null);
const chatView = ref<ChatViewExposed>();
// 本会话产生的审批卡片：服务端消息列表里没有它们，
// onDone 用服务端快照覆盖消息后需要按顺序重新挂回去。
// 按会话累积而非按轮次清空，否则第二轮完成时会把第一轮的卡片冲掉。
const sessionApprovalCards = ref<RenderedAssistantMessage[]>([]);

let abortController: AbortController | null = null;
let sendGeneration = 0;

function makeMessage(
  role: RenderedAssistantMessage["role"],
  content: string,
  runId: string | null = null,
): RenderedAssistantMessage {
  return {
    role,
    content,
    html: renderSafeMarkdown(content),
    runId,
  };
}

function makeApprovalMessage(
  approval: ApprovalCardData,
): RenderedAssistantMessage {
  return {
    role: "assistant",
    content: approval.summary,
    html: "",
    kind: "approval",
    approval,
  };
}

function scrollToBottom() {
  chatView.value?.scrollToBottom();
}

async function ensureSession(): Promise<string> {
  if (sessionId.value) return sessionId.value;
  const result = await createSession();
  return result.sessionId;
}

async function sendMessage(text: string) {
  if (!text || isGenerating.value) return;
  const generation = ++sendGeneration;

  messages.value.push(makeMessage("user", text));
  isGenerating.value = true;
  streamingContent.value = "";
  currentPhase.value = "";
  currentRunId.value = null;
  scrollToBottom();

  let sid: string;
  try {
    sid = await ensureSession();
  } catch {
    if (generation !== sendGeneration) return;
    isGenerating.value = false;
    messages.value.push(
      makeMessage("assistant", "⚠️ 创建会话失败，请稍后重试"),
    );
    scrollToBottom();
    return;
  }
  if (generation !== sendGeneration || !props.visible) {
    if (generation === sendGeneration) finishRun();
    return;
  }
  sessionId.value = sid;

  abortController = streamAssistantRun(text, sid, {
    onEvent: (event) => {
      if (generation !== sendGeneration) return;
      if (event.type === "run.started" && event.data?.run_id) {
        currentRunId.value = String(event.data.run_id);
      }
      if (event.type === "approval.required") {
        const approval = parseApprovalRequired(event.data);
        if (!approval) return;
        const card = makeApprovalMessage(approval);
        sessionApprovalCards.value.push(card);
        messages.value.push(card);
        scrollToBottom();
      }
    },
    onPhase: (phase) => {
      if (generation !== sendGeneration) return;
      currentPhase.value = phase.label;
    },
    onDelta: (_delta, accumulated) => {
      if (generation !== sendGeneration) return;
      streamingContent.value = accumulated;
      scrollToBottom();
    },
    onDone: async (finalAnswer) => {
      if (generation !== sendGeneration) return;
      const streamedAnswer = finalAnswer || streamingContent.value;
      finishRun();
      try {
        const result = await getSessionMessages(sid);
        // finishRun 已解锁输入：await 期间用户可能已发新消息 / 新建对话 / 切换会话，
        // 旧会话快照不能覆盖当前消息列表。
        if (generation !== sendGeneration || sessionId.value !== sid) return;
        // 服务端消息列表不含审批卡片，覆盖后把本轮卡片挂回末尾
        messages.value = [
          ...(result.messages || []).map((message) =>
            makeMessage(message.role, message.content, message.runId),
          ),
          ...sessionApprovalCards.value,
        ];
      } catch {
        if (generation !== sendGeneration || sessionId.value !== sid) return;
        if (streamedAnswer) {
          messages.value.push(makeMessage("assistant", streamedAnswer));
        }
      }
      streamingContent.value = "";
      scrollToBottom();
    },
    onError: (error) => {
      if (generation !== sendGeneration) return;
      finishRun();
      streamingContent.value = "";
      messages.value.push(
        makeMessage("assistant", `⚠️ ${error.message || "请求失败"}`),
      );
      scrollToBottom();
    },
  });
}

function finishRun() {
  isGenerating.value = false;
  currentPhase.value = "";
  currentRunId.value = null;
  abortController = null;
}

async function cancelActiveRun() {
  sendGeneration += 1;
  abortController?.abort();
  abortController = null;
  if (currentRunId.value) {
    try {
      await cancelRun(currentRunId.value);
    } catch {
      // 运行可能已经结束；本地状态仍需正常收口。
    }
  }
}

async function stopGenerating() {
  await cancelActiveRun();
  const partial = streamingContent.value || "（已停止生成）";
  finishRun();
  streamingContent.value = "";
  messages.value.push(makeMessage("assistant", partial));
  scrollToBottom();
}

async function newChat() {
  await cancelActiveRun();
  finishRun();
  streamingContent.value = "";
  messages.value = [];
  sessionApprovalCards.value = [];
  sessionId.value = null;
  currentView.value = "chat";
  nextTick(() => chatView.value?.focus());
}

async function handleFeedback(runId: string, rating: 1 | -1) {
  try {
    await submitRunFeedback(runId, rating);
  } catch {
    // 评分尽力而为：失败不打断对话，也不弹错
  }
}

async function handleRenameSession(sessionId: string, currentTitle: string) {
  try {
    const { value } = await ElMessageBox.prompt("请输入新的会话标题", "重命名会话", {
      inputValue: currentTitle,
      confirmButtonText: "保存",
      cancelButtonText: "取消",
      inputValidator: (input: string) => !!input.trim() || "标题不能为空",
    });
    await renameSession(sessionId, value.trim());
    await loadSessionList();
  } catch {
    // 用户取消或请求失败：列表保持原样
  }
}

async function handleDeleteSession(targetSessionId: string) {
  try {
    await ElMessageBox.confirm(
      "删除后该会话将从历史列表移除，确认删除？",
      "删除会话",
      { type: "warning", confirmButtonText: "删除", cancelButtonText: "取消" },
    );
  } catch {
    return; // 用户取消
  }
  try {
    await deleteSession(targetSessionId);
    // 删除的是当前正打开的会话：复位到全新对话
    if (sessionId.value === targetSessionId) {
      await newChat();
    }
    await loadSessionList();
  } catch {
    ElMessage.error("删除会话失败");
  }
}

async function loadSessionList() {
  historyLoading.value = true;
  historyError.value = "";
  try {
    const result = await listSessions();
    sessions.value = result.sessions || [];
  } catch {
    sessions.value = [];
    historyError.value = "历史会话加载失败";
  } finally {
    historyLoading.value = false;
  }
}

async function loadSession(selectedSessionId: string) {
  // 生成中从历史切换会话：先终止当前运行并清空流式内容，
  // 防止旧会话的流式增量渲染进新会话（跨会话串流），
  // 也防止旧运行的完成回调用旧快照覆盖新会话消息。
  await cancelActiveRun();
  finishRun();
  streamingContent.value = "";
  // 切换会话：审批卡片属于旧会话，不能带进新会话
  sessionApprovalCards.value = [];
  try {
    const result = await getSessionMessages(selectedSessionId);
    sessionId.value = selectedSessionId;
    messages.value = (result.messages || []).map((message) =>
      makeMessage(message.role, message.content),
    );
    currentView.value = "chat";
    scrollToBottom();
  } catch {
    ElMessage.error("加载会话失败");
  }
}

async function resetForRoleChange() {
  await cancelActiveRun();
  finishRun();
  currentView.value = "chat";
  messages.value = [];
  sessionApprovalCards.value = [];
  streamingContent.value = "";
  sessionId.value = null;
  sessions.value = [];
  historyError.value = "";
}

watch(currentView, (view) => {
  if (view === "history") loadSessionList();
});

watch(
  () => props.visible,
  (visible) => {
    if (visible) {
      nextTick(() => chatView.value?.focus());
      return;
    }
    if (isGenerating.value) {
      // 与 stopGenerating 语义一致：把未完成的流式内容收编进消息列表，
      // 避免重开面板后残留半截流式气泡。
      void stopGenerating();
      return;
    }
    streamingContent.value = "";
    void cancelActiveRun().finally(finishRun);
  },
);

watch(
  () => props.role,
  () => {
    void resetForRoleChange();
  },
);

onBeforeUnmount(() => {
  void cancelActiveRun();
});
</script>

<style scoped>
.assistant-panel {
  position: fixed;
  right: 28px;
  bottom: 96px;
  width: min(520px, calc(100vw - 32px));
  height: 75vh;
  max-height: 720px;
  min-height: 500px;
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.18);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  z-index: 2001;
}

.panel-header {
  height: 52px;
  flex: 0 0 auto;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 12px 0 16px;
}

.header-title,
.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.header-title {
  font-weight: 600;
}

.header-actions :deep(.el-button) {
  color: white;
}

.panel-slide-enter-active,
.panel-slide-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.panel-slide-enter-from,
.panel-slide-leave-to {
  opacity: 0;
  transform: translateY(12px);
}

@media (max-width: 640px) {
  .assistant-panel {
    right: 8px;
    bottom: 76px;
    width: calc(100vw - 16px);
    height: calc(100vh - 96px);
    min-height: 0;
  }
}
</style>
