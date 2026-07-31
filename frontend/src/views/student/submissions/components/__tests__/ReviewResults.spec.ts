import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import ReviewResults from "../ReviewResults.vue";

describe("ReviewResults", () => {
  it("尚未提交时显示明确的评价空状态", () => {
    const wrapper = mount(ReviewResults, {
      props: {
        aiReview: null,
        teacherReview: null,
        submissionStatus: undefined,
      },
      global: {
        stubs: {
          "el-card": { template: "<section><slot /></section>" },
          "el-icon": { template: "<i><slot /></i>" },
          "el-alert": true,
          "el-empty": true,
          "el-tab-pane": true,
          "el-tabs": true,
          "el-tag": true,
        },
      },
    });

    expect(
      wrapper.get('[data-testid="no-submission-review"]').text()
    ).toContain("提交作业后");
  });
});
