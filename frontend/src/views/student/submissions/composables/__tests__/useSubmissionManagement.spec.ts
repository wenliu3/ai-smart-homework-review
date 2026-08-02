import { mount } from "@vue/test-utils";
import { defineComponent, h, ref } from "vue";
import { afterEach, describe, expect, it, vi } from "vitest";

import SubmissionsApi from "@/api/submissions";
import type {
  Assignment,
  MySubmissionDetail,
  Submission,
} from "@/api/submissions";
import { getRun } from "@/api/assistant";
import { ElMessage } from "element-plus";

vi.mock("vue-router", () => ({
  useRoute: () => ({
    query: { assignmentId: "21", classId: "4" },
    params: {},
  }),
  useRouter: () => ({ back: vi.fn() }),
}));

vi.mock("element-plus", () => ({
  ElMessage: {
    error: vi.fn(),
    success: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
  },
  ElMessageBox: { confirm: vi.fn() },
}));

vi.mock("@/api/submissions", () => ({
  default: {
    getMySubmission: vi.fn(),
    submit: vi.fn(),
    deleteSubmission: vi.fn(),
  },
}));

vi.mock("@/api/assistant", () => ({ getRun: vi.fn() }));
vi.mock("@/config/ai-config", () => ({
  checkAiSupport: () => ({ supported: false, reason: "未配置 AI" }),
}));
vi.mock("../useAiReviewPolling", () => ({
  useAiReviewPolling: () => ({
    isPolling: ref(false),
    pollingCount: ref(0),
    startPolling: vi.fn(),
    stopPolling: vi.fn(),
    handleVisibilityChange: () => vi.fn(),
  }),
}));

import { useSubmissionManagement } from "../useSubmissionManagement";

type Management = ReturnType<typeof useSubmissionManagement> & {
  hasFormalSubmission: { value: boolean };
  canResubmit: { value: boolean };
};

const makeDetail = (
  submissionStatus: Submission["status"] | null,
  assignmentOverrides: Partial<Assignment> = {}
): MySubmissionDetail => ({
  assignment: {
    id: "21",
    title: "语料库分析",
    description: "",
    attachments: [],
    allowAttachments: true,
    dueDate: "2099-08-05T18:00:00",
    maxScore: 100,
    teacherName: "张老师",
    aiRule: null,
    status: "published",
    ...assignmentOverrides,
  },
  submission: submissionStatus
    ? {
        id: "8",
        content: "<p>已提交正文</p>",
        attachments: [],
        wordCount: 6,
        status: submissionStatus,
        submittedAt: "2026-08-01T12:00:00",
        updatedAt: "2026-08-01T12:00:00",
        createdAt: "2026-08-01T12:00:00",
        isDraft: submissionStatus === "draft",
        submissionCount: 1,
        gradingRunId: "run-1",
      }
    : null,
  aiReview: null,
  teacherReview: null,
});

let wrapper: ReturnType<typeof mount> | null = null;

const mountManagement = () => {
  let management!: Management;
  const Harness = defineComponent({
    setup() {
      management = useSubmissionManagement() as Management;
      return () => h("div");
    },
  });
  wrapper = mount(Harness);
  return management;
};

afterEach(() => {
  wrapper?.unmount();
  wrapper = null;
});

describe("useSubmissionManagement lifecycle state", () => {
  it("treats a formal submission as read-only until resubmission is requested", () => {
    const management = mountManagement();
    management.submissionData.value = makeDetail("submitted");

    expect(management.hasFormalSubmission).toBeDefined();
    expect(management.hasFormalSubmission.value).toBe(true);
    expect(management.showSubmissionForm.value).toBe(false);
    expect(management.showSubmittedContent.value).toBe(true);
    expect(management.canResubmit.value).toBe(true);
  });

  it("allows resubmission only before teacher review, deadline and termination", () => {
    const management = mountManagement();

    management.submissionData.value = makeDetail("ai_reviewed");
    expect(management.canResubmit.value).toBe(true);

    management.submissionData.value = makeDetail("teacher_reviewed");
    expect(management.canResubmit.value).toBe(false);

    management.submissionData.value = makeDetail("submitted", {
      dueDate: "2000-01-01T00:00:00",
    });
    expect(management.canResubmit.value).toBe(false);

    management.submissionData.value = makeDetail("ai_reviewed", {
      status: "terminated",
    });
    expect(management.canResubmit.value).toBe(false);
  });

  it("keeps resubmission guidance consistent with deadline and termination", () => {
    const management = mountManagement();

    management.submissionData.value = makeDetail("submitted");
    expect(management.submissionLimitInfo.value).toMatchObject({
      title: "重新提交提醒",
    });

    management.submissionData.value = makeDetail("submitted", {
      dueDate: "2000-01-01T00:00:00",
    });
    expect(management.submissionLimitInfo.value).toEqual({
      type: "info",
      title: "作业已截止，无法重新提交",
      message: "",
    });

    management.submissionData.value = makeDetail("ai_reviewed", {
      status: "terminated",
    });
    expect(management.submissionLimitInfo.value).toEqual({
      type: "info",
      title: "作业已终止，无法重新提交",
      message: "",
    });
  });

  it("keeps new submissions and drafts editable without review results", () => {
    const management = mountManagement();

    management.submissionData.value = makeDetail(null);
    expect(management.hasFormalSubmission.value).toBe(false);
    expect(management.showSubmissionForm.value).toBe(true);
    expect(management.showSubmittedContent.value).toBe(false);

    management.submissionData.value = makeDetail("draft");
    expect(management.hasFormalSubmission.value).toBe(false);
    expect(management.showSubmissionForm.value).toBe(true);
    expect(management.showSubmittedContent.value).toBe(false);
  });
});

describe("useSubmissionManagement grading run summary", () => {
  it("exposes a failed grading run as a read-only summary after getRun resolves", async () => {
    const management = mountManagement();

    vi.mocked(SubmissionsApi.getMySubmission).mockResolvedValue(
      makeDetail("submitted")
    );
    vi.mocked(getRun).mockResolvedValue({
      runId: "run-1",
      status: "failed",
      errorCode: "AGENT_GRADING_TIMEOUT",
      finalOutput: null,
      intent: null,
      startedAt: null,
      finishedAt: null,
    });

    await management.loadData();

    expect(management.gradingRun.value).toMatchObject({
      status: "failed",
      errorCode: "AGENT_GRADING_TIMEOUT",
    });
  });

  it("exposes a cancelled grading run as a read-only summary", async () => {
    const management = mountManagement();

    vi.mocked(SubmissionsApi.getMySubmission).mockResolvedValue(
      makeDetail("submitted")
    );
    vi.mocked(getRun).mockResolvedValue({
      runId: "run-1",
      status: "cancelled",
      errorCode: "AGENT_RUN_CANCELLED",
      finalOutput: null,
      intent: null,
      startedAt: null,
      finishedAt: null,
    });

    await management.loadData();

    expect(management.gradingRun.value).toMatchObject({
      status: "cancelled",
      errorCode: "AGENT_RUN_CANCELLED",
    });
  });

  it("keeps gradingRun unresolved when getRun throws (network error is not a failure)", async () => {
    const management = mountManagement();

    vi.mocked(SubmissionsApi.getMySubmission).mockResolvedValue(
      makeDetail("submitted")
    );
    vi.mocked(getRun).mockRejectedValue(new Error("network down"));

    await management.loadData();

    expect(management.gradingRun.value).toBeNull();
  });

  it("treats a completed run without AI result as terminal (degraded to manual review)", async () => {
    const management = mountManagement();

    vi.mocked(SubmissionsApi.getMySubmission).mockResolvedValue(
      makeDetail("submitted")
    );
    vi.mocked(getRun).mockResolvedValue({
      runId: "run-1",
      status: "completed",
      errorCode: null,
      finalOutput: "AI 批改未通过结构化校验，已转教师人工批改。",
      intent: null,
      startedAt: null,
      finishedAt: null,
    });

    await management.loadData();
    expect(management.gradingRun.value).toMatchObject({ status: "completed" });

    // completed + 无 AI 结果 = 终态：不启动轮询，提示人工批改（不再停留在评价中）
    management.checkAndStartPolling();
    expect(ElMessage.info).toHaveBeenCalledWith(
      "AI 批改已完成但未生成有效评分，请等待教师人工批改"
    );
  });
});
