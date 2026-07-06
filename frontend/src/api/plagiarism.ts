import request from "@/utils/request";

/** 查重结果单项 */
export interface PlagiarismResultItem {
  submissionId: string;
  studentName: string;
  studentNumber: string;
  rate: number;
  phraseRate: number;
  topicRate: number;
  status: string;
  matchName: string;
  matchId: string;
  matchSubmissionId: string | null;
}

/** 跳过的文件 */
export interface SkippedItem {
  fileName?: string;
  studentName?: string;
  studentNumber?: string;
  reason: string;
}

/** 查重结果 */
export interface AdhocCheckResult {
  checkId: string;
  results: PlagiarismResultItem[];
  skipped: SkippedItem[];
  total: number;
  suspectCount: number;
  passRate: number;
  message?: string;
}

/**
 * 临时查重 — 上传多个文件进行查重
 */
export function adhocCheck(files: File[]): Promise<AdhocCheckResult> {
  const formData = new FormData();
  files.forEach((f) => formData.append("files", f));
  return request({
    url: "/plagiarism/adhoc-check",
    method: "post",
    data: formData,
    timeout: 120000,
    // 不要手动设 Content-Type，让浏览器自动设置 multipart/form-data; boundary=xxx
    headers: { "Content-Type": undefined as any },
  });
}

/**
 * 下载查重报告 Excel
 */
export function downloadReportUrl(checkId: string): string {
  const token = localStorage.getItem("token");
  return `/api/plagiarism/${checkId}/report`;
}
