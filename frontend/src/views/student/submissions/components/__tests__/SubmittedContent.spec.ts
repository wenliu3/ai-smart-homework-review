import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import type { Submission } from "@/api/submissions";
import SubmittedContent from "../SubmittedContent.vue";

const submission: Submission = {
  id: "8",
  content: "<p>已提交正文</p>",
  attachments: [],
  wordCount: 6,
  status: "submitted",
  submittedAt: "2026-08-01T12:00:00",
  updatedAt: "2026-08-01T12:00:00",
  createdAt: "2026-08-01T12:00:00",
  isDraft: false,
  submissionCount: 2,
};

const mountContent = (canResubmit: boolean) =>
  mount(SubmittedContent, {
    props: { submission, canResubmit },
    global: {
      stubs: {
        "el-button": {
          template: "<button><slot /></button>",
        },
        AssignmentAttachmentList: true,
      },
    },
  });

describe("SubmittedContent", () => {
  it("shows submission metadata and emits an explicit resubmission request", async () => {
    const wrapper = mountContent(true);

    expect(wrapper.text()).toContain("第 2 次提交");
    expect(wrapper.text()).toContain("重新提交");

    await wrapper.get('[data-testid="resubmit-button"]').trigger("click");
    expect(wrapper.emitted("resubmit")).toHaveLength(1);
  });

  it("keeps reviewed or otherwise locked submissions read-only", () => {
    const wrapper = mountContent(false);

    expect(wrapper.find('[data-testid="resubmit-button"]').exists()).toBe(
      false
    );
  });
});
