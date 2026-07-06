<template>
  <div class="h-full flex">
    <!-- 左侧班级列表组件 -->
    <ClassList ref="classListRef" />

    <!-- 右侧作业列表组件 -->
    <AssignmentList />

    <!-- 加入班级对话框 -->
    <JoinClassDialog v-model="showJoinDialog" @success="handleJoinSuccess" />
  </div>
</template>

<script setup lang="ts">
import { ref, provide } from "vue";
import ClassList from "./components/ClassList.vue";
import AssignmentList from "./components/AssignmentList.vue";
import JoinClassDialog from "../../../components/JoinClassDialog.vue";

// 共享状态
const selectedClass = ref(null);
const selectedClassId = ref<string | null>(null);
const showJoinDialog = ref(false);
const classListRef = ref(null);

// 设置选中的班级
const setSelectedClass = (classItem: any) => {
  selectedClass.value = classItem;
  selectedClassId.value = classItem ? classItem._id : null;
};

// 刷新班级列表
const refreshClassList = () => {
  if (classListRef.value && classListRef.value.refresh) {
    classListRef.value.refresh();
  }
};

// 加入班级成功处理
const handleJoinSuccess = () => {
  // 刷新班级列表
  refreshClassList();
};

// 提供数据给子组件
provide("selectedClass", selectedClass);
provide("selectedClassId", selectedClassId);
provide("setSelectedClass", setSelectedClass);
provide("showJoinDialog", showJoinDialog);
provide("refreshClassList", refreshClassList);
</script>

<style scoped>
/* 动画效果 */
@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* 响应式设计 */
@media (max-width: 768px) {
  :deep(.w-\[320px\]) {
    width: 280px !important;
  }
}
</style>
