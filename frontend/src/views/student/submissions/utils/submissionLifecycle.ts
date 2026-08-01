import type { Submission } from "@/api/submissions";

export type SubmissionStatus = Submission["status"] | null | undefined;

export type SubmissionTab = "assignment" | "submission" | "results";

export interface SubmissionWorkspaceState {
  hasFormalSubmission: boolean;
  showSubmissionStep: boolean;
  submissionStepLabel: "提交作业" | "继续提交" | "重新提交";
  showResultsStep: boolean;
  resultsStepNumber: 2 | 3 | null;
  defaultTab: SubmissionTab;
}

export function isFormalSubmissionStatus(status: SubmissionStatus): boolean {
  return (
    status === "submitted" ||
    status === "ai_reviewed" ||
    status === "teacher_reviewed"
  );
}

export function getSubmissionWorkspaceState(
  status: SubmissionStatus,
  isResubmitting: boolean
): SubmissionWorkspaceState {
  const hasFormalSubmission = isFormalSubmissionStatus(status);

  if (!hasFormalSubmission) {
    const isDraft = status === "draft";

    return {
      hasFormalSubmission: false,
      showSubmissionStep: true,
      submissionStepLabel: isDraft ? "继续提交" : "提交作业",
      showResultsStep: false,
      resultsStepNumber: null,
      defaultTab: isDraft ? "submission" : "assignment",
    };
  }

  return {
    hasFormalSubmission: true,
    showSubmissionStep: isResubmitting,
    submissionStepLabel: "重新提交",
    showResultsStep: true,
    resultsStepNumber: isResubmitting ? 3 : 2,
    defaultTab: "results",
  };
}
