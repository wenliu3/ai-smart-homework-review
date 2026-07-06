import request from "@/utils/request";

// Dashboard API 接口定义
export interface DashboardApi {
  // 管理员看板
  getAdminOverview(refresh?: boolean): Promise<AdminOverviewResponse>;
  getAiModelStats(refresh?: boolean): Promise<AiModelStatsResponse>;
  getRecentUsers(limit?: number): Promise<RecentUsersResponse>;

  // 教师看板
  getTeacherStats(refresh?: boolean): Promise<TeacherStatsResponse>;
  getTeacherPendingTasks(): Promise<TeacherPendingTasksResponse>;

  // 学生看板
  getStudentStats(refresh?: boolean): Promise<StudentStatsResponse>;
}

// 响应数据类型定义
export interface AdminOverviewResponse {
  totalUsers: number;
  totalClasses: number;
  totalAssignments: number;
  totalSubmissions: number;
  aiModelCount: number;
  userRoleDistribution: RoleDistribution[];
  classStatusDistribution: StatusDistribution[];
  submissionStatusDistribution: StatusDistribution[];
  lastUpdated: string;
}

// 基础分布统计接口
export interface DistributionStat {
  name: string;
  count: number;
  percentage?: number;
}

export interface RoleDistribution {
  role: string;
  count: number;
  percentage: number;
}

export interface StatusDistribution {
  status: string;
  count: number;
  percentage: number;
}

export interface AiModelStatsResponse {
  deepseek?: {
    isOnline: boolean;
    balance: string;
    balanceCurrency?: string;
    totalUsage: number;
    totalTokens: number;
    todayUsage: number;
    lastBalanceCheck?: string;
  };
  mimo?: {
    isOnline: boolean;
    balance: number;
    totalUsage: number;
    totalTokens: number;
    todayUsage: number;
    lastBalanceCheck?: string;
  };
}

export interface RecentUsersResponse {
  users: Array<{
    id: string;
    name: string;
    role: string;
    email: string;
    createdAt: string;
    status: string;
  }>;
}

export interface TeacherStatsResponse {
  myClasses: number;
  myAssignments: number;
  pendingReviews: number;
  totalStudents: number;
  classSubmissionStats: Array<{
    classId: string;
    className: string;
    totalStudents: number;
    submittedCount: number;
    submissionRate: number;
  }>;
  assignmentStatusDistribution: StatusDistribution[];
  aiReviewStats: {
    todayReviews: number;
    totalReviews: number;
    failedReviews: number;
    pendingReviews: number;
  };
  studentScoreAnalysis: {
    avgAiScore: number;
    avgTeacherScore: number;
    scoreDifference: number;
    excellentRate: number;
    passRate: number;
  };
}

export interface TeacherPendingTasksResponse {
  assignments: Array<{
    id: string;
    title: string;
    classCount: number;
    submissionRate: number;
    status: string;
    endDate: string;
  }>;
  submissions: Array<{
    id: string;
    studentName: string;
    assignmentTitle: string;
    status: string;
    submittedAt: string;
    aiScore?: number;
  }>;
}

export interface StudentStatsResponse {
  completedSubmissions: number;
  averageScore: number;
  joinedClasses: number;
  onTimeRate: number;
  pendingAssignments: number;
  submissionStatusStats: StatusDistribution[];
  performanceAnalysis: {
    excellentCount: number;
    goodCount: number;
    passCount: number;
    classRanking: string;
    perfectScoreCount: number;
  };
  pendingAssignmentsList: Array<{
    assignmentId: string;
    title: string;
    classId: string;
    className: string;
    endDate: string;
    status: "not_started" | "draft";
  }>;
  recentSubmissions: Array<{
    id: string;
    assignmentTitle: string;
    aiScore?: number;
    teacherScore?: number;
    submittedAt: string;
    status: string;
  }>;
}

/**
 * 获取管理员看板概览统计
 */
export function getAdminOverview(
  refresh = false
): Promise<AdminOverviewResponse> {
  const params = refresh ? { refresh: true } : {};
  return request({
    url: "/admin/dashboard/overview",
    method: "get",
    params,
  });
}

/**
 * 获取AI模型使用统计
 */
export function getAiModelStats(
  refresh = false
): Promise<AiModelStatsResponse> {
  const params = refresh ? { refresh: true } : {};
  return request({
    url: "/admin/dashboard/ai-models",
    method: "get",
    params,
  });
}

/**
 * 获取最新注册用户列表
 */
export function getRecentUsers(limit = 10): Promise<RecentUsersResponse> {
  return request({
    url: "/admin/dashboard/recent-users",
    method: "get",
    params: { limit },
  });
}

/**
 * 获取教师看板个人统计
 */
export function getTeacherStats(
  refresh = false
): Promise<TeacherStatsResponse> {
  const params = refresh ? { refresh: true } : {};
  return request({
    url: "/teacher/dashboard/stats",
    method: "get",
    params,
  });
}

/**
 * 获取教师待处理任务列表
 */
export function getTeacherPendingTasks(): Promise<TeacherPendingTasksResponse> {
  return request({
    url: "/teacher/dashboard/pending-tasks",
    method: "get",
  });
}

/**
 * 获取学生看板个人统计
 */
export function getStudentStats(
  refresh = false
): Promise<StudentStatsResponse> {
  const params = refresh ? { refresh: true } : {};
  return request({
    url: "/student/dashboard/stats",
    method: "get",
    params,
  });
}

/**
 * 获取教师表现总结
 */
export function getTeacherPerformanceSummary(): Promise<any> {
  return request({
    url: "/teacher/dashboard/performance-summary",
    method: "get",
  });
}

/**
 * 获取教师快速操作
 */
export function getTeacherQuickActions(): Promise<any> {
  return request({
    url: "/teacher/dashboard/quick-actions",
    method: "get",
  });
}

/**
 * 获取学生学习进度
 */
export function getStudentLearningProgress(): Promise<any> {
  return request({
    url: "/student/dashboard/learning-progress",
    method: "get",
  });
}

/**
 * 获取学生成就
 */
export function getStudentAchievements(): Promise<any> {
  return request({
    url: "/student/dashboard/achievements",
    method: "get",
  });
}

/**
 * 获取学生学习建议
 */
export function getStudentStudyRecommendations(): Promise<any> {
  return request({
    url: "/student/dashboard/study-recommendations",
    method: "get",
  });
}

/**
 * 获取系统健康状态
 */
export function getSystemHealth(): Promise<any> {
  return request({
    url: "/admin/dashboard/health",
    method: "get",
  });
}

// 兼容原有的 dashboardApi 对象导出
export const dashboardApi = {
  // 管理员看板
  getAdminOverview,
  getAiModelStats,
  getRecentUsers,

  // 教师看板
  getTeacherStats,
  getTeacherPendingTasks,
  getTeacherPerformanceSummary,
  getTeacherQuickActions,

  // 学生看板
  getStudentStats,
  getStudentLearningProgress,
  getStudentAchievements,
  getStudentStudyRecommendations,

  // 系统健康
  getSystemHealth,
};

export default dashboardApi;

// 显式导出所有类型接口（确保模块导出正确）
export type {
  DashboardApi,
  AdminOverviewResponse,
  AiModelStatsResponse,
  RecentUsersResponse,
  TeacherStatsResponse,
  TeacherPendingTasksResponse,
  StudentStatsResponse,
  DistributionStat,
  RoleDistribution,
  StatusDistribution,
};
