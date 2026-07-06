<template>
  <transition name="panel-slide">
    <div v-show="visible" class="assistant-panel">
      <!-- ====== 顶部标题栏 ====== -->
      <div class="panel-header">
        <div class="header-title">
          <el-icon class="header-icon"><Promotion /></el-icon>
          <span>AI教学助手</span>
        </div>
        <div class="header-actions">
          <el-tooltip content="新建对话" placement="bottom">
            <el-button
              text
              circle
              size="small"
              @click="newChat"
              :disabled="isGenerating"
            >
              <el-icon><Plus /></el-icon>
            </el-button>
          </el-tooltip>
          <el-tooltip content="历史记录" placement="bottom">
            <el-button
              text
              circle
              size="small"
              @click="currentView = 'history'"
            >
              <el-icon><Clock /></el-icon>
            </el-button>
          </el-tooltip>
          <el-tooltip content="关闭" placement="bottom">
            <el-button text circle size="small" @click="$emit('close')">
              <el-icon><Close /></el-icon>
            </el-button>
          </el-tooltip>
        </div>
      </div>

      <!-- ====== 视图A：对话视图 ====== -->
      <div v-show="currentView === 'chat'" class="chat-view">
        <!-- 消息列表 -->
        <div ref="msgListRef" class="message-list">
          <div v-if="messages.length === 0" class="empty-hint">
            <el-icon class="empty-icon"><ChatLineSquare /></el-icon>
            <p>你好！我是你的AI教学助手</p>
            <p class="sub">可以问我学生信息、作业提交情况、班级统计等</p>
          </div>

          <div
            v-for="(msg, i) in messages"
            :key="i"
            class="message-row"
            :class="msg.role === 'user' ? 'is-user' : 'is-ai'"
          >
            <div class="message-avatar">
              <el-icon v-if="msg.role === 'user'"><User /></el-icon>
              <el-icon v-else><Promotion /></el-icon>
            </div>
            <div class="message-bubble" v-html="msg.html">
            </div>
          </div>

          <!-- 思考中加载态 -->
          <div v-if="isGenerating && !streamingContent" class="message-row is-ai">
            <div class="message-avatar">
              <el-icon><Promotion /></el-icon>
            </div>
            <div class="message-bubble thinking">
              <span class="dot"></span>
              <span class="dot"></span>
              <span class="dot"></span>
            </div>
          </div>
        </div>

        <!-- 输入区 -->
        <div class="input-area">
          <textarea
            ref="inputRef"
            v-model="inputText"
            class="chat-input"
            placeholder="输入消息，回车发送，Shift+回车换行"
            :disabled="isGenerating"
            rows="3"
            @keydown.enter.exact.prevent="sendMessage"
          ></textarea>
          <el-button
            v-if="!isGenerating"
            type="primary"
            class="send-btn"
            :disabled="!inputText.trim()"
            @click="sendMessage"
          >
            <el-icon><Promotion /></el-icon>
          </el-button>
          <el-button
            v-else
            type="danger"
            class="send-btn"
            title="停止生成"
            @click="stopGenerating"
          >
            <el-icon><VideoPause /></el-icon>
          </el-button>
        </div>
      </div>

      <!-- ====== 视图B：历史记录视图 ====== -->
      <div v-show="currentView === 'history'" class="history-view">
        <div class="history-toolbar">
          <el-button text size="small" @click="currentView = 'chat'">
            <el-icon><ArrowLeft /></el-icon> 返回
          </el-button>
          <el-button
            text
            type="danger"
            size="small"
            @click="confirmClearAll"
            :disabled="sessions.length === 0"
          >
            <el-icon><Delete /></el-icon> 清空全部
          </el-button>
        </div>

        <div class="session-list">
          <el-empty
            v-if="sessions.length === 0"
            description="暂无历史会话"
            :image-size="80"
          />
          <div
            v-for="s in sessions"
            :key="s.sessionId"
            class="session-item"
            @click="loadSession(s.sessionId)"
          >
            <div class="session-main">
              <div class="session-preview">{{ s.lastMessage || "（空对话）" }}</div>
              <div class="session-meta">
                <span>{{ formatTime(s.lastTime) }}</span>
                <span class="dot-sep">·</span>
                <span>{{ s.messageCount }}条消息</span>
              </div>
            </div>
            <el-button
              text
              circle
              size="small"
              class="session-delete"
              @click.stop="confirmDelete(s)"
            >
              <el-icon><Delete /></el-icon>
            </el-button>
          </div>
        </div>
      </div>
    </div>
  </transition>
</template>

<script setup lang="ts">
import { ref, nextTick, watch, computed, onBeforeUnmount } from "vue";
import { ElMessageBox, ElMessage } from "element-plus";
import {
  Promotion,
  Plus,
  Clock,
  Close,
  User,
  ChatLineSquare,
  ArrowLeft,
  Delete,
  VideoPause,
} from "@element-plus/icons-vue";
import { marked } from "marked";
import moment from "moment";
import {
  chatStream,
  getSessions,
  getSessionMessages,
  deleteSession,
  deleteAllSessions,
  type ChatMessage,
  type ChatSession,
} from "@/api/chat";

// ===================== 组件属性 =====================
const props = defineProps<{ visible: boolean }>();
const emit = defineEmits<{ (e: "close"): void }>();

// ===================== 状态 =====================
const currentView = ref<"chat" | "history">("chat");
type RenderedMessage = ChatMessage & { html: string };
const messages = ref<RenderedMessage[]>([]);
const inputText = ref("");
const isGenerating = ref(false);
const streamingContent = ref(""); // 正在流式追加的内容
const sessionId = ref(generateSessionId());
const sessions = ref<ChatSession[]>([]);

const msgListRef = ref<HTMLElement>();
const inputRef = ref<HTMLTextAreaElement>();

let abortController: AbortController | null = null;

// 组件卸载时中止正在进行的 SSE 请求，防止内存/网络泄漏
onBeforeUnmount(() => {
  if (abortController) {
    abortController.abort();
    abortController = null;
  }
});

// ===================== Markdown 渲染 =====================
// async:false 确保浏览器 ESM 环境下 marked.parse() 返回 string 而非 Promise
marked.setOptions({ breaks: true, async: false });

function renderMarkdown(content: string): string {
  // 流式输出中可能有未闭合的 markdown，容错处理
  if (!content) return "";
  // 预处理：修复 AI 输出的不规范 markdown（#/- 后缺空格，CommonMark 要求必须有空格才识别）
  // 标题：行首 1-6 个 # 后直接跟非空格字符 → 补一个空格
  let fixed = content.replace(/^(#{1,6})([^\s#])/gm, "$1 $2");
  // 列表：行首 - 或 * 后直接跟非空格字符 → 补一个空格
  fixed = fixed.replace(/^([-*])([^\s*-])/gm, "$1 $2");
  try {
    // 显式传 { async: false } 确保同步返回 string（setOptions 的 async:false 可能不生效）
    const result = marked.parse(fixed, { async: false });
    if (typeof result === "string") return result;
    // marked 返回了 Promise — 退回纯文本，并打印警告便于定位
    console.warn("[renderMarkdown] marked.parse 返回非 string:", typeof result, content.slice(0, 30));
    return content;
  } catch (e) {
    console.error("[renderMarkdown] error:", e);
    return content;
  }
}

// 构造消息对象：content + 预渲染好的 html，v-html 直接读 msg.html，不依赖 computed
function makeMsg(role: "user" | "assistant", content: string): RenderedMessage {
  return { role, content, html: renderMarkdown(content) };
}

// ===================== 工具函数 =====================
function generateSessionId(): string {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
}

function formatTime(time: string): string {
  if (!time) return "";
  return moment(time).format("MM-DD HH:mm");
}

function scrollToBottom() {
  nextTick(() => {
    const el = msgListRef.value;
    if (el) el.scrollTop = el.scrollHeight;
  });
}

// ===================== 对话逻辑 =====================
function sendMessage() {
  const text = inputText.value.trim();
  if (!text || isGenerating.value) return;

  // 追加用户消息
  messages.value.push(makeMsg("user", text));
  inputText.value = "";
  isGenerating.value = true;
  streamingContent.value = "";

  scrollToBottom();

  // 发起 SSE 流式请求
  abortController = chatStream(text, sessionId.value, {
    onMessage: (chunk) => {
      // 第一次收到内容时，先创建 AI 消息占位
      if (!streamingContent.value) {
        messages.value.push({ role: "assistant", content: "" });
      }
      streamingContent.value += chunk;
      // 用整体数组替换（而非 splice/改属性）触发 ref 响应式，
      // 确保 renderedMessages computed 重新执行 marked.parse，实时渲染 markdown
      const idx = messages.value.length - 1;
      const next = [...messages.value];
      next[idx] = makeMsg("assistant", streamingContent.value);
      messages.value = next;
      scrollToBottom();
    },
    onDone: async () => {
      isGenerating.value = false;
      streamingContent.value = "";
      // 流式过程中 marked 对不完整 markdown 的解析可能有偏差（表格未闭合时后面的文字会被吞进表格），
      // 流结束后静默重新加载会话，用数据库里的完整内容重新渲染，确保最终显示和历史记录一致。
      try {
        const res = await getSessionMessages(sessionId.value);
        messages.value = (res.messages || []).map((m) => makeMsg(m.role, m.content));
      } catch {
        // 重新加载失败时保留流式结果
      }
      scrollToBottom();
    },
    onError: (err) => {
      isGenerating.value = false;
      streamingContent.value = "";
      messages.value.push(makeMsg("assistant", `⚠️ 出错了：${err}`));
      scrollToBottom();
    },
  });
}

function stopGenerating() {
  // 中断正在进行的 SSE 请求
  if (abortController) {
    abortController.abort();
    abortController = null;
  }
  isGenerating.value = false;
  // 保留已生成的内容；若一个字都还没收到，给个提示
  const idx = messages.value.length - 1;
  const last = messages.value[idx];
  if (last && last.role === "assistant") {
    const content = last.content || "（已停止生成）";
    messages.value.splice(idx, 1, makeMsg("assistant", content));
  }
  streamingContent.value = "";
  scrollToBottom();
}

function newChat() {
  // 如果正在生成，先中断
  if (abortController) {
    abortController.abort();
    abortController = null;
  }
  isGenerating.value = false;
  streamingContent.value = "";
  messages.value = [];
  sessionId.value = generateSessionId();
  currentView.value = "chat";
  nextTick(() => inputRef.value?.focus());
}

// ===================== 历史记录逻辑 =====================
async function loadSessionList() {
  try {
    const res = await getSessions();
    sessions.value = res.sessions || [];
  } catch {
    sessions.value = [];
  }
}

async function loadSession(sid: string) {
  try {
    ElMessage.info("正在加载会话...");
    const res = await getSessionMessages(sid);
    sessionId.value = sid;
    messages.value = (res.messages || []).map((m) => makeMsg(m.role, m.content));
    currentView.value = "chat";
    scrollToBottom();
  } catch {
    ElMessage.error("加载会话失败");
  }
}

async function confirmDelete(s: ChatSession) {
  try {
    await ElMessageBox.confirm(
      `确定删除该会话吗？（${s.messageCount}条消息）`,
      "删除确认",
      { type: "warning", confirmButtonText: "删除", cancelButtonText: "取消" }
    );
    await deleteSession(s.sessionId);
    ElMessage.success("已删除");
    // 如果删的是当前会话，清空对话
    if (s.sessionId === sessionId.value) {
      messages.value = [];
      sessionId.value = generateSessionId();
    }
    loadSessionList();
  } catch (e) {
    if (e !== "cancel" && e !== "close") {
      ElMessage.error("删除失败，请稍后重试");
    }
  }
}

async function confirmClearAll() {
  try {
    await ElMessageBox.confirm("确定清空全部会话记录吗？此操作不可恢复。", "清空确认", {
      type: "warning",
      confirmButtonText: "清空",
      cancelButtonText: "取消",
    });
    await deleteAllSessions();
    ElMessage.success("已清空全部会话");
    sessions.value = [];
    messages.value = [];
    sessionId.value = generateSessionId();
    currentView.value = "chat";
  } catch (e) {
    // 用户主动取消（点"取消"或关闭弹窗）时静默；其余为接口错误，需提示
    if (e !== "cancel" && e !== "close") {
      ElMessage.error("清空失败，请稍后重试");
    }
  }
}

// 切到历史视图时刷新列表
function onHistoryView() {
  loadSessionList();
}

// 监听视图切换
watch(currentView, (v) => {
  if (v === "history") onHistoryView();
});

// 面板打开时聚焦输入框
watch(
  () => props.visible,
  (v) => {
    if (v) {
      nextTick(() => inputRef.value?.focus());
    }
  }
);
</script>

<style scoped>
.assistant-panel {
  position: fixed;
  right: 28px;
  bottom: 96px;
  width: 520px;
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

/* ====== 顶部标题栏 ====== */
.panel-header {
  height: 52px;
  flex-shrink: 0;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 12px 0 16px;
}

.header-title {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #fff;
  font-size: 16px;
  font-weight: 600;
}

.header-icon {
  font-size: 20px;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}

.header-actions .el-button {
  color: #fff;
}

.header-actions .el-button:hover {
  background: rgba(255, 255, 255, 0.2);
}

/* ====== 对话视图 ====== */
.chat-view {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-height: 0;
}

.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 16px 12px;
  background: #f7f8fa;
}

/* 空状态提示 */
.empty-hint {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #999;
  text-align: center;
}

.empty-hint .empty-icon {
  font-size: 48px;
  color: #c0c4cc;
  margin-bottom: 12px;
}

.empty-hint p {
  margin: 4px 0;
  font-size: 14px;
}

.empty-hint .sub {
  font-size: 12px;
  color: #c0c4cc;
}

/* 消息行 */
.message-row {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}

.message-row.is-user {
  flex-direction: row-reverse;
}

.message-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: 16px;
  color: #fff;
}

.is-user .message-avatar {
  background: #667eea;
}

.is-ai .message-avatar {
  background: #764ba2;
}

/* 气泡 */
.message-bubble {
  max-width: 380px;
  padding: 10px 14px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.6;
  word-break: break-word;
}

.is-user .message-bubble {
  background: #667eea;
  color: #fff;
  border-top-right-radius: 4px;
}

.is-ai .message-bubble {
  background: #fff;
  color: #333;
  border: 1px solid #ebeef5;
  border-top-left-radius: 4px;
}

/* markdown 样式 */
.message-bubble :deep(p) {
  margin: 4px 0;
}

.message-bubble :deep(ul),
.message-bubble :deep(ol) {
  margin: 4px 0;
  padding-left: 20px;
}

.message-bubble :deep(li) {
  margin: 2px 0;
}

.message-bubble :deep(pre) {
  background: #f5f5f5;
  border-radius: 6px;
  padding: 8px;
  overflow-x: auto;
  font-size: 12px;
}

.message-bubble :deep(code) {
  background: #f0f0f0;
  padding: 2px 4px;
  border-radius: 3px;
  font-size: 12px;
}

/* markdown 表格 */
.message-bubble :deep(table) {
  border-collapse: collapse;
  margin: 8px 0;
  font-size: 13px;
  display: block;
  overflow-x: auto;
  max-width: 100%;
}

.message-bubble :deep(th),
.message-bubble :deep(td) {
  border: 1px solid #dcdfe6;
  padding: 6px 10px;
  text-align: left;
  white-space: nowrap;
}

.message-bubble :deep(th) {
  background: #f5f7fa;
  font-weight: 600;
  color: #303133;
}

.message-bubble :deep(tr:nth-child(even)) {
  background: #fafafa;
}

/* markdown 标题 */
.message-bubble :deep(h1),
.message-bubble :deep(h2),
.message-bubble :deep(h3),
.message-bubble :deep(h4) {
  margin: 10px 0 6px;
  font-weight: 600;
  line-height: 1.3;
}

.message-bubble :deep(h1) {
  font-size: 18px;
}

.message-bubble :deep(h2) {
  font-size: 16px;
}

.message-bubble :deep(h3) {
  font-size: 15px;
}

.message-bubble :deep(h4) {
  font-size: 14px;
}

/* 引用 / 分割线 / 链接 */
.message-bubble :deep(blockquote) {
  margin: 6px 0;
  padding: 4px 12px;
  border-left: 3px solid #667eea;
  background: #f5f7fa;
  color: #606266;
}

.message-bubble :deep(hr) {
  border: none;
  border-top: 1px solid #ebeef5;
  margin: 10px 0;
}

.message-bubble :deep(a) {
  color: #667eea;
  text-decoration: none;
}

.message-bubble :deep(a:hover) {
  text-decoration: underline;
}

/* 强调 */
.message-bubble :deep(strong) {
  font-weight: 600;
}

.is-user .message-bubble :deep(pre) {
  background: rgba(0, 0, 0, 0.2);
}

.is-user .message-bubble :deep(code) {
  background: rgba(0, 0, 0, 0.2);
}

/* 思考中动画 */
.message-bubble.thinking {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 14px 16px;
}

.thinking .dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #c0c4cc;
  animation: dot-bounce 1.4s infinite ease-in-out;
}

.thinking .dot:nth-child(2) {
  animation-delay: 0.2s;
}

.thinking .dot:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes dot-bounce {
  0%, 80%, 100% {
    transform: scale(0.6);
    opacity: 0.4;
  }
  40% {
    transform: scale(1);
    opacity: 1;
  }
}

/* ====== 输入区 ====== */
.input-area {
  flex-shrink: 0;
  padding: 10px 12px;
  border-top: 1px solid #ebeef5;
  background: #fff;
  display: flex;
  gap: 8px;
  align-items: flex-end;
}

.chat-input {
  flex: 1;
  resize: none;
  border: 1px solid #dcdfe6;
  border-radius: 8px;
  padding: 8px 12px;
  font-size: 14px;
  line-height: 1.5;
  outline: none;
  font-family: inherit;
  transition: border-color 0.2s;
  max-height: 100px;
}

.chat-input:focus {
  border-color: #667eea;
}

.chat-input:disabled {
  background: #f5f7fa;
  cursor: not-allowed;
}

.send-btn {
  flex-shrink: 0;
  width: 38px;
  height: 38px;
  border-radius: 8px;
  padding: 0;
}

/* ====== 历史视图 ====== */
.history-view {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.history-toolbar {
  flex-shrink: 0;
  display: flex;
  justify-content: space-between;
  padding: 8px 12px;
  border-bottom: 1px solid #ebeef5;
}

.session-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.session-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.2s;
}

.session-item:hover {
  background: #f5f7fa;
}

.session-item:hover .session-delete {
  opacity: 1;
}

.session-main {
  flex: 1;
  min-width: 0;
}

.session-preview {
  font-size: 13px;
  color: #333;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 4px;
}

.session-meta {
  font-size: 11px;
  color: #999;
  display: flex;
  align-items: center;
  gap: 4px;
}

.dot-sep {
  color: #ddd;
}

.session-delete {
  opacity: 0;
  transition: opacity 0.2s;
  color: #f56c6c !important;
}

/* ====== 面板进出动画 ====== */
.panel-slide-enter-active,
.panel-slide-leave-active {
  transition: all 0.3s ease;
}

.panel-slide-enter-from,
.panel-slide-leave-to {
  opacity: 0;
  transform: translateY(20px) scale(0.95);
}

/* ====== 滚动条美化 ====== */
.message-list::-webkit-scrollbar,
.session-list::-webkit-scrollbar {
  width: 5px;
}

.message-list::-webkit-scrollbar-thumb,
.session-list::-webkit-scrollbar-thumb {
  background: #dcdfe6;
  border-radius: 3px;
}

.message-list::-webkit-scrollbar-track,
.session-list::-webkit-scrollbar-track {
  background: transparent;
}
</style>
