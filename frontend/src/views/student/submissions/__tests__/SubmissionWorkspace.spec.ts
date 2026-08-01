import { flushPromises, shallowMount } from "@vue/test-utils";
import { computed, defineComponent, h, ref } from "vue";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type {
  Assignment,
  MySubmissionDetail,
  Submission,
} from "@/api/submissions";

const getSubmissionDetail = vi.hoisted(() => vi.fn());
const submitMock = vi.hoisted(() => vi.fn());
const confirmMock = vi.hoisted(() => vi.fn());

vi.mock("vue-router", () => ({
  useRoute: () => ({
    query: { assignmentId: "21", classId: "3" },
    params: {},
  }),
  useRouter: () => ({ back: vi.fn(), push: vi.fn() }),
}));

vi.mock("element-plus", () => ({
  ElMessage: {
    error: vi.fn(),
    success: vi.fn(),
    warning: vi.fn(),
  },
  ElMessageBox: { confirm: confirmMock },
}));

vi.mock("@/api/submissions", () => ({
  SubmissionsApi: {
    submit: submitMock,
    submitFinal: vi.fn(),
    saveDraft: vi.fn(),
    deleteSubmission: vi.fn(),
  },
}));

vi.mock("../composables", async () => {
  const { computed, ref } = await import("vue");
  const { isFormalSubmissionStatus } = await import(
    "../utils/submissionLifecycle"
  );

  return {
    useSubmissionManagement: () => {
      const submissionData = ref<MySubmissionDetail>(getSubmissionDetail());
      const isOverdue = computed(
        () => new Date() > new Date(submissionData.value.assignment.dueDate)
      );
      const hasFormalSubmission = computed(() =>
        isFormalSubmissionStatus(submissionData.value.submission?.status)
      );
      const canResubmit = computed(() => {
        const status = submissionData.value.submission?.status;
        return (
          (status === "submitted" || status === "ai_reviewed") &&
          !isOverdue.value &&
          submissionData.value.assignment.status !== "terminated"
        );
      });

      return {
        loading: ref(false),
        submitting: ref(false),
        saving: ref(false),
        deleting: ref(false),
        submissionData,
        isPolling: ref(false),
        pollingCount: ref(0),
        isSubmitted: computed(
          () => submissionData.value.submission?.status === "teacher_reviewed"
        ),
        canSaveDraft: computed(() => {
          const status = submissionData.value.submission?.status;
          return !status || status === "draft";
        }),
        canSubmit: computed(
          () =>
            submissionData.value.submission?.status !== "teacher_reviewed"
        ),
        submissionLimitInfo: computed(() => null),
        hasFormalSubmission,
        canResubmit,
        showSubmissionForm: computed(() => !hasFormalSubmission.value),
        showSubmittedContent: computed(() => hasFormalSubmission.value),
        isOverdue,
        statusTagType: computed(() => "info"),
        statusText: computed(() => {
          const status = submissionData.value.submission?.status;
          if (!status) return "待提交";
          if (status === "draft") return "草稿";
          return "已提交";
        }),
        loadData: vi.fn().mockResolvedValue(undefined),
        handleSubmit: vi.fn(),
        handleSaveDraft: vi.fn(),
        handleDelete: vi.fn(),
        checkAndStartPolling: vi.fn(),
        stopPolling: vi.fn(),
      };
    },
    useSubmissionUtils: () => ({ formatDate: (value: string) => value }),
  };
});

import SubmissionWorkspace from "../index.vue";
import submissionWorkspaceSource from "../index.vue?raw";

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

const SubmissionFormStub = defineComponent({
  name: "SubmissionForm",
  setup(_, { expose }) {
    expose({
      validate: vi.fn().mockResolvedValue(true),
      getUploadedAttachments: () => [],
      getContent: () => "<p>重新提交正文</p>",
      markFilesConsumed: vi.fn(),
    });
    return () => h("div", { "data-testid": "submission-form" });
  },
});

const SubmittedContentStub = defineComponent({
  name: "SubmittedContent",
  props: { canResubmit: Boolean },
  emits: ["resubmit"],
  setup(props, { emit }) {
    return () =>
      h("div", { "data-testid": "submitted-content" }, [
        props.canResubmit
          ? h(
              "button",
              {
                "data-testid": "resubmit-button",
                onClick: () => emit("resubmit"),
              },
              "重新提交"
            )
          : null,
      ]);
  },
});

const mountWorkspace = (detail: MySubmissionDetail) => {
  getSubmissionDetail.mockReturnValue(detail);
  return shallowMount(SubmissionWorkspace, {
    global: {
      stubs: {
        "el-button": { template: "<button><slot /></button>" },
        "el-alert": true,
        "el-tabs": { template: "<div><slot /></div>" },
        "el-tab-pane": {
          template: "<section><slot name='label' /></section>",
        },
        "el-badge": true,
        "el-icon": { template: "<i><slot /></i>" },
        AssignmentInfo: true,
        SubmissionForm: SubmissionFormStub,
        SubmittedContent: SubmittedContentStub,
        ReviewResults: {
          template: '<div data-testid="review-results" />',
        },
      },
      directives: { loading: () => undefined },
    },
  });
};

beforeEach(() => {
  submitMock.mockReset();
  submitMock.mockResolvedValue({ id: "8", status: "submitted" });
  confirmMock.mockReset();
  confirmMock.mockResolvedValue(undefined);
});

describe("SubmissionWorkspace", () => {
  it("keeps the submission workspace as the vertical scroll container", () => {
    const containerRules = [
      ...submissionWorkspaceSource.matchAll(
        /\.submission-container\s*\{([^}]*)\}/g
      ),
    ];
    const finalRule = containerRules[containerRules.length - 1]?.[1] || "";

    expect(finalRule).toMatch(/height:\s*100%/);
    expect(finalRule).toMatch(/min-height:\s*0/);
    expect(finalRule).toMatch(/overflow-y:\s*auto/);
    expect(finalRule).toMatch(/overflow-x:\s*hidden/);
  });

  it("shows submission but no review step before a formal submission", () => {
    const wrapper = mountWorkspace(makeDetail(null));
    const navigation = wrapper.get(".tab-navigation").text();

    expect(navigation).toContain("作业详情");
    expect(navigation).toContain("提交作业");
    expect(navigation).not.toContain("评价结果");
    expect(wrapper.find('[data-testid="submission-form"]').exists()).toBe(
      true
    );
  });

  it("continues a draft without exposing review results", () => {
    const wrapper = mountWorkspace(makeDetail("draft"));
    const navigation = wrapper.get(".tab-navigation").text();

    expect(navigation).toContain("继续提交");
    expect(navigation).not.toContain("评价结果");
    expect(wrapper.find('[data-testid="submission-form"]').exists()).toBe(
      true
    );
  });

  it("opens a formal submission on read-only review results", () => {
    const wrapper = mountWorkspace(makeDetail("submitted"));
    const navigation = wrapper.get(".tab-navigation").text();

    expect(navigation).toContain("作业详情");
    expect(navigation).toContain("评价结果");
    expect(navigation).not.toContain("提交作业");
    expect(wrapper.find('[data-testid="submission-form"]').exists()).toBe(
      false
    );
    expect(wrapper.find('[data-testid="submitted-content"]').exists()).toBe(
      true
    );
    expect(wrapper.get(".results-pane").attributes("style") || "").not.toContain(
      "display: none"
    );
  });

  it("enters and cancels resubmission only through the explicit action", async () => {
    const wrapper = mountWorkspace(makeDetail("submitted"));

    await wrapper.get('[data-testid="resubmit-button"]').trigger("click");
    expect(wrapper.get(".tab-navigation").text()).toContain("重新提交");
    expect(wrapper.find('[data-testid="submission-form"]').exists()).toBe(
      true
    );

    await wrapper
      .get('[data-testid="cancel-resubmit-button"]')
      .trigger("click");
    expect(wrapper.get(".tab-navigation").text()).not.toContain("重新提交");
    expect(wrapper.find('[data-testid="submission-form"]').exists()).toBe(
      false
    );
    expect(wrapper.get(".results-pane").attributes("style") || "").not.toContain(
      "display: none"
    );
  });

  it("returns to review results after a successful resubmission", async () => {
    const wrapper = mountWorkspace(makeDetail("ai_reviewed"));

    await wrapper.get('[data-testid="resubmit-button"]').trigger("click");
    await wrapper.get(".submit-btn").trigger("click");
    await flushPromises();

    expect(submitMock).toHaveBeenCalledOnce();
    expect(wrapper.find('[data-testid="submission-form"]').exists()).toBe(
      false
    );
    expect(wrapper.get(".results-pane").attributes("style") || "").not.toContain(
      "display: none"
    );
  });

  it.each([
    ["teacher reviewed", makeDetail("teacher_reviewed")],
    [
      "overdue",
      makeDetail("submitted", { dueDate: "2000-01-01T00:00:00" }),
    ],
    ["terminated", makeDetail("submitted", { status: "terminated" })],
  ])("does not offer resubmission when %s", (_, detail) => {
    const wrapper = mountWorkspace(detail);

    expect(wrapper.find('[data-testid="resubmit-button"]').exists()).toBe(
      false
    );
  });

  it("shows pending submission rather than pending review without a record", () => {
    const wrapper = mountWorkspace(makeDetail(null));
    const statusText = wrapper.get(".submission-hero__statuses").text();

    expect(statusText).toContain("待提交");
    expect(statusText).not.toContain("待批改");
  });
});
