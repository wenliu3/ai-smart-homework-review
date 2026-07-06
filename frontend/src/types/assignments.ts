// 作业状态枚举
export enum AssignmentStatus {
  DRAFT = "draft",
  PUBLISHED = "published",
  TERMINATED = "terminated",
}

// AI规则快照接口
export interface AiRuleSnapshot {
  id?: string; // 原始规则ID（编辑时需要）
  name: string;
  modelType: string;
  prompt: string;
  originalRuleId: string;
  snapshotAt: string;
}

// 作业接口
export interface Assignment {
  id: string;
  title: string;
  description: string;
  teacherId: string;
  teacherName?: string;
  classes: Array<{
    id: string;
    name: string;
  }>;
  aiRule: AiRuleSnapshot;
  startDate: string;
  endDate: string;
  allowAttachments: boolean;
  status: AssignmentStatus;
  terminatedReason?: string;
  isDeleted: boolean;
  deletedAt?: string;
  createdAt: string;
  updatedAt: string;
  isExpired?: boolean;
  // 统计信息
  submissionStats: {
    total: number;
    submitted: number;
    graded: number;
    pending: number;
  };
  totalSubmissions?: number;
  gradedSubmissions?: number;
  pendingSubmissions?: number;
}

// 作业列表项接口（简化版）
export interface AssignmentListItem {
  id: string;
  title: string;
  description: string;
  teacherId: string;
  teacherName?: string;
  classes: Array<{
    id: string;
    name: string;
  }>;
  aiRule: AiRuleSnapshot;
  startDate: string;
  endDate: string;
  allowAttachments: boolean;
  status: AssignmentStatus;
  terminatedReason?: string;
  isDeleted: boolean;
  deletedAt?: string;
  createdAt: string;
  updatedAt: string;
  isExpired?: boolean;
  // 简化的统计信息
  submissionCount: number;
  totalStudents: number;
}

// 作业查询参数
export interface AssignmentQueryParams {
  page?: number;
  pageSize?: number;
  search?: string;
  status?: AssignmentStatus;
  classId?: string; // 班级ID精确查询
  className?: string; // 班级名称模糊查询
  teacherName?: string;
  startDate?: string;
  endDate?: string;
  isExpired?: boolean;
  sort?: string;
  order?: "asc" | "desc";
}

// 作业列表响应
export interface AssignmentListResponse {
  items: AssignmentListItem[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
}

// 创建作业DTO
export interface CreateAssignmentDto {
  title: string;
  description: string;
  classes: string[];
  aiRule: AiRuleSnapshot | null;
  startDate: string;
  endDate: string;
  allowAttachments: boolean;
}

// 更新作业DTO
export interface UpdateAssignmentDto extends Partial<CreateAssignmentDto> {}

// 更新作业状态DTO
export interface UpdateAssignmentStatusDto {
  status: AssignmentStatus;
  terminatedReason?: string;
}

// 学生端作业接口
export interface StudentAssignment {
  id: string;
  title: string;
  description: string;
  teacherName: string;
  startDate: string;
  endDate: string;
  allowAttachments: boolean;
  maxFileSize: number;
  allowedFileTypes: string[];
  status: AssignmentStatus;
  terminatedReason?: string;
  isExpired: boolean;
  hasSubmitted: boolean;
  hasDraft: boolean;
  submissionStatus?: string;
  submissionId?: string;
  canSubmit: boolean;
  createdAt: string;
}

// 学生端作业列表项接口
export interface StudentAssignmentListItem {
  id: string;
  title: string;
  teacherName: string;
  startDate: string;
  endDate: string;
  status: AssignmentStatus;
  terminatedReason?: string;
  isExpired: boolean;
  hasSubmitted: boolean;
  hasDraft: boolean;
  submissionStatus?: string;
  submissionId?: string;
  allowAttachments: boolean;
  createdAt: string;
  // 新增字段：支持多班级场景
  classId: string;
  className: string;
}
