<template>
  <div class="approval-diff">
    <p v-if="rows.length === 0" class="diff-empty">
      本次操作不修改任何字段。
    </p>

    <table v-else class="diff-table">
      <thead v-if="hasChanges">
        <tr>
          <th>字段</th>
          <th>原值</th>
          <th>新值</th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="row in rows"
          :key="row.key"
          :class="`row-${row.kind}`"
          :data-testid="`diff-row-${row.key}`"
        >
          <th scope="row">{{ row.label }}</th>
          <td class="value-before">
            <span v-if="row.before">{{ row.before }}</span>
            <span v-else class="value-empty">（空）</span>
          </td>
          <td v-if="hasChanges" class="value-after">
            <span v-if="row.after">{{ row.after }}</span>
            <span v-else class="value-empty">（空）</span>
          </td>
        </tr>
      </tbody>
    </table>

    <p v-if="rows.length > 0 && !hasChanges" class="diff-hint">
      以上为操作对象的当前信息，本次操作不修改这些字段。
    </p>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";

import { buildDiffRows } from "./diff";

const props = defineProps<{
  parameters: Record<string, unknown>;
}>();

const rows = computed(() => buildDiffRows(props.parameters));
// context 行只展示对象现状，没有「新值」列
const hasChanges = computed(() =>
  rows.value.some((row) => row.kind !== "context"),
);
</script>

<style scoped>
.approval-diff { font-size: 12px; }
.diff-empty, .diff-hint { margin: 6px 0 0; color: #909399; }
.diff-table { width: 100%; border-collapse: collapse; table-layout: fixed; }
.diff-table th, .diff-table td { padding: 6px 8px; text-align: left; vertical-align: top; overflow-wrap: anywhere; }
.diff-table thead th { color: #909399; font-weight: normal; border-bottom: 1px solid #ebeef5; }
.diff-table tbody th { width: 32%; color: #909399; font-weight: normal; }
.diff-table tbody tr + tr { border-top: 1px solid #f2f3f5; }
.value-before { color: #606266; }
.value-empty { color: #c0c4cc; }
.row-changed .value-before, .row-removed .value-before { background: #fef0f0; color: #c45656; text-decoration: line-through; }
.row-changed .value-after, .row-added .value-after { background: #f0f9eb; color: #529b2e; }
.row-context .value-before { background: #f4f4f5; }
</style>
