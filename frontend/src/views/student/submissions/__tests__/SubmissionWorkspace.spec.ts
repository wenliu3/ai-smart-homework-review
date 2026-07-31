import { shallowMount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";

vi.mock("vue-router", () => ({
  useRoute: () => ({
    query: { assignmentId: "21", classId: "3" },
    params: {},
  }),
  useRouter: () => ({ back: vi.fn(), push: vi.fn() }),
}));

vi.mock("@/api/submissions", () => ({
  SubmissionsApi: {
    submitFinal: vi.fn(),
    saveDraft: vi.fn(),
    deleteSubmission: vi.fn(),
  },
}));

vi.mock("../composables", async () => {
  const { computed, ref } = await import("vue");
  const submissionData = ref({
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
    },
    submission: null,
    aiReview: null,
    teacherReview: null,
  });
  return {
    useSubmissionManagement: () => ({
      loading: ref(false),
      submitting: ref(false),
      saving: ref(false),
      deleting: ref(false),
      submissionData,
      isPolling: ref(false),
      pollingCount: ref(0),
      isSubmitted: computed(() => false),
      canSaveDraft: computed(() => true),
      canSubmit: computed(() => true),
      submissionLimitInfo: computed(() => null),
      showSubmissionForm: computed(() => true),
      showSubmittedContent: computed(() => false),
      isOverdue: computed(() => false),
      statusTagType: computed(() => "info"),
      statusText: computed(() => "待提交"),
      loadData: vi.fn().mockResolvedValue(undefined),
      handleSubmit: vi.fn(),
      handleSaveDraft: vi.fn(),
      handleDelete: vi.fn(),
      checkAndStartPolling: vi.fn(),
      stopPolling: vi.fn(),
    }),
    useSubmissionUtils: () => ({ formatDate: (value: string) => value }),
  };
});

import SubmissionWorkspace from "../index.vue";

describe("SubmissionWorkspace", () => {
  it("没有提交记录时页头显示待提交而不是待批改", () => {
    const wrapper = shallowMount(SubmissionWorkspace, {
      global: {
        stubs: {
          "el-button": { template: "<button><slot /></button>" },
          "el-alert": true,
          "el-tabs": { template: "<div><slot /></div>" },
          "el-tab-pane": { template: "<section><slot name='label' /></section>" },
          "el-badge": true,
          "el-icon": { template: "<i><slot /></i>" },
        },
        directives: { loading: () => undefined },
      },
    });

    const statusText = wrapper.get(".submission-hero__statuses").text();
    expect(statusText).toContain("待提交");
    expect(statusText).not.toContain("待批改");
  });
});
