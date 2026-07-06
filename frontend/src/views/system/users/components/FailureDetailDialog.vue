<template>
  <el-dialog
    :model-value="visible"
    :title="title || '失败详情'"
    width="900px"
    @close="handleClose"
    append-to-body
  >
    <div class="failure-table-wrapper">
      <el-table :data="pagedFailures" border style="width: 100%">
        <el-table-column prop="user.username" label="用户名" width="120" />
        <el-table-column prop="user.name" label="姓名" width="100" />
        <el-table-column prop="user.email" label="邮箱" min-width="180" />
        <el-table-column prop="user.role" label="角色" width="100" />
        <el-table-column prop="user.studentId" label="学号" width="100" />
        <el-table-column prop="reason" label="失败原因" min-width="200" />
      </el-table>
    </div>
    <div class="pagination-bar">
      <el-pagination
        background
        layout="prev, pager, next, total"
        :total="failures.length"
        :page-size="pageSize"
        :current-page="currentPage"
        @current-change="handlePageChange"
      />
    </div>
    <template #footer>
      <el-button @click="handleClose">关闭</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from "vue";

interface FailureItem {
  user: {
    username: string;
    name: string;
    email: string;
    role: string;
    studentId: string;
  };
  reason: string;
}

const props = defineProps<{
  visible: boolean;
  failures: FailureItem[];
  title?: string;
}>();

const emit = defineEmits(["close"]);

const pageSize = 20;
const currentPage = ref(1);

const pagedFailures = computed(() => {
  const start = (currentPage.value - 1) * pageSize;
  return props.failures.slice(start, start + pageSize);
});

function handlePageChange(page: number) {
  currentPage.value = page;
}

function handleClose() {
  emit("close");
}

// 当弹窗重新打开时，重置到第一页
watch(
  () => props.visible,
  (val) => {
    if (val) currentPage.value = 1;
  }
);
</script>

<style scoped>
.failure-table-wrapper {
  max-height: 400px;
  overflow-y: auto;
  margin-bottom: 16px;
}
.pagination-bar {
  text-align: right;
  margin-top: 8px;
}
</style>
