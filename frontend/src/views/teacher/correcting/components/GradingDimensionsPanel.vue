<template>
  <div v-if="visible" class="dimensions-panel mb-4">
    <div class="text-sm font-medium text-purple-700 mb-2">
      📋 AI 分维度评分草案
    </div>

    <el-alert
      v-if="degraded"
      type="warning"
      :closable="false"
      show-icon
      title="AI 批改未通过结构化校验，已转人工批改"
      description="模型原始输出已留存，可作为参考；请以人工评分为准。"
      class="mb-2"
      data-testid="grading-degraded-alert"
    />

    <template v-if="outcome">
      <el-alert
        v-if="outcome.needs_human_review"
        type="warning"
        :closable="false"
        show-icon
        title="需要教师人工复核"
        :description="reviewReasons"
        class="mb-2"
        data-testid="grading-review-alert"
      />

      <table class="dimensions-table" data-testid="grading-dimensions-table">
        <thead>
          <tr>
            <th>评分维度</th>
            <th class="score-col">主批改</th>
            <th class="score-col">独立复核</th>
            <th>评语与证据</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="row in dimensionRows"
            :key="row.criterionId"
            :data-testid="`dimension-${row.criterionId}`"
          >
            <th scope="row">{{ row.title }}</th>
            <td class="score-col">{{ row.primaryScore }} / {{ row.maxScore }}</td>
            <td class="score-col">{{ row.reviewScore }} / {{ row.maxScore }}</td>
            <td>
              <div>{{ row.feedback }}</div>
              <div v-if="row.evidence" class="evidence">
                证据：{{ row.evidence }}
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";

import { getRunArtifacts, type RunArtifact } from "@/api/assistant";

interface DimensionRow {
  criterionId: string;
  title: string;
  primaryScore: number;
  reviewScore: number | string;
  maxScore: number;
  feedback: string;
  evidence: string;
}

const props = defineProps<{
  runId?: string | null;
}>();

const artifacts = ref<RunArtifact[]>([]);
const loaded = ref(false);

const outcome = computed<Record<string, any> | null>(() => {
  const item = artifacts.value.find(
    (artifact) => artifact.artifactType === "grading_outcome",
  );
  return (item?.payload as Record<string, any>) ?? null;
});

const degraded = computed(() =>
  artifacts.value.some(
    (artifact) => artifact.artifactType === "grading_raw_draft",
  ),
);

const visible = computed(
  () => loaded.value && (outcome.value !== null || degraded.value),
);

const reviewReasons = computed(() => {
  const reasons = (outcome.value?.review_reasons as string[]) || [];
  return reasons.join("；");
});

const dimensionRows = computed<DimensionRow[]>(() => {
  const primaryItems = (outcome.value?.primary?.items as any[]) || [];
  const reviewItems = (outcome.value?.review?.items as any[]) || [];
  const reviewById = new Map(
    reviewItems.map((item) => [item.criterion_id, item]),
  );
  return primaryItems.map((item) => ({
    criterionId: String(item.criterion_id),
    title: String(item.title || item.criterion_id),
    primaryScore: Number(item.score),
    reviewScore: reviewById.has(item.criterion_id)
      ? Number(reviewById.get(item.criterion_id).score)
      : "-",
    maxScore: Number(item.max_score),
    feedback: String(item.feedback || ""),
    evidence: ((item.evidence_refs as string[]) || []).join("、"),
  }));
});

async function load(runId: string) {
  try {
    const result = await getRunArtifacts(runId);
    artifacts.value = result.items || [];
  } catch {
    // 产物不可见（run 不存在/无权限）时静默隐藏面板
    artifacts.value = [];
  } finally {
    loaded.value = true;
  }
}

watch(
  () => props.runId,
  (runId) => {
    loaded.value = false;
    artifacts.value = [];
    if (runId) void load(runId);
  },
  { immediate: true },
);
</script>

<style scoped>
.dimensions-panel { padding: 12px; background: #faf5ff; border: 1px solid #e9d5ff; border-radius: 8px; }
.dimensions-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.dimensions-table th, .dimensions-table td { padding: 6px 8px; text-align: left; vertical-align: top; overflow-wrap: anywhere; }
.dimensions-table thead th { color: #7c3aed; font-weight: 500; border-bottom: 1px solid #e9d5ff; }
.dimensions-table tbody th { font-weight: 500; color: #374151; width: 22%; }
.dimensions-table tbody tr + tr { border-top: 1px solid #f3e8ff; }
.score-col { white-space: nowrap; width: 90px; }
.evidence { margin-top: 2px; font-size: 12px; color: #9ca3af; }
</style>
