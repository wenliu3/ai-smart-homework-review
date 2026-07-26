<template>
  <div class="chat-view">
    <div ref="messageList" class="message-list">
      <div v-if="messages.length === 0" class="empty-hint">
        <el-icon class="empty-icon"><ChatLineSquare /></el-icon>
        <p>{{ config.welcome }}</p>
        <p class="sub">{{ config.capabilities.join(" · ") }}</p>
        <p class="safety-notice">{{ config.safetyNotice }}</p>
      </div>

      <div
        v-for="(message, index) in messages"
        :key="index"
        class="message-row"
        :class="message.role === 'user' ? 'is-user' : 'is-ai'"
      >
        <div class="message-avatar">
          <el-icon v-if="message.role === 'user'"><User /></el-icon>
          <el-icon v-else><Promotion /></el-icon>
        </div>
        <div
          v-if="message.kind === 'approval' && message.approval"
          class="message-bubble approval-card"
          data-testid="chat-approval-card"
        >
          <div class="approval-card-title">
            <el-icon><DocumentChecked /></el-icon>
            <span>待审批：{{ approvalActionLabel(message.approval.actionType) }}</span>
          </div>
          <p class="approval-card-summary">{{ message.approval.summary }}</p>
          <p class="approval-card-hint">
            该操作需要你确认后才会执行。
          </p>
          <el-button
            size="small"
            type="primary"
            data-testid="chat-open-approvals"
            @click="$emit('open-approvals')"
          >
            去审批
          </el-button>
        </div>
        <div v-else class="message-bubble" v-html="message.html"></div>
      </div>

      <div v-if="streamingContent" class="message-row is-ai">
        <div class="message-avatar">
          <el-icon><Promotion /></el-icon>
        </div>
        <div
          class="message-bubble"
          v-html="renderSafeMarkdown(streamingContent)"
        ></div>
      </div>

      <div v-if="isGenerating && currentPhase" class="phase-indicator">
        <el-icon class="phase-icon"><Loading /></el-icon>
        <span>{{ currentPhase }}</span>
      </div>

      <div
        v-if="isGenerating && !currentPhase && !streamingContent"
        class="message-row is-ai"
      >
        <div class="message-avatar">
          <el-icon><Promotion /></el-icon>
        </div>
        <div class="message-bubble thinking">
          <span class="dot"></span><span class="dot"></span><span class="dot"></span>
        </div>
      </div>
    </div>

    <div class="input-area">
      <textarea
        ref="input"
        v-model="draft"
        class="chat-input"
        :placeholder="config.inputPlaceholder"
        :disabled="isGenerating"
        rows="3"
        @keydown.enter.exact="handleEnter"
      ></textarea>
      <el-button
        v-if="!isGenerating"
        data-testid="assistant-send"
        type="primary"
        class="send-btn"
        :disabled="!draft.trim()"
        @click="submit"
      >
        <el-icon><Promotion /></el-icon>
      </el-button>
      <el-button
        v-else
        data-testid="assistant-stop"
        type="danger"
        class="send-btn"
        title="停止生成"
        @click="$emit('stop')"
      >
        <el-icon><VideoPause /></el-icon>
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { nextTick, ref, watch } from "vue";
import {
  ChatLineSquare,
  DocumentChecked,
  Loading,
  Promotion,
  User,
  VideoPause,
} from "@element-plus/icons-vue";

import { approvalActionLabel } from "./approval";
import { renderSafeMarkdown } from "./markdown";
import type { AssistantRoleConfig } from "./role-config";
import type { RenderedAssistantMessage } from "./types";

const props = defineProps<{
  config: AssistantRoleConfig;
  messages: RenderedAssistantMessage[];
  streamingContent: string;
  isGenerating: boolean;
  currentPhase: string;
}>();

const emit = defineEmits<{
  (event: "send", message: string): void;
  (event: "stop"): void;
  (event: "open-approvals"): void;
}>();

const draft = ref("");
const input = ref<HTMLTextAreaElement>();
const messageList = ref<HTMLElement>();

function submit() {
  const message = draft.value.trim();
  if (!message || props.isGenerating) return;
  emit("send", message);
  draft.value = "";
}

function handleEnter(event: KeyboardEvent) {
  // 中文输入法组词上屏的回车不应发送：Vue 的 .enter 修饰符不检查 isComposing，
  // 部分浏览器 IME 场景下 keyCode 为 229。此时不拦截默认行为，让输入法正常上屏。
  if (event.isComposing || event.keyCode === 229) return;
  event.preventDefault();
  submit();
}

function focus() {
  nextTick(() => input.value?.focus());
}

function scrollToBottom() {
  nextTick(() => {
    if (messageList.value) {
      messageList.value.scrollTop = messageList.value.scrollHeight;
    }
  });
}

watch(
  () => [props.messages.length, props.streamingContent],
  scrollToBottom,
);

defineExpose({ focus, scrollToBottom });
</script>

<style scoped>
.chat-view { display: flex; flex: 1; min-height: 0; flex-direction: column; }
.message-list { flex: 1; overflow-y: auto; padding: 18px; background: #f7f8fb; }
.empty-hint { color: #606266; text-align: center; padding: 54px 20px; }
.empty-icon { font-size: 42px; color: #8b78d6; }
.empty-hint p { margin: 10px 0 0; }
.empty-hint .sub { color: #909399; font-size: 13px; }
.safety-notice { color: #b88230; font-size: 12px; }
.message-row { display: flex; gap: 9px; margin-bottom: 14px; align-items: flex-start; }
.message-row.is-user { flex-direction: row-reverse; }
.message-avatar { width: 32px; height: 32px; border-radius: 50%; display: grid; place-items: center; color: white; background: #745fc1; flex: 0 0 auto; }
.is-user .message-avatar { background: #607be8; }
.message-bubble { max-width: 78%; padding: 10px 13px; border-radius: 12px; background: white; color: #303133; line-height: 1.6; overflow-wrap: anywhere; box-shadow: 0 2px 8px rgba(0, 0, 0, .06); }
.is-user .message-bubble { background: #607be8; color: white; }
.approval-card { border-left: 3px solid #745fc1; }
.approval-card-title { display: flex; align-items: center; gap: 6px; font-weight: 600; color: #745fc1; }
.approval-card-summary { margin: 8px 0 0; }
.approval-card-hint { margin: 4px 0 10px; font-size: 12px; color: #b88230; }
.phase-indicator { display: flex; align-items: center; gap: 8px; color: #745fc1; font-size: 13px; padding-left: 42px; }
.phase-icon { animation: spin 1.2s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.thinking .dot { display: inline-block; width: 6px; height: 6px; margin: 0 2px; border-radius: 50%; background: #909399; animation: pulse 1s infinite alternate; }
.thinking .dot:nth-child(2) { animation-delay: .2s; }
.thinking .dot:nth-child(3) { animation-delay: .4s; }
@keyframes pulse { to { opacity: .25; } }
.input-area { display: flex; gap: 10px; align-items: flex-end; padding: 12px; border-top: 1px solid #ebeef5; background: white; }
.chat-input { flex: 1; resize: none; border: 1px solid #dcdfe6; border-radius: 10px; padding: 10px 12px; font: inherit; outline: none; }
.chat-input:focus { border-color: #745fc1; }
.send-btn { flex: 0 0 auto; }
</style>
