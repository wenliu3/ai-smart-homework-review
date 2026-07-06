<template>
  <el-dialog
    v-model="dialogVisible"
    title="批量删除结果"
    width="600px"
    :close-on-click-modal="false"
  >
    <div v-if="result">
      <!-- 成功统计 -->
      <div class="mb-4">
        <el-alert
          :type="result.success ? 'success' : 'warning'"
          :title="`删除完成：成功 ${result.successCount} 个，失败 ${result.failureCount} 个`"
          show-icon
          :closable="false"
        />
      </div>

      <!-- 失败详情 -->
      <div v-if="result.failures && result.failures.length > 0">
        <h4 class="mb-2">失败详情：</h4>
        <el-table :data="result.failures" border size="small" max-height="300">
          <el-table-column prop="userId" label="用户ID" width="200" />
          <el-table-column prop="reason" label="失败原因" />
        </el-table>
      </div>
    </div>

    <template #footer>
      <el-button type="primary" @click="dialogVisible = false">确定</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref } from "vue";

interface BatchDeleteResult {
  success: boolean;
  total: number;
  successCount: number;
  failureCount: number;
  failures?: Array<{
    userId: string;
    reason: string;
  }>;
}

const dialogVisible = ref(false);
const result = ref<BatchDeleteResult | null>(null);

const open = (deleteResult: BatchDeleteResult) => {
  result.value = deleteResult;
  dialogVisible.value = true;
};

defineExpose({
  open,
});
</script>
