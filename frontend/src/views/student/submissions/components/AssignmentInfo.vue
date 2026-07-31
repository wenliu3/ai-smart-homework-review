<template>
  <article class="assignment-info-card">
    <header class="assignment-summary">
      <div>
        <p class="assignment-summary__eyebrow">ASSIGNMENT BRIEF</p>
        <h2>作业要求</h2>
        <p class="assignment-summary__teacher">
          <el-icon><User /></el-icon>
          {{ assignment.teacherName }} 老师
        </p>
      </div>
      <span
        data-testid="assignment-status"
        class="assignment-status"
        :class="`assignment-status--${statusTone}`"
      >
        {{ isOverdue ? "已截止" : statusText }}
      </span>
    </header>

    <div class="assignment-facts">
      <div data-testid="assignment-deadline" class="assignment-fact">
        <span class="assignment-fact__icon"><Clock /></span>
        <span>
          <small>截止时间</small>
          <strong>{{ formatDate(assignment.dueDate) }}</strong>
        </span>
      </div>
      <div class="assignment-fact">
        <span class="assignment-fact__icon"><Star /></span>
        <span>
          <small>作业满分</small>
          <strong>{{ assignment.maxScore }} 分</strong>
        </span>
      </div>
      <div class="assignment-fact">
        <span class="assignment-fact__icon"><Paperclip /></span>
        <span>
          <small>教师附件</small>
          <strong>{{ assignment.attachments?.length || 0 }} 个</strong>
        </span>
      </div>
    </div>

    <section class="assignment-content-section">
      <div class="section-heading">
        <span class="section-heading__icon"><Document /></span>
        <div>
          <h3>任务说明</h3>
          <p>请先阅读要求和附件，再开始提交</p>
        </div>
      </div>
      <div
        ref="descriptionRef"
        class="description-content"
        v-html="assignment.description"
      ></div>
    </section>

    <AssignmentAttachmentList
      :attachments="assignment.attachments"
      title="教师附件"
      @download="downloadFile"
    />

    <div v-if="isOverdue" class="assignment-deadline-warning">
      <el-icon><Warning /></el-icon>
      当前已超过截止时间，提交入口将保持关闭。
    </div>
  </article>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import {
  Clock,
  Document,
  Paperclip,
  Star,
  User,
  Warning,
} from "@element-plus/icons-vue";
import type { Assignment, Submission } from "../../../../api/submissions";
import AssignmentAttachmentList from "../../components/AssignmentAttachmentList.vue";
import { useSubmissionUtils } from "../composables";

interface Props {
  assignment: Assignment;
  submission?: Submission | null;
  statusTagType: "success" | "warning" | "info" | "primary" | "danger";
  statusText: string;
  isOverdue: boolean;
}

const props = defineProps<Props>();

const { formatDate, downloadFile } = useSubmissionUtils();
const descriptionRef = ref();

const statusTone = computed(() => {
  if (props.isOverdue) return "danger";
  if (props.statusTagType === "success") return "success";
  if (props.statusTagType === "danger") return "danger";
  if (props.statusTagType === "warning") return "warning";
  return "primary";
});

defineOptions({ name: "AssignmentInfo" });
</script>

<style scoped>
.assignment-info-card {
  display: grid;
  gap: 20px;
  padding: 24px;
  border: 1px solid #e8eaf2;
  border-radius: 16px;
  background: #fff;
  box-shadow: 0 10px 30px rgba(34, 39, 70, 0.055);
}

.assignment-summary {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  padding-bottom: 18px;
  border-bottom: 1px solid #eff0f5;
}

.assignment-summary__eyebrow {
  margin: 0 0 4px;
  color: #7063db;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.13em;
}

.assignment-summary h2 {
  margin: 0;
  color: #252a40;
  font-size: 21px;
}

.assignment-summary__teacher {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 8px 0 0;
  color: #858ca0;
  font-size: 13px;
}

.assignment-status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 11px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
}

.assignment-status::before {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
  content: "";
}

.assignment-status--primary {
  background: #f0eeff;
  color: #6558d9;
}
.assignment-status--success {
  background: #eaf8f2;
  color: #25936a;
}
.assignment-status--warning {
  background: #fff5e5;
  color: #c77b22;
}
.assignment-status--danger {
  background: #fff0f1;
  color: #d74e5a;
}

.assignment-facts {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.assignment-fact {
  display: flex;
  align-items: center;
  gap: 11px;
  min-width: 0;
  padding: 13px;
  border: 1px solid #eeeff5;
  border-radius: 12px;
  background: #fafbfe;
}

.assignment-fact__icon,
.section-heading__icon {
  display: inline-flex;
  width: 34px;
  height: 34px;
  flex: 0 0 34px;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  background: #efedff;
  color: #6558d9;
}

.assignment-fact__icon :deep(svg),
.section-heading__icon :deep(svg) {
  width: 17px;
}

.assignment-fact > span:last-child {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 3px;
}

.assignment-fact small {
  color: #9298aa;
  font-size: 11px;
}

.assignment-fact strong {
  overflow: hidden;
  color: #363b50;
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.assignment-content-section {
  padding: 20px;
  border: 1px solid #eceef4;
  border-radius: 14px;
}

.section-heading {
  display: flex;
  align-items: center;
  gap: 11px;
  margin-bottom: 16px;
}

.section-heading h3 {
  margin: 0;
  color: #2b3045;
  font-size: 15px;
}

.section-heading p {
  margin: 3px 0 0;
  color: #969caf;
  font-size: 12px;
}

.description-content {
  color: #4f566e;
  font-size: 14px;
  line-height: 1.9;
}

.description-content :deep(p:first-child) {
  margin-top: 0;
}
.description-content :deep(p:last-child) {
  margin-bottom: 0;
}
.description-content :deep(img) {
  max-width: 100%;
  border-radius: 8px;
}

.assignment-deadline-warning {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 11px 13px;
  border-radius: 10px;
  background: #fff3f4;
  color: #c94d59;
  font-size: 13px;
}

@media (max-width: 680px) {
  .assignment-info-card {
    padding: 16px;
  }
  .assignment-facts {
    grid-template-columns: 1fr;
  }
  .assignment-content-section {
    padding: 16px;
  }
}
</style>
