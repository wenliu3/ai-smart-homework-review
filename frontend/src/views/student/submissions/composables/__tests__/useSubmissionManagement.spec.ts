import { mount } from "@vue/test-utils";
import { defineComponent, h, ref } from "vue";
import { afterEach, describe, expect, it, vi } from "vitest";

import type {
  Assignment,
  MySubmissionDetail,
  Submission,
} from "@/api/submissions";

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
