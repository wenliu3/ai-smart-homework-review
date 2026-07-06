import request from "@/utils/request";

// 附件接口
export interface Attachment {
  fileName: string;
  fileUrl: string;
  fileSize: number;
  fileType: string;
}

// 提交作业请求参数
export interface SubmitAssignmentParams {
  assignmentId: string;
  classId: string;
  content: string;
  attachments?: Attachment[];
  isDraft?: boolean;
}

// 作业信息
export interface Assignment {
  id: string;
  title: string;
  description: string;
  dueDate: string;
  maxScore: number;
  teacherName: string; // 教师姓名
  aiRule: any; // AI规则内容
  status: "draft" | "published" | "terminated"; // 作业状态
  terminatedReason?: string; // 终止原因
}

// 提交信息
export interface Submission {
  id: string;
  content: string;
  attachments: Attachment[];
  status: "draft" | "submitted" | "ai_reviewed" | "teacher_reviewed";
  submittedAt: string | null;
  updatedAt: string;
  createdAt: string;
  isDraft: boolean;
  submissionCount: number; // 提交次数
}

// AI批改信息
export interface AiReview {
  content: string;
  score: number;
  reviewedAt: string;
  aiReviewMetadata?: {
    error?: string;
    errorTime?: string;
    modelUsed?: string;
  };
}

// 教师批改信息
export interface TeacherReview {
  content: string;
  score: number;
  reviewedAt: string;
}

// 我的作业提交详情
export interface MySubmissionDetail {
  assignment: Assignment;
  submission: Submission | null;
  aiReview: AiReview | null;
  teacherReview: TeacherReview | null;
}

// 提交作业响应
export interface SubmitAssignmentResponse {
  id: string;
  assignmentId: string;
  studentId: string;
  status: string;
  submittedAt: string | null;
  updatedAt: string;
  isDraft: boolean;
  submissionCount: number; // 提交次数
}

// 删除提交参数
export interface DeleteSubmissionParams {
  submissionId: string;
}

/**
 * 学生作业提交API服务
 */
export class SubmissionsApi {
  /**
   * 提交作业（统一接口）
   * @param params 提交参数
   * @returns 提交结果
   */
  static async submit(params: SubmitAssignmentParams) {
    console.log("💾 发起提交请求，URL:", "/students/submissions/submit");
    console.log("📤 提交参数:", params);

    const result = await request<SubmitAssignmentResponse>({
      url: "/students/submissions/submit",
      method: "POST",
      data: params,
    });

    console.log("✅ 提交响应结果:", result);
    return result;
  }

  /**
   * 查看我的作业提交
   * @param assignmentId 作业ID
   * @returns 作业提交详情
   */
  static async getMySubmission(assignmentId: string) {
    console.log(
      "🔍 发起查询请求，URL:",
      `/students/submissions/my/${assignmentId}`
    );

    const result = await request<MySubmissionDetail>({
      url: `/students/submissions/my/${assignmentId}`,
      method: "GET",
    });

    console.log("📥 查询响应结果:", result);
    return result;
  }

  /**
   * 删除作业提交（仅草稿）
   * @param params 删除参数
   * @returns 删除结果
   */
  static async deleteSubmission(params: DeleteSubmissionParams) {
    return request<{ success: boolean; message: string; resourceId: string }>({
      url: "/students/submissions/delete",
      method: "POST",
      data: params,
    });
  }

  /**
   * 保存草稿
   * @param params 保存参数
   * @returns 保存结果
   */
  static async saveDraft(params: Omit<SubmitAssignmentParams, "isDraft">) {
    return this.submit({ ...params, isDraft: true });
  }

  /**
   * 正式提交作业
   * @param params 提交参数
   * @returns 提交结果
   */
  static async submitFinal(params: Omit<SubmitAssignmentParams, "isDraft">) {
    return this.submit({ ...params, isDraft: false });
  }
}

export default SubmissionsApi;
