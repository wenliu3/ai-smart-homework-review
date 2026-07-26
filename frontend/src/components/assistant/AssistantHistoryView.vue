<template>
  <div class="history-view">
    <div class="toolbar">
      <el-button text size="small" @click="$emit('back')">
        <el-icon><ArrowLeft /></el-icon> 返回
      </el-button>
      <el-button text size="small" :loading="loading" @click="$emit('retry')">
        刷新
      </el-button>
    </div>

    <div v-if="error" class="error-state">
      <span>{{ error }}</span>
      <el-button text type="primary" @click="$emit('retry')">重试</el-button>
    </div>

    <div v-else class="session-list">
      <el-empty
        v-if="!loading && sessions.length === 0"
        description="暂无历史会话"
        :image-size="80"
      />
      <button
        v-for="session in sessions"
        :key="session.sessionId"
        :data-testid="`session-${session.sessionId}`"
        class="session-item"
        type="button"
        @click="$emit('select', session.sessionId)"
      >
        <span class="session-title">{{ session.title || "（未命名会话）" }}</span>
        <span class="session-meta">
          <span class="session-time">
            {{ formatTime(session.updatedAt || session.createdAt) }}
          </span>
          <span class="session-actions">
            <span
              class="session-action"
              role="button"
              title="重命名"
              :data-testid="`rename-${session.sessionId}`"
              @click.stop="$emit('rename', session.sessionId, session.title || '')"
            >✏️</span>
            <span
              class="session-action"
              role="button"
              title="删除会话"
              :data-testid="`delete-${session.sessionId}`"
              @click.stop="$emit('delete', session.sessionId)"
            >🗑️</span>
          </span>
        </span>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ArrowLeft } from "@element-plus/icons-vue";
import moment from "moment";

import type { AssistantSession } from "@/api/assistant";

defineProps<{
  sessions: AssistantSession[];
  loading: boolean;
  error: string;
}>();

defineEmits<{
  (event: "back"): void;
  (event: "retry"): void;
  (event: "select", sessionId: string): void;
  (event: "rename", sessionId: string, currentTitle: string): void;
  (event: "delete", sessionId: string): void;
}>();

function formatTime(value: string | null): string {
  return value ? moment(value).format("MM-DD HH:mm") : "";
}
</script>

<style scoped>
.history-view { flex: 1; min-height: 0; display: flex; flex-direction: column; background: #f7f8fb; }
.toolbar { display: flex; justify-content: space-between; padding: 10px 12px; background: white; border-bottom: 1px solid #ebeef5; }
.session-list { padding: 12px; overflow-y: auto; }
.session-item { width: 100%; border: 1px solid #ebeef5; background: white; border-radius: 10px; padding: 13px; margin-bottom: 9px; display: flex; justify-content: space-between; align-items: center; cursor: pointer; text-align: left; }
.session-item:hover { border-color: #8b78d6; }
.session-title { color: #303133; font-weight: 500; }
.session-time { color: #909399; font-size: 12px; }
.session-meta { display: flex; align-items: center; gap: 8px; }
.session-actions { display: flex; gap: 2px; opacity: .35; }
.session-item:hover .session-actions { opacity: 1; }
.session-action { padding: 2px 4px; border-radius: 6px; font-size: 13px; }
.session-action:hover { background: #f0edfa; }
.error-state { margin: 18px; padding: 14px; border-radius: 8px; background: #fef0f0; color: #c45656; display: flex; justify-content: space-between; }
</style>
