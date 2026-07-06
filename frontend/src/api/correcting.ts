import request from "@/utils/request";

// 作业提交记录接口
export interface SubmissionRecord {
  _id: string;
  assignmentId: string;
  studentId: string;
  studentName: string;
  studentNumber: string;
  classId: string;
  className: string;
  content: string;
  status: "draft" | "submitted" | "ai_reviewed" | "teacher_reviewed";
  submittedAt?: string;
  aiScore?: number;
  aiReviewContent?: string;
  teacherScore?: number;
  teacherReviewContent?: string;
  teacherReviewedAt?: string;
  createdAt: string;
  updatedAt: string;
}

// 查询参数接口 - 匹配后端FindSubmissionsDto
export interface SubmissionQueryParams {
  assignmentId?: string; // 可选参数，不传则查询所有作业提交
  page?: number;
  limit?: number;
  classId?: string;
  status?: string; // 统一的作业状态字段
  studentName?: string;
  studentNumber?: string; // 新增学号搜索
  minScore?: number;
  maxScore?: number;
  sortBy?: "submittedAt" | "teacherScore" | "aiScore" | "studentName";
  sortOrder?: "asc" | "desc";
}

// 列表响应接口（注意：request拦截器已经提取了data部分）
export interface SubmissionListResponse {
  items: SubmissionRecord[];
  total: number;
  page: number;
  pageSize: number;
}

/**
 * 获取作业提交列表（教师批改用）
 */
export function getSubmissionList(
  params: SubmissionQueryParams
): Promise<SubmissionListResponse> {
  return request({
    url: "/teachers/submissions/list",
    method: "get",
    params,
  });
}

/**
 * 获取作业提交详情
 */
export function getSubmissionDetail(
  submissionId: string
): Promise<SubmissionRecord> {
  return request({
    url: `/teachers/submissions/detail/${submissionId}`,
    method: "get",
  });
}

/**
 * 教师批改作业
 */
export function submitTeacherReview(params: {
  submissionId: string;
  teacherReviewContent: string;
  teacherScore: number;
}): Promise<any> {
  return request({
    url: "/teachers/submissions/review",
    method: "post",
    data: params,
  });
}
