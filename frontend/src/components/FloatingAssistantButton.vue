<template>
  <transition name="fab-pop">
    <div
      v-show="visible"
      class="floating-assistant-btn"
      @click="$emit('toggle')"
      title="AI教学助手"
    >
      <el-icon class="fab-icon"><ChatDotRound /></el-icon>
      <span class="fab-badge" v-if="unread">AI</span>
    </div>
  </transition>
</template>

<script setup lang="ts">
import { ChatDotRound } from "@element-plus/icons-vue";

defineProps<{
  visible?: boolean;
  unread?: boolean;
}>();

defineEmits<{
  (e: "toggle"): void;
}>();
</script>

<style scoped>
.floating-assistant-btn {
  position: fixed;
  right: 28px;
  bottom: 28px;
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  box-shadow: 0 8px 24px rgba(102, 126, 234, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  z-index: 2000;
  transition: transform 0.25s ease, box-shadow 0.25s ease;
}

.floating-assistant-btn:hover {
  transform: scale(1.08);
  box-shadow: 0 12px 32px rgba(102, 126, 234, 0.55);
}

.fab-icon {
  font-size: 26px;
  color: #fff;
}

.fab-badge {
  position: absolute;
  top: -4px;
  right: -4px;
  background: #f56c6c;
  color: #fff;
  font-size: 10px;
  font-weight: 700;
  line-height: 1;
  padding: 3px 5px;
  border-radius: 8px;
  border: 2px solid #fff;
}

/* 进出动画 */
.fab-pop-enter-active,
.fab-pop-leave-active {
  transition: all 0.3s ease;
}

.fab-pop-enter-from,
.fab-pop-leave-to {
  opacity: 0;
  transform: scale(0.5);
}
</style>
