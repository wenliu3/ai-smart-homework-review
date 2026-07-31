import { describe, expect, it } from "vitest";

import {
  getSubmissionWorkspaceState,
  isFormalSubmissionStatus,
} from "../submissionLifecycle";

describe("submissionLifecycle", () => {
  it("returns the assignment-first state when no submission exists", () => {
    expect(getSubmissionWorkspaceState(undefined, false)).toEqual({
      hasFormalSubmission: false,
      showSubmissionStep: true,
      submissionStepLabel: "提交作业",
      showResultsStep: false,
      resultsStepNumber: null,
      defaultTab: "assignment",
    });
  });

  it("resumes a draft from the submission tab", () => {
    expect(getSubmissionWorkspaceState("draft", false)).toMatchObject({
      hasFormalSubmission: false,
      showSubmissionStep: true,
      submissionStepLabel: "继续提交",
      showResultsStep: false,
      resultsStepNumber: null,
      defaultTab: "submission",
    });
  });

  it("shows results after a non-resubmitted formal submission", () => {
    expect(getSubmissionWorkspaceState("submitted", false)).toEqual({
      hasFormalSubmission: true,
      showSubmissionStep: false,
      submissionStepLabel: "提交作业",
      showResultsStep: true,
      resultsStepNumber: 2,
      defaultTab: "results",
    });
  });

  it("shows a resubmission step before reviewed results", () => {
    expect(getSubmissionWorkspaceState("ai_reviewed", true)).toMatchObject({
      hasFormalSubmission: true,
      showSubmissionStep: true,
      submissionStepLabel: "重新提交",
      showResultsStep: true,
      resultsStepNumber: 3,
      defaultTab: "results",
    });
  });

  it("defaults teacher-reviewed submissions to results", () => {
    expect(getSubmissionWorkspaceState("teacher_reviewed", false).defaultTab).toBe(
      "results"
    );
  });

  it("recognizes only formal submission statuses", () => {
    expect(isFormalSubmissionStatus("submitted")).toBe(true);
    expect(isFormalSubmissionStatus("ai_reviewed")).toBe(true);
    expect(isFormalSubmissionStatus("teacher_reviewed")).toBe(true);
    expect(isFormalSubmissionStatus(undefined)).toBe(false);
    expect(isFormalSubmissionStatus("draft")).toBe(false);
  });
});
