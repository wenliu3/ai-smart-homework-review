<template>
  <div class="student-page classes-page">
    <div class="student-page__inner classes-page__inner">
      <section class="student-hero classes-hero">
        <div>
          <p class="student-eyebrow">MY CLASSES</p>
          <h1 class="student-page-title">我的班级</h1>
          <p class="student-page-description">
            在班级之间快速切换，查看课程作业、截止安排和提交进度。
          </p>
        </div>
      </section>

      <div class="classes-workspace student-card">
        <ClassList ref="classListRef" />
        <AssignmentList />
      </div>

      <JoinClassDialog v-model="showJoinDialog" @success="handleJoinSuccess" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { provide, ref } from "vue";
import JoinClassDialog from "../../../components/JoinClassDialog.vue";
import AssignmentList from "./components/AssignmentList.vue";
import ClassList from "./components/ClassList.vue";

const selectedClass = ref<any>(null);
const selectedClassId = ref<string | null>(null);
const showJoinDialog = ref(false);
const classListRef = ref<{ refresh?: () => void } | null>(null);

const setSelectedClass = (classItem: any) => {
  selectedClass.value = classItem;
  selectedClassId.value = classItem?._id || null;
};

const refreshClassList = () => classListRef.value?.refresh?.();
const handleJoinSuccess = refreshClassList;

provide("selectedClass", selectedClass);
provide("selectedClassId", selectedClassId);
provide("setSelectedClass", setSelectedClass);
provide("showJoinDialog", showJoinDialog);
provide("refreshClassList", refreshClassList);
</script>

<style scoped>
@import "../student-theme.css";

.classes-page {
  min-height: 100%;
}
.classes-page__inner {
  display: flex;
  min-height: 0;
  flex-direction: column;
}
.classes-hero {
  flex: 0 0 auto;
}
.classes-hero > div {
  position: relative;
  z-index: 1;
}

.classes-workspace {
  display: flex;
  min-height: 620px;
  margin-top: 18px;
  overflow: hidden;
}

@media (max-width: 860px) {
  .classes-workspace {
    flex-direction: column;
  }
}
</style>
