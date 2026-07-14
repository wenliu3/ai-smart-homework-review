import request from "@/utils/request";

// 作业状态枚举
export enum AssignmentStatus {
  DRAFT = "draft",
  PUBLISHED = "published",
  TERMINATED = "terminated",
}

// 作业基础信息
export interface Assignment {
  id: string;
  title: string;
  description: string;
  teacherId: string;
  teacherName: string;
  classes: Array<{
    id: string;
    name: string;
  }>;
  startDate: string;
  endDate: string;
  status: AssignmentStatus;
  terminatedReason?: string;
  isExpired: boolean;
  allowAttachments?: boolean;
  attachments?: Array<{
    fileName: string;
    fileUrl: string;
    fileSize: number;
    fileType: string;
  }>;
  createdAt: string;
  updatedAt: string;
}

// 作业列表项（包含统计信息）
export interface AssignmentListItem extends Assignment {
  submissionCount: number;
  totalSubmissions: number;
  reviewedSubmissions: number;
  pendingSubmissions: number;
  totalStudents: number;
}

// 作业详情（教师端）
export interface AssignmentDetail extends Assignment {
  aiRule?: any;
  totalStudents?: number;
  submissionStats: {
    totalSubmissions: number;
    reviewedSubmissions: number;
    pendingSubmissions: number;
    draftSubmissions: number;
    aiReviewed: number;
    teacherReviewed: number;
  };
}

// 学生提交记录（精简版）
export interface StudentSubmissionSummary {
  _id: string;
  studentId: string;
  studentName: string;
  studentNumber: string;
  classId: string;
  className: string;
  status: "draft" | "submitted" | "ai_reviewed" | "teacher_reviewed";
  submittedAt?: string;
  aiScore?: number;
  teacherScore?: number;
  teacherReviewedAt?: string;
  contentPreview?: string;
  wordCount?: number;
}

// 作业详情页面响应（包含提交列表）
export interface AssignmentWithSubmissions {
  assignment: AssignmentDetail;
  submissions: {
    items: StudentSubmissionSummary[];
    total: number;
    page: number;
    limit: number;
    totalPages: number;
  };
}

// 查询参数
export interface AssignmentQueryParams {
  page?: number;
  pageSize?: number;
  title?: string;
  status?: AssignmentStatus;
  teacherName?: string;
  className?: string;
  startDate?: string;
  endDate?: string;
  sortBy?: string;
  sortOrder?: "asc" | "desc";
}

// 作业详情查询参数
export interface AssignmentSubmissionsQueryParams {
  classId?: string;
  studentName?: string;
  studentNumber?: string;
  submissionStatus?: "draft" | "submitted" | "ai_reviewed" | "teacher_reviewed";
  gradingStatus?: "pending" | "ai_reviewed" | "teacher_reviewed";
  page?: number;
  limit?: number;
}

// 列表响应
export interface AssignmentListResponse {
  items: AssignmentListItem[];
  total: number;
  page: number;
  pageSize: number;
}

// 创建作业参数
export interface CreateAssignmentParams {
  title: string;
  description: string;
  classes: string[];
  startDate: string;
  endDate: string;
  aiRule?: any;
  allowAttachments?: boolean;
  attachments?: Array<{
    fileName: string;
    fileUrl: string;
    fileSize: number;
    fileType: string;
  }>;
}

// 更新作业参数
export interface UpdateAssignmentParams
  extends Partial<CreateAssignmentParams> {
  status?: AssignmentStatus;
  terminatedReason?: string;
}

/**
 * 获取作业列表（教师端）
 */
export function getAssignmentList(
  params: AssignmentQueryParams
): Promise<AssignmentListResponse> {
  return request({
    url: "/teacher/assignments",
    method: "get",
    params,
  });
}

/**
 * 获取作业详情（教师端）
 */
export function getAssignmentDetail(id: string): Promise<AssignmentDetail> {
  return request({
    url: `/teacher/assignments/${id}`,
    method: "get",
  });
}

/**
 * 获取作业的学生提交情况（教师端）- 包含所有学生
 */
export function getAssignmentStudents(
  id: string,
  params?: AssignmentSubmissionsQueryParams
): Promise<any> {
  return request({
    url: `/teacher/assignments/${id}/students`,
    method: "get",
    params,
  });
}

/**
 * 创建作业
 */
export function createAssignment(
  params: CreateAssignmentParams
): Promise<Assignment> {
  return request({
    url: "/teacher/assignments",
    method: "post",
    data: params,
  });
}

/**
 * 更新作业
 */
export function updateAssignment(
  id: string,
  params: UpdateAssignmentParams
): Promise<Assignment> {
  return request({
    url: `/teacher/assignments/${id}/update`,
    method: "post",
    data: params,
  });
}

/**
 * 发布作业
 */
export function publishAssignment(id: string): Promise<Assignment> {
  return request({
    url: `/teacher/assignments/${id}/status`,
    method: "post",
    data: { status: AssignmentStatus.PUBLISHED },
  });
}

/**
 * 终止作业
 */
export function terminateAssignment(
  id: string,
  reason?: string
): Promise<Assignment> {
  return request({
    url: `/teacher/assignments/${id}/status`,
    method: "post",
    data: {
      status: AssignmentStatus.TERMINATED,
      terminatedReason: reason,
    },
  });
}

/**
 * 删除作业
 */
export function deleteAssignment(id: string): Promise<void> {
  return request({
    url: `/teacher/assignments/${id}/delete`,
    method: "post",
  });
}

/**
 * 获取我的作业列表（学生端）
 */
export function getMyAssignments(params?: any): Promise<any> {
  return request({
    url: "/student/assignments",
    method: "get",
    params,
  });
}

/**
 * 获取我的作业统计（学生端）
 */
export function getMyAssignmentStatistics(classId?: string): Promise<any> {
  return request({
    url: "/student/assignments/statistics",
    method: "get",
    params: classId ? { classId } : undefined,
  });
}

/**
 * 获取学生作业详情（学生端）
 */
export function getStudentAssignment(
  assignmentId: string,
  classId?: string
): Promise<any> {
  return request({
    url: `/student/assignments/${assignmentId}`,
    method: "get",
    params: classId ? { classId } : undefined,
  });
}

/**
 * 更新作业状态（兼容函数）
 */
export function updateAssignmentStatus(
  id: string,
  params: { status: AssignmentStatus; terminatedReason?: string }
) {
  if (params.status === AssignmentStatus.PUBLISHED) {
    return publishAssignment(id);
  } else if (params.status === AssignmentStatus.TERMINATED) {
    return terminateAssignment(id, params.terminatedReason);
  }
  return updateAssignment(id, params);
}

/**
 * 获取作业详情（兼容函数）
 */
export function getAssignment(id: string): Promise<Assignment> {
  return getAssignmentDetail(id);
}

// 兼容原有的 assignmentApi 对象导出
export const assignmentApi = {
  getAssignments: getAssignmentList,
  getAssignment: getAssignmentDetail,
  createAssignment,
  updateAssignment,
  updateAssignmentStatus: (
    id: string,
    params: { status: AssignmentStatus; terminatedReason?: string }
  ) => {
    if (params.status === AssignmentStatus.PUBLISHED) {
      return publishAssignment(id);
    } else if (params.status === AssignmentStatus.TERMINATED) {
      return terminateAssignment(id, params.terminatedReason);
    }
    return updateAssignment(id, params);
  },
  deleteAssignment,
};

// ===================== 作业查重 =====================

/** 查重结果单项 */
export interface PlagiarismResultItem {
  submissionId: string;
  studentName: string;
  studentNumber: string;
  rate: number;           // 综合重复率(%)
  phraseRate: number;     // 片段重合度(%)
  topicRate: number;      // 主题相似度(%)
  status: string;         // 合格 / 不合格(疑似抄袭)
  matchName: string;      // 最相似对象姓名
  matchId: string;        // 最相似对象学号
  matchSubmissionId: string | null;
  // 代码维度查重结果
  codeRate?: number | null;      // 代码重合度(%)
  codeStatus?: string;           // 代码判定结果
  codeMatchName?: string;       // 代码最相似对象
  codeMatchId?: string;         // 代码对方学号
  // 图片维度查重结果
  imageRate?: number | null;     // 图片重合度(%)
  imageStatus?: string;          // 图片判定结果
  imageMatchName?: string;      // 图片最相似对象
  imageMatchId?: string;        // 图片对方学号
  matchedImageCount?: number;   // 疑似复制图片数
  totalImageCount?: number;     // 该学生参与比对的有效图片总数
  lowConfidence?: boolean;     // 单张图片命中时置信度低
  suspectReason?: string;       // 疑似原因（如 "文字+图片"）
  matchedSnippets?: string[];   // 命中片段样例
}

/** 查重结果 */
export interface PlagiarismResult {
  results: PlagiarismResultItem[];
  skipped: Array<{ studentName: string; studentNumber: string; reason: string }>;
  total: number;
  suspectCount: number;
  passRate: number;
  message?: string;
  // 代码查重维度
  codeCheckEnabled?: boolean;
  codeSuspectCount?: number;
  codePassRate?: number | null;
  // 图片查重维度
  imageCheckEnabled?: boolean;
  imageSuspectCount?: number;
  templateFiltered?: boolean;
  autoCommonFiltered?: boolean;
}

/** 查重参数配置 */
export interface PlagiarismConfig {
  passRate?: number;       // 合格阈值(%)
  phraseWeight?: number;   // 片段重合度权重
  topicWeight?: number;    // 主题相似度权重
}

/**
 * 作业查重 — 对该作业所有学生提交进行查重比对
 * @param assignmentId 作业ID
 * @param templateFile 可选，任务书/起始代码模板
 * @param config 可选，查重参数配置（不传则使用后端默认值）
 */
export function checkPlagiarism(
  assignmentId: string,
  templateFile?: File | null,
  config?: PlagiarismConfig,
): Promise<PlagiarismResult> {
  const hasExtra = templateFile || config;
  if (hasExtra) {
    const formData = new FormData();
    if (templateFile) {
      formData.append("template_file", templateFile);
    }
    if (config?.passRate != null) formData.append("passRate", String(config.passRate));
    if (config?.phraseWeight != null) formData.append("phraseWeight", String(config.phraseWeight));
    if (config?.topicWeight != null) formData.append("topicWeight", String(config.topicWeight));
    return request({
      url: `/teacher/assignments/${assignmentId}/plagiarism`,
      method: "post",
      data: formData,
      timeout: 300000,
      headers: { "Content-Type": undefined as any },
    });
  }
  return request({
    url: `/teacher/assignments/${assignmentId}/plagiarism`,
    method: "post",
    timeout: 120000,
  });
}

/** 文件信息 */
export interface CompareFileInfo {
  fileUrl: string;
  ext: string;
  fileName: string;
}

/** 对比预览结果 */
export interface CompareResult {
  studentA: { name: string; number: string };
  studentB: { name: string; number: string };
  fileA: CompareFileInfo | null;
  fileB: CompareFileInfo | null;
  pdfUrlA: string | null;   // 标黄 PDF（后端生成，优先用它预览）
  pdfUrlB: string | null;
  contentHtmlA: string;
  contentHtmlB: string;
  snippets: string[];
}

/**
 * 对比预览 — 获取两份提交的全文和命中片段
 */
export function compareSubmissions(submissionId: string, matchSubmissionId: string): Promise<CompareResult> {
  return request({
    url: "/teacher/submissions/compare",
    method: "get",
    params: { submission_id: submissionId, match_submission_id: matchSubmissionId },
    timeout: 60000,
  });
}

/**
 * AI 建议 — 结合查重结果和大模型，针对学生作业提出分析和建议
 * @param submissionId 提交记录ID
 * @param plagiarismInfo 查重结果数据（rate/phraseRate/topicRate/status/matchName等）
 * @param matchSubmissionId 可选，对比模式下对方提交记录ID
 */
export function getAiSuggestion(
  submissionId: string,
  plagiarismInfo: Record<string, any>,
  matchSubmissionId?: string,
): Promise<{ suggestion: string }> {
  return request({
    url: `/teacher/submissions/${submissionId}/ai-suggestion`,
    method: "post",
    data: { plagiarismInfo, matchSubmissionId },
    timeout: 120000,
  });
}
