<template>
  <div v-if="steps.length > 0" class="run-timeline" data-testid="run-timeline">
    <div
      v-for="step in steps"
      :key="step.key"
      class="timeline-step"
      :class="`is-${step.status}`"
      :data-testid="`timeline-${step.key}`"
    >
      <span class="step-marker">{{ step.status === "done" ? "✓" : "…" }}</span>
      <span class="step-label">{{ step.label }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { TimelineStep } from "./timeline";

defineProps<{ steps: TimelineStep[] }>();
</script>

<style scoped>
.run-timeline { display: flex; flex-direction: column; gap: 3px; padding: 6px 0 6px 42px; font-size: 13px; }
.timeline-step { display: flex; align-items: center; gap: 6px; color: #909399; }
.timeline-step.is-running { color: #745fc1; }
.timeline-step.is-done { color: #67c23a; }
.step-marker { width: 14px; text-align: center; }
.timeline-step.is-running .step-marker { animation: blink 1s infinite alternate; }
@keyframes blink { to { opacity: .3; } }
</style>
