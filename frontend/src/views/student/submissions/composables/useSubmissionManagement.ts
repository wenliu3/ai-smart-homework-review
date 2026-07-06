import { ref, computed, onUnmounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import SubmissionsApi, {
  type MySubmissionDetail,
  type Attachment,
  type SubmitAssignmentParams,
} from "@/api/submissions";
import { useAiReviewPolling } from "./useAiReviewPolling";
import { checkAiSupport } from "@/config/ai-config";

export function useSubmissionManagement() {
  const route = useRoute();
  const router = useRouter();

  // 响应式数据
  const loading = ref(true);
  const submitting = ref(false);
  const saving = ref(false);
  const deleting = ref(false);
  const submissionData = ref<MySubmissionDetail | null>(null);

  // AI评价轮询
  const {
    isPolling,
    pollingCount,
    startPolling,
    stopPolling,
    handleVisibilityChange,
  } = useAiReviewPolling();

  // 计算属性
  const assignmentId = computed(() => {
    const id = (route.query.assignmentId ||
      route.params.assignmentId) as string;
    console.log("📍 当前路由信息:", {
      query: route.query,
      params: route.params,
      assignmentId: id,
    });
    return id;
  });

  const classId = computed(() => {
    const id = (route.query.classId || route.params.classId) as string;
    console.log("📍 当前班级ID:", id);
    return id;
  });

  const isSubmitted = computed(() => {
    // 只有当老师已经批改过时，才认为是真正的已提交状态（不可重新提交）
    const status = submissionData.value?.submission?.status;
    return status === "teacher_reviewed";
  });

  // 是否可以保存草稿（只有草稿状态才能保存草稿）
  const canSaveDraft = computed(() => {
    const status = submissionData.value?.submission?.status;
    return !status || status === "draft";
  });

  // 是否可以提交（只有老师批改后不能提交，其余都可重新提交）
  const canSubmit = computed(() => {
    const submission = submissionData.value?.submission;
    if (!submission) return true; // 没有提交记录时可以提交
    return submission.status !== "teacher_reviewed";
  });

  // 获取提交限制提示信息
  const submissionLimitInfo = computed(() => {
    const submission = submissionData.value?.submission;
    if (!submission) return null;
    
    // 老师已批改
    if (submission.status === "teacher_reviewed") {
      return {
        type: "info" as const,
        title: "作业已被老师批改，无法重新提交",
        message: ""
      };
    }
    
    // 已提交过，显示提醒
    if (submission.status !== "draft") {
      return {
        type: "info" as const,
        title: "重新提交提醒",
        message: `您已提交${submission.submissionCount || 1}次，可继续修改后重新提交，直到老师评分。`
      };
    }
    
    return null;
  });

  // 是否显示提交表单（未被老师批改时显示）
  const showSubmissionForm = computed(() => {
    const status = submissionData.value?.submission?.status;
    return status !== "teacher_reviewed";
  });

  // 是否显示已提交内容（已提交且被老师批改时显示）
  const showSubmittedContent = computed(() => {
    const status = submissionData.value?.submission?.status;
    return status === "teacher_reviewed";
  });
  const isOverdue = computed(() => {
    if (!submissionData.value?.assignment.dueDate) return false;
    return new Date() > new Date(submissionData.value.assignment.dueDate);
  });

  // 获取状态标签类型
  const statusTagType = computed(() => {
    const status = submissionData.value?.submission?.status;
    const statusMap: Record<
      string,
      "success" | "warning" | "info" | "primary" | "danger"
    > = {
      draft: "info",
      submitted: "warning",
      ai_reviewed: "primary",
      teacher_reviewed: "success",
    };
    return statusMap[status || ""] || "info";
  });

  // 获取状态文本
  const statusText = computed(() => {
    const status = submissionData.value?.submission?.status;
    const statusMap: Record<string, string> = {
      draft: "草稿",
      submitted: "已提交",
      ai_reviewed: "AI已批改",
      teacher_reviewed: "教师已批改",
    };
    return statusMap[status || ""] || "未知状态";
  });

  // 获取当前状态（供轮询使用）
  const getCurrentStatus = () => {
    const aiReview = submissionData.value?.aiReview;
    return {
      status: submissionData.value?.submission?.status,
      hasAiReview: !!aiReview,
      hasAiError: !!aiReview?.aiReviewMetadata?.error, // 🔥 新增：检测AI评价错误
      assignment: submissionData.value?.assignment,
    };
  };

  // 加载数据
  const loadData = async () => {
    if (!assignmentId.value) {
      ElMessage.error("缺少作业ID参数");
      router.back();
      return;
    }

    if (!classId.value) {
      ElMessage.error("缺少班级ID参数");
      router.back();
      return;
    }

    try {
      loading.value = true;
      console.log(
        "🔍 开始查询作业数据，assignmentId:",
        assignmentId.value,
        "classId:",
        classId.value
      );
      const data = await SubmissionsApi.getMySubmission(assignmentId.value);
      console.log("📥 查询到的作业数据:", data);
      submissionData.value = data;
    } catch (error) {
      console.error("❌ 加载作业数据失败:", error);
      ElMessage.error("加载作业数据失败");
    } finally {
      loading.value = false;
    }
  };

  // 检查并启动AI评价轮询
  const checkAndStartPolling = () => {
    const { status, hasAiReview, hasAiError } = getCurrentStatus();
    const assignment = submissionData.value?.assignment;

    console.log("🔍 检查轮询启动条件:");
    console.log("  - 提交状态:", status);
    console.log("  - AI评价状态:", hasAiReview ? "已完成" : "未完成");
    console.log("  - AI错误状态:", hasAiError ? "有错误" : "无错误"); // 🔥 新增
    console.log("  - 作业状态:", assignment?.status);
    console.log("  - 作业截止时间:", assignment?.dueDate);
    console.log("  - 当前时间:", new Date().toISOString());

    // 🔥 如果有AI错误，立即停止轮询并显示错误信息
    if (hasAiError) {
      console.log("❌ AI评价失败，停止轮询");
      const errorMessage =
        submissionData.value?.aiReview?.aiReviewMetadata?.error || "AI评价失败";
      ElMessage.error(`AI评价失败: ${errorMessage}`);
      return;
    }

    // 检查作业是否可以进行AI评价
    const canAiReview = checkCanAiReview(assignment, status, hasAiReview);

    if (canAiReview.canReview) {
      console.log("✅ 满足轮询条件，启动AI评价轮询...");
      startPolling(loadData, getCurrentStatus);
    } else {
      console.log("❌ 不满足轮询条件，原因:", canAiReview.reason);
    }
  };

  // 检查是否可以进行AI评价
  const checkCanAiReview = (
    assignment: any,
    submissionStatus: string | undefined,
    hasAiReview: boolean
  ) => {
    // 如果已经有AI评价结果，不需要轮询
    if (hasAiReview) {
      return { canReview: false, reason: "AI评价已完成" };
    }

    // 如果提交状态不是submitted，不需要轮询
    if (submissionStatus !== "submitted") {
      return { canReview: false, reason: `提交状态为: ${submissionStatus}` };
    }

    // 使用统一的AI支持检查
    const aiSupport = checkAiSupport(assignment);

    if (!aiSupport.supported) {
      return { canReview: false, reason: aiSupport.reason };
    }

    return { canReview: true, reason: "满足AI评价条件" };
  };

  // 提交作业
  const handleSubmit = async (content: string, attachments: Attachment[]) => {
    try {
      // 根据当前状态显示不同的确认信息
      const isResubmit =
        submissionData.value?.submission &&
        submissionData.value.submission.status !== "draft";

      const confirmMessage = isResubmit
        ? "确定要重新提交作业吗？这将覆盖之前的提交内容。"
        : "确定要提交作业吗？";

      await ElMessageBox.confirm(confirmMessage, "确认提交", {
        confirmButtonText: "确定提交",
        cancelButtonText: "取消",
        type: "warning",
      });

      submitting.value = true;

      const params: SubmitAssignmentParams = {
        assignmentId: assignmentId.value,
        classId: classId.value,
        content,
        isDraft: false,
      };

      // 只有当有附件时才添加 attachments 字段
      if (attachments && attachments.length > 0) {
        params.attachments = attachments;
      }

      await SubmissionsApi.submit(params);
      ElMessage.success(isResubmit ? "作业重新提交成功！" : "作业提交成功！");

      // 重新加载数据
      await loadData();

      // 启动AI评价轮询
      checkAndStartPolling();
    } catch (error: any) {
      if (error !== "cancel") {
        console.error("提交作业失败:", error);
        ElMessage.error(error.message || "提交作业失败");
      }
    } finally {
      submitting.value = false;
    }
  };

  // 保存草稿
  const handleSaveDraft = async (
    content: string,
    attachments: Attachment[]
  ) => {
    // 检查是否可以保存草稿
    if (!canSaveDraft.value) {
      ElMessage.warning("作业已提交，无法保存草稿");
      return;
    }

    if (!content.trim()) {
      ElMessage.warning("请先输入作业内容");
      return;
    }

    try {
      saving.value = true;

      const params: SubmitAssignmentParams = {
        assignmentId: assignmentId.value,
        classId: classId.value,
        content,
        isDraft: true,
      };

      // 只有当有附件时才添加 attachments 字段
      if (attachments && attachments.length > 0) {
        params.attachments = attachments;
      }

      console.log("💾 开始保存草稿，参数:", params);
      const result = await SubmissionsApi.submit(params);
      console.log("✅ 草稿保存成功，响应:", result);
      ElMessage.success("草稿保存成功！");

      // 延迟一下再查询，确保数据已同步
      console.log("🔄 延迟500ms后重新加载数据...");
      await new Promise((resolve) => setTimeout(resolve, 500));
      console.log("🔄 开始重新加载数据...");
      await loadData();
    } catch (error: any) {
      console.error("❌ 保存草稿失败:", error);
      ElMessage.error(error.message || "保存草稿失败");
    } finally {
      saving.value = false;
    }
  };

  // 删除草稿
  const handleDelete = async () => {
    if (!submissionData.value?.submission?.id) return;

    try {
      await ElMessageBox.confirm(
        "确定要删除这个草稿吗？删除后无法恢复。",
        "确认删除",
        {
          confirmButtonText: "确定删除",
          cancelButtonText: "取消",
          type: "warning",
        }
      );

      deleting.value = true;

      await SubmissionsApi.deleteSubmission({
        submissionId: submissionData.value.submission.id,
      });

      ElMessage.success("草稿删除成功！");

      // 重新加载数据
      await loadData();
    } catch (error: any) {
      if (error !== "cancel") {
        console.error("删除草稿失败:", error);
        ElMessage.error(error.message || "删除草稿失败");
      }
    } finally {
      deleting.value = false;
    }
  };

  // 设置页面可见性监听
  const cleanupVisibilityListener = handleVisibilityChange(
    loadData,
    getCurrentStatus
  );

  // 组件卸载时清理
  onUnmounted(() => {
    stopPolling();
    cleanupVisibilityListener();
  });

  return {
    // 状态
    loading,
    submitting,
    saving,
    deleting,
    submissionData,

    // 轮询状态
    isPolling,
    pollingCount,

    // 计算属性
    assignmentId,
    classId,
    isSubmitted,
    canSaveDraft,
    canSubmit,
    submissionLimitInfo,
    showSubmissionForm,
    showSubmittedContent,
    isOverdue,
    statusTagType,
    statusText,

    // 方法
    loadData,
    handleSubmit,
    handleSaveDraft,
    handleDelete,
    checkAndStartPolling,
    stopPolling,
  };
}
