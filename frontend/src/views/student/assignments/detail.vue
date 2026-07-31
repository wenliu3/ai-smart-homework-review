<template>
  <div class="student-page assignment-detail-page">
    <div class="student-page__inner" v-loading="loading">
      <el-button class="detail-back" text :icon="ArrowLeft" @click="goBack">
        返回作业列表
      </el-button>

      <template v-if="assignment">
        <section class="student-hero assignment-detail-hero">
          <div class="assignment-detail-hero__copy">
            <p class="student-eyebrow">ASSIGNMENT DETAIL</p>
            <h1 class="student-page-title">{{ assignment.title }}</h1>
            <p class="student-page-description">
              {{ assignment.teacherName }} 老师 · 截止
              {{ formatDate(assignment.endDate) }}
            </p>
          </div>
          <span
            class="student-status"
            :class="`student-status--${getSubmissionStatusType()}`"
          >
            {{ getSubmissionStatusText() }}
          </span>
        </section>

        <div class="assignment-detail-grid">
          <main class="assignment-detail-main student-card">
            <section class="assignment-requirement">
              <div class="student-section-header">
                <div>
                  <p class="student-eyebrow">REQUIREMENTS</p>
                  <h2 class="student-section-title">作业要求</h2>
                  <p class="student-section-description">
                    请完整阅读任务说明和教师附件后再开始作业。
                  </p>
                </div>
              </div>
              <div
                class="assignment-content"
                v-html="assignment.description"
              ></div>
            </section>

            <AssignmentAttachmentList
              :attachments="assignment.attachments || []"
              title="教师附件"
              @download="downloadFile"
            />
          </main>

          <aside class="assignment-detail-side">
            <section class="detail-status-card student-card">
              <div class="detail-status-card__header">
                <p class="student-eyebrow">STATUS</p>
                <h2>当前状态</h2>
              </div>
              <dl>
                <div>
                  <dt>提交状态</dt>
                  <dd>
                    <span
                      class="student-status"
                      :class="`student-status--${getSubmissionStatusType()}`"
                    >
                      {{ getSubmissionStatusText() }}
                    </span>
                  </dd>
                </div>
                <div v-if="assignment.hasSubmitted">
                  <dt>评价状态</dt>
                  <dd>
                    <span
                      class="student-status"
                      :class="`student-status--${getReviewStatusType()}`"
                    >
                      {{ getReviewStatusText() }}
                    </span>
                  </dd>
                </div>
                <div>
                  <dt>截止时间</dt>
                  <dd
                    class="detail-deadline"
                    :class="{ overdue: assignment.isExpired }"
                  >
                    {{ formatDate(assignment.endDate) }}
                  </dd>
                </div>
              </dl>

              <div v-if="assignment.terminatedReason" class="terminated-reason">
                <strong>终止原因</strong>
                <p>{{ assignment.terminatedReason }}</p>
              </div>

              <div class="detail-actions">
                <el-button
                  v-if="assignment.hasSubmitted || assignment.hasDraft"
                  class="student-primary-button"
                  type="primary"
                  @click="viewSubmission"
                >
                  {{
                    assignment.hasSubmitted ? "查看提交与评价" : "继续编辑草稿"
                  }}
                </el-button>
                <el-button
                  v-else-if="
                    !assignment.isExpired && assignment.status !== 'terminated'
                  "
                  class="student-primary-button"
                  type="primary"
                  @click="startSubmission"
                >
                  开始作业
                </el-button>
                <div v-else class="detail-action-disabled">
                  {{ assignment.isExpired ? "作业已截止" : "作业已终止" }}
                </div>
              </div>
            </section>
          </aside>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { ArrowLeft } from "@element-plus/icons-vue";
import { getStudentAssignment } from "../../../api/assignments";
import type { Attachment } from "../../../api/submissions";
import AssignmentAttachmentList from "../components/AssignmentAttachmentList.vue";

const route = useRoute();
const router = useRouter();
const loading = ref(false);
const assignment = ref<any>(null);

const loadAssignment = async () => {
  loading.value = true;
  try {
    assignment.value = await getStudentAssignment(
      route.params.id as string,
      route.query.classId as string
    );
  } catch (error) {
    console.error("加载作业详情失败:", error);
    ElMessage.error("加载作业详情失败");
  } finally {
    loading.value = false;
  }
};

const formatDate = (date?: string) =>
  date ? new Date(date).toLocaleString("zh-CN") : "-";

const getSubmissionStatusType = () => {
  if (!assignment.value) return "primary";
  if (assignment.value.hasDraft && !assignment.value.hasSubmitted)
    return "warning";
  if (assignment.value.hasSubmitted) return "success";
  if (assignment.value.isExpired) return "danger";
  return "primary";
};

const getSubmissionStatusText = () => {
  if (!assignment.value) return "待提交";
  if (assignment.value.hasDraft && !assignment.value.hasSubmitted)
    return "草稿";
  if (assignment.value.hasSubmitted) return "已提交";
  if (assignment.value.isExpired) return "未提交";
  return "待提交";
};

const getReviewStatusType = () => {
  if (assignment.value?.submissionStatus === "teacher_reviewed")
    return "success";
  if (assignment.value?.submissionStatus === "ai_reviewed") return "primary";
  return "warning";
};

const getReviewStatusText = () => {
  if (assignment.value?.submissionStatus === "teacher_reviewed")
    return "已批改";
  if (assignment.value?.submissionStatus === "ai_reviewed") return "AI 已评";
  return "待批改";
};

const downloadFile = async (attachment: Attachment) => {
  try {
    const filename = (attachment.fileUrl || "").replace("/uploads/", "");
    const token = localStorage.getItem("token");
    const response = await fetch(`/api/upload/download/${filename}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const url = URL.createObjectURL(await response.blob());
    const link = document.createElement("a");
    link.href = url;
    link.download = attachment.fileName || filename;
    link.click();
    URL.revokeObjectURL(url);
  } catch (error) {
    console.error("附件下载失败:", error);
    ElMessage.warning("附件下载失败，请稍后重试");
  }
};

const goBack = () => router.back();

const openSubmission = () =>
  router.push({
    path: "/student/submissions",
    query: {
      assignmentId: route.params.id,
      classId: route.query.classId || "",
    },
  });

const startSubmission = openSubmission;
const viewSubmission = openSubmission;

onMounted(loadAssignment);
</script>

<style scoped>
@import "../student-theme.css";

.assignment-detail-page {
  min-height: 100%;
}
.detail-back {
  margin: 0 0 12px -8px;
  color: #767d91;
}

.assignment-detail-hero {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
}

.assignment-detail-hero__copy {
  position: relative;
  z-index: 1;
}
.assignment-detail-hero > .student-status {
  position: relative;
  z-index: 1;
}

.assignment-detail-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 310px;
  gap: 18px;
  margin-top: 18px;
  align-items: start;
}

.assignment-detail-main {
  display: grid;
  gap: 20px;
  padding: 24px;
}

.assignment-requirement {
  padding-bottom: 20px;
  border-bottom: 1px solid #eceef4;
}

.assignment-content {
  padding: 18px 20px;
  border-radius: 13px;
  background: #fafbfe;
  color: #50576d;
  font-size: 14px;
  line-height: 1.85;
}

.assignment-content :deep(p:first-child) {
  margin-top: 0;
}
.assignment-content :deep(p:last-child) {
  margin-bottom: 0;
}
.assignment-content :deep(h1),
.assignment-content :deep(h2),
.assignment-content :deep(h3) {
  margin: 0.9em 0 0.45em;
  color: #31364b;
  font-weight: 700;
}
.assignment-content :deep(ul),
.assignment-content :deep(ol) {
  padding-left: 1.5em;
}
.assignment-content :deep(img) {
  max-width: 100%;
  border-radius: 8px;
}

.assignment-detail-side {
  position: sticky;
  top: 18px;
}
.detail-status-card {
  overflow: hidden;
}
.detail-status-card__header {
  padding: 20px;
  border-bottom: 1px solid #eceef4;
}
.detail-status-card__header h2 {
  margin: 0;
  color: #2d3248;
  font-size: 18px;
}

.detail-status-card dl {
  display: grid;
  gap: 0;
  margin: 0;
  padding: 4px 20px;
}
.detail-status-card dl > div {
  display: grid;
  gap: 7px;
  padding: 15px 0;
  border-bottom: 1px solid #f0f1f5;
}
.detail-status-card dt {
  color: #9399aa;
  font-size: 11px;
}
.detail-status-card dd {
  margin: 0;
  color: #43495e;
  font-size: 13px;
  font-weight: 600;
}

.detail-deadline.overdue {
  color: #d4525e;
}
.terminated-reason {
  margin: 0 20px 18px;
  padding: 12px;
  border-radius: 10px;
  background: #fff1f2;
  color: #b84b55;
  font-size: 12px;
}
.terminated-reason p {
  margin: 5px 0 0;
  line-height: 1.6;
}

.detail-actions {
  padding: 0 20px 20px;
}
.detail-actions .el-button {
  width: 100%;
  margin: 0;
}
.detail-action-disabled {
  padding: 10px;
  border-radius: 9px;
  background: #f2f3f6;
  color: #969cad;
  text-align: center;
  font-size: 13px;
}

@media (max-width: 900px) {
  .assignment-detail-grid {
    grid-template-columns: 1fr;
  }
  .assignment-detail-side {
    position: static;
  }
}

@media (max-width: 620px) {
  .assignment-detail-hero {
    align-items: flex-start;
    flex-direction: column;
  }
  .assignment-detail-main {
    padding: 16px;
  }
  .assignment-content {
    padding: 15px;
  }
}
</style>
