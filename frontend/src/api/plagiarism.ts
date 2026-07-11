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
  // 代码维度查重结果
  codeRate: number | null;
  codeStatus: string;
  codeMatchName: string;
  codeMatchId: string;
  // 图片维度查重结果
  imageRate: number | null;
  imageStatus: string;
  imageMatchName: string;
  imageMatchId: string;
  matchedImageCount: number;
  totalImageCount?: number;   // 该学生参与比对的有效图片总数
  lowConfidence?: boolean;   // 单张图片命中时置信度低
  // 疑似抄袭原因（如 "文字+图片"）
  suspectReason?: string;
  // 命中片段样例
  matchedSnippets?: string[];
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
  // 代码查重维度
  codeCheckEnabled?: boolean;
  codeSuspectCount?: number;
  // 图片查重维度
  imageCheckEnabled?: boolean;
  imageSuspectCount?: number;
  templateFiltered?: boolean;
  codeTemplateFiltered?: boolean;
  imageTemplateFiltered?: boolean;
  textResult?: {
    total: number;
    suspectCount: number;
    autoCommonFiltered: boolean;
  };
  codeResult?: {
    total: number;
    suspectCount: number;
  } | null;
  imageResult?: {
    total: number;
    suspectCount: number;
  } | null;
}

/** 查重参数配置 */
export interface PlagiarismConfig {
  passRate?: number;       // 合格阈值(%)
  phraseWeight?: number;   // 片段重合度权重
  topicWeight?: number;    // 主题相似度权重
}

/**
 * 临时查重 — 上传多个文件进行查重
 * @param files 学生作业文件
 * @param templateFile 可选，任务书/起始代码模板
 * @param config 可选，查重参数配置（不传则使用后端默认值）
 */
export function adhocCheck(
  files: File[],
  templateFile?: File | null,
  config?: PlagiarismConfig,
): Promise<AdhocCheckResult> {
  const formData = new FormData();
  files.forEach((f) => formData.append("files", f));
  if (templateFile) {
    formData.append("template_file", templateFile);
  }
  if (config?.passRate != null) formData.append("passRate", String(config.passRate));
  if (config?.phraseWeight != null) formData.append("phraseWeight", String(config.phraseWeight));
  if (config?.topicWeight != null) formData.append("topicWeight", String(config.topicWeight));
  return request({
    url: "/plagiarism/adhoc-check",
    method: "post",
    data: formData,
    timeout: 120000,
    headers: { "Content-Type": undefined as any },
  });
}

/**
 * 下载查重报告 Excel
 */
export function downloadReport(checkId: string): Promise<Blob> {
  return request({
    url: `/plagiarism/${checkId}/report`,
    method: "get",
    responseType: "blob",
    timeout: 60000,
  });
}
