import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import ReviewResults from "../ReviewResults.vue";

const mountReview = (props: Record<string, unknown>) =>
  mount(ReviewResults, {
    props,
    global: {
      stubs: {
        "el-card": { template: "<section><slot /></section>" },
        "el-icon": { template: "<i><slot /></i>" },
        "el-alert": { template: "<aside><slot /></aside>" },
        "el-empty": { template: "<div><slot name='description' /></div>" },
        "el-tab-pane": {
          template:
            "<section><slot name='label' /><slot /></section>",
        },
        "el-tabs": { template: "<div><slot /></div>" },
        "el-tag": { template: "<span><slot /></span>" },
      },
    },
  });

describe("ReviewResults", () => {
  it("尚未提交时显示明确的评价空状态", () => {
    const wrapper = mountReview({
      aiReview: null,
      teacherReview: null,
      submissionStatus: undefined,
    });

    expect(
      wrapper.get('[data-testid="no-submission-review"]').text()
    ).toContain("提交作业后");
  });

  it("草稿尚未正式提交时仍显示提交后评价提示", () => {
    const wrapper = mountReview({
      aiReview: null,
      teacherReview: null,
      submissionStatus: "draft",
    });

    expect(
      wrapper.get('[data-testid="no-submission-review"]').text()
    ).toContain("提交作业后");
  });

  it("未配置 AI 规则的已提交作业显示等待教师批改", () => {
    const wrapper = mountReview({
      aiReview: null,
      teacherReview: null,
      submissionStatus: "submitted",
      assignment: {
        status: "published",
        dueDate: "2099-08-05T18:00:00",
        aiRule: null,
      },
    });

    expect(wrapper.text()).toContain("等待教师批改");
    expect(wrapper.text()).not.toContain("评价进行中");
  });

  it("评价为零分时仍显示分数标签", () => {
    const wrapper = mountReview({
      aiReview: {
        content: "需要继续改进",
        score: 0,
        reviewedAt: "2026-08-01T12:00:00",
      },
      teacherReview: null,
      submissionStatus: "ai_reviewed",
      assignment: {
        status: "published",
        dueDate: "2099-08-05T18:00:00",
        aiRule: { prompt: "请评分" },
      },
    });

    expect(wrapper.text()).toContain("0分");
  });
});
