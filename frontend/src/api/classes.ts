import request from "@/utils/request";
import type {
  Class,
  ClassListResponse,
  ClassStudentListResponse,
  ClassQueryParams,
  ClassStudentQueryParams,
  CreateClassParams,
  UpdateClassParams,
  AddStudentsParams,
  JoinClassParams,
  UpdateStudentStatusParams,
  CreateClassApiResponse,
  RegenerateCodeApiResponse,
  AddStudentsApiResponse,
} from "@/types/classes";

/**
 * 获取班级列表
 * @param params 查询参数
 */
export function getClassList(
  params: ClassQueryParams
): Promise<ClassListResponse> {
  return request({
    url: "/classes/list",
    method: "get",
    params,
  });
}

/**
 * 获取班级详情
 * @param id 班级ID
 */
export function getClassDetail(id: string): Promise<Class> {
  return request({
    url: `/classes/${id}`,
    method: "get",
  });
}

/**
 * 创建班级
 * @param data 班级信息
 */
export function createClass(
  data: CreateClassParams
): Promise<CreateClassApiResponse> {
  return request({
    url: "/classes/create",
    method: "post",
    data,
  });
}

/**
 * 更新班级信息
 * @param id 班级ID
 * @param data 更新数据
 */
export function updateClass(
  id: string,
  data: UpdateClassParams
): Promise<{ message: string }> {
  return request({
    url: `/classes/${id}/edit`,
    method: "post",
    data,
  });
}

/**
 * 解散班级
 * @param id 班级ID
 */
export function disbandClass(id: string): Promise<{ message: string }> {
  return request({
    url: `/classes/${id}/close`,
    method: "post",
  });
}

/**
 * 刷新班级邀请码
 * @param id 班级ID
 */
export function regenerateClassCode(
  id: string
): Promise<RegenerateCodeApiResponse> {
  return request({
    url: `/classes/${id}/regenerate-code`,
    method: "post",
  });
}

/**
 * 获取班级学生列表
 * @param id 班级ID
 * @param params 查询参数
 */
export function getClassStudents(
  id: string,
  params: ClassStudentQueryParams
): Promise<ClassStudentListResponse> {
  return request({
    url: `/classes/${id}/students`,
    method: "get",
    params,
  });
}

/**
 * 添加学生到班级
 * @param id 班级ID
 * @param data 学生ID列表
 */
export function addStudentsToClass(
  id: string,
  data: AddStudentsParams
): Promise<AddStudentsApiResponse> {
  return request({
    url: `/classes/${id}/students`,
    method: "post",
    data,
  });
}

/**
 * 学生加入班级
 * @param data 班级码
 */
export function joinClass(data: JoinClassParams): Promise<any> {
  return request({
    url: "/classes/join",
    method: "post",
    data,
  });
}

/**
 * 更新学生状态
 * @param id 班级ID
 * @param data 学生状态更新参数
 */
export function updateStudentStatus(
  id: string,
  data: UpdateStudentStatusParams
): Promise<any> {
  return request({
    url: `/classes/${id}/students/status`,
    method: "post",
    data,
  });
}

/**
 * 退出班级
 * @param id 班级ID
 */
export function leaveClass(id: string): Promise<any> {
  return request({
    url: `/classes/${id}/leave`,
    method: "post",
  });
}
