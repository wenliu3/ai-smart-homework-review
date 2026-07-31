<template>
  <article class="submitted-content">
    <header class="submitted-content__header">
      <div>
        <p class="submitted-content__eyebrow">SUBMITTED WORK</p>
        <h2>我的提交</h2>
      </div>
      <span>{{ formatDate(submission?.submittedAt) }}</span>
    </header>

    <section v-if="submission?.content" class="submitted-content__body">
      <div class="submitted-content__section-heading">
        <h3>作业正文</h3>
        <span>{{ submission.wordCount || 0 }} 字</span>
      </div>
      <div class="submission-content" v-html="submission.content"></div>
    </section>

    <AssignmentAttachmentList
      :attachments="submission?.attachments || []"
      title="我的附件"
      @download="downloadFile"
    />

    <div
      v-if="!submission?.content && !submission?.attachments?.length"
      class="submitted-content__empty"
    >
      暂无提交内容
    </div>
  </article>
</template>

<script setup lang="ts">
import type { Submission } from "../../../../api/submissions";
import AssignmentAttachmentList from "../../components/AssignmentAttachmentList.vue";
import { useSubmissionUtils } from "../composables";

defineProps<{ submission?: Submission | null }>();

const { formatDate, downloadFile } = useSubmissionUtils();

defineOptions({ name: "SubmittedContent" });
</script>

<style scoped>
.submitted-content {
  display: grid;
  gap: 18px;
  padding: 22px;
  border: 1px solid #e8eaf2;
  border-radius: 15px;
  background: #fff;
}

.submitted-content__header,
.submitted-content__section-heading {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 18px;
}

.submitted-content__header {
  padding-bottom: 16px;
  border-bottom: 1px solid #eef0f5;
}

.submitted-content__eyebrow {
  margin: 0 0 4px;
  color: #6a5dd6;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.13em;
}

.submitted-content__header h2,
.submitted-content__section-heading h3 {
  margin: 0;
  color: #292e43;
}

.submitted-content__header h2 {
  font-size: 20px;
}
.submitted-content__section-heading h3 {
  font-size: 14px;
}

.submitted-content__header > span,
.submitted-content__section-heading > span {
  color: #969caf;
  font-size: 12px;
}

.submitted-content__body {
  padding: 18px;
  border-radius: 12px;
  background: #fafbfe;
}

.submitted-content__section-heading {
  margin-bottom: 12px;
}

.submission-content {
  color: #50576e;
  font-size: 14px;
  line-height: 1.85;
}

.submission-content :deep(img) {
  max-width: 100%;
  border-radius: 8px;
}
.submission-content :deep(p:first-child) {
  margin-top: 0;
}
.submission-content :deep(p:last-child) {
  margin-bottom: 0;
}

.submitted-content__empty {
  padding: 52px 20px;
  color: #9ba1b3;
  text-align: center;
}

@media (max-width: 560px) {
  .submitted-content {
    padding: 16px;
  }
  .submitted-content__header {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
