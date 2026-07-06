// 班级状态枚举
export type ClassStatus = "active" | "inactive" | "disbanded";

// 学生在班级中的状态
export type StudentStatus = "active" | "inactive" | "left";

// 加入班级的方式
export type JoinMethod = "teacher" | "code";

// 班级基本信息
export interface Class {
  _id: string;
  name: string;
  code: string;
  teacherId: string;
  teacherName?: string;
  status: ClassStatus;
  studentCount: number;
  maxStudents: number; // 班级最大学生数量
  description?: string;
  createdAt: string;
  updatedAt: string;
}

// 班级学生信息
export interface ClassStudent {
  _id: string;
  classId?: string;
  studentId: string;
  studentName: string; // 学生姓名
  studentNumber?: string; // 学号
  avatar?: string; // 头像
  joinMethod: JoinMethod;
  status: StudentStatus;
  joinedAt: string;
  updatedAt?: string;
  // 作业相关统计
  totalSubmissions?: number; // 累计提交作业数
  lastSubmissionTime?: string; // 最后提交时间
}

// 创建班级参数
export interface CreateClassParams {
  name: string;
  description?: string;
  code?: string;
  maxStudents?: number; // 班级最大学生数量，可选
}

// 更新班级参数
export interface UpdateClassParams {
  name?: string;
  description?: string;
  status?: ClassStatus;
  maxStudents?: number; // 班级最大学生数量，可选
}

// 班级查询参数
export interface ClassQueryParams {
  page?: number;
  limit?: number;
  status?: ClassStatus;
  search?: string;
  teacherId?: string;
  sortField?: "name" | "createdAt" | "studentCount";
  sortOrder?: "asc" | "desc";
}

// 班级学生查询参数
export interface ClassStudentQueryParams {
  page?: number;
  limit?: number;
  status?: StudentStatus;
  search?: string;
  sortField?: "studentName" | "joinedAt";
  sortOrder?: "asc" | "desc";
}

// 添加学生参数
export interface AddStudentsParams {
  studentIds: string[];
}

// 加入班级参数
export interface JoinClassParams {
  code: string;
}

// 更新学生状态参数
export interface UpdateStudentStatusParams {
  studentIds: string[];
  status: StudentStatus;
}

// 班级列表响应
export interface ClassListResponse {
  items: Class[];
  total: number;
  page: number;
  limit: number;
}

// 班级学生列表响应
export interface ClassStudentListResponse {
  items: ClassStudent[];
  total: number;
  page: number;
  limit: number;
}

// API统一响应格式 - 由于axios拦截器已经返回了data字段，所以直接是业务数据类型
export type ApiResponse<T = any> = T;

// 班级列表API响应（直接是分页数据）
export type ClassListApiResponse = ClassListResponse;

// 其他API响应也直接是对应的数据类型
export interface CreateClassApiResponse {
  message: string;
  classId: string;
}

export interface RegenerateCodeApiResponse {
  message: string;
  inviteCode: string;
}

// 添加学生失败信息
export interface AddStudentError {
  id: string;
  reason: string;
}

// 添加学生API响应
export interface AddStudentsApiResponse {
  success: string[];
  failed: AddStudentError[];
}
