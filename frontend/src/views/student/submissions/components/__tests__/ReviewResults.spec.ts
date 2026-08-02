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

  it("批改 Run 失败时显示稳定失败终态文案", () => {
    const failedWrapper = mountReview({
      aiReview: null,
      teacherReview: null,
      submissionStatus: "submitted",
      assignment: {
        status: "published",
        dueDate: "2099-08-05T18:00:00",
        aiRule: { prompt: "请评分" },
      },
      gradingRun: {
        status: "failed",
        errorCode: "AGENT_GRADING_TIMEOUT",
        finalOutput: null,
      },
    });

    expect(failedWrapper.text()).toContain("AI 批改失败");
    expect(failedWrapper.text()).toContain("等待教师人工批改");
    expect(failedWrapper.text()).not.toContain("AI 智能评价中");
    expect(failedWrapper.text()).not.toContain("AGENT_GRADING_TIMEOUT");
  });

  it("等待教师批改与 failed run 并存时标题与副标题保持一致", () => {
    // 过期作业 → aiSupported=false（waitingForTeacherOnly 为 true）；
    // 历史 failed run 同时存在 → 标题应优先显示失败终态，副标题不得回落到“未启用 AI 评价”
    const wrapper = mountReview({
      aiReview: null,
      teacherReview: null,
      submissionStatus: "submitted",
      assignment: {
        status: "published",
        dueDate: "2000-01-01T00:00:00",
        aiRule: { prompt: "请评分" },
      },
      gradingRun: {
        status: "failed",
        errorCode: "AGENT_GRADING_TIMEOUT",
        finalOutput: null,
      },
    });

    expect(wrapper.text()).toContain("AI 批改失败");
    expect(wrapper.text()).toContain("AI 批改出现问题，教师批改后将在这里显示反馈");
    expect(wrapper.text()).not.toContain("本作业未启用 AI 评价");
  });

  it("批改 Run 取消时显示已取消终态文案", () => {
    const cancelledWrapper = mountReview({
      aiReview: null,
      teacherReview: null,
      submissionStatus: "submitted",
      assignment: {
        status: "published",
        dueDate: "2099-08-05T18:00:00",
        aiRule: { prompt: "请评分" },
      },
      gradingRun: {
        status: "cancelled",
        errorCode: "AGENT_RUN_CANCELLED",
        finalOutput: null,
      },
    });

    expect(cancelledWrapper.text()).toContain("AI 批改已取消");
    expect(cancelledWrapper.text()).not.toContain("AI 智能评价中");
    expect(cancelledWrapper.text()).not.toContain("AGENT_RUN_CANCELLED");
  });

  it("批改 Run 已完成但无 AI/教师结果时显示等待人工批改（降级终态）", () => {
    const wrapper = mountReview({
      aiReview: null,
      teacherReview: null,
      submissionStatus: "submitted",
      assignment: {
        status: "published",
        dueDate: "2099-08-05T18:00:00",
        aiRule: { prompt: "请评分" },
      },
      gradingRun: {
        status: "completed",
        errorCode: null,
        finalOutput: "AI 批改未通过结构化校验，已转教师人工批改。",
      },
      isPolling: false,
    });

    expect(wrapper.text()).toContain("等待教师人工批改");
    expect(wrapper.text()).toContain("AI 批改未生成有效评分，教师批改后将在这里显示反馈");
    expect(wrapper.text()).not.toContain("AI 智能评价中");
    expect(wrapper.text()).not.toContain("暂未取得最终状态");
  });

  it("轮询进行中仍显示 AI 智能评价中", () => {
    const wrapper = mountReview({
      aiReview: null,
      teacherReview: null,
      submissionStatus: "submitted",
      assignment: {
        status: "published",
        dueDate: "2099-08-05T18:00:00",
        aiRule: { prompt: "请评分" },
      },
      gradingRun: {
        status: "running",
        errorCode: null,
        finalOutput: null,
      },
      isPolling: true,
      pollingCount: 3,
    });

    expect(wrapper.text()).toContain("AI 智能评价中");
  });

  it("轮询停止且无终态时显示暂未取得最终状态", () => {
    const wrapper = mountReview({
      aiReview: null,
      teacherReview: null,
      submissionStatus: "submitted",
      assignment: {
        status: "published",
        dueDate: "2099-08-05T18:00:00",
        aiRule: { prompt: "请评分" },
      },
      gradingRun: {
        status: "running",
        errorCode: null,
        finalOutput: null,
      },
      isPolling: false,
    });

    expect(wrapper.text()).toContain("暂未取得最终状态，请稍后刷新");
    expect(wrapper.text()).not.toContain("AI 智能评价中");
  });
});
