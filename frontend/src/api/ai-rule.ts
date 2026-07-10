import request from "@/utils/request";

// AI规则接口类型定义
export interface AiRule {
  id: string;
  name: string;
  description?: string;
  modelType: "deepseek" | "mimo";
  prompt: string;
  status: "active" | "inactive";
  visibility: "private" | "public" | "system";
  tags: string[];
  createdBy?: {
    id: string;
    name: string;
  };
  createdAt: string;
  updatedAt: string;
}

// 查询参数接口
export interface AiRuleQueryParams {
  page?: number;
  pageSize?: number;
  search?: string;
  status?: string;
  visibility?: string;
  modelType?: "deepseek" | "mimo";
  tags?: string[];
  sort?: string;
  order?: "asc" | "desc";
}

// 创建AI规则DTO
export interface CreateAiRuleDto {
  name: string;
  description?: string;
  modelType: "deepseek" | "mimo";
  prompt: string;
  visibility?: "private" | "public" | "system";
  status?: "active" | "inactive";
  tags?: string[];
}

// 更新AI规则DTO
export interface UpdateAiRuleDto {
  name?: string;
  description?: string;
  modelType?: "deepseek" | "mimo";
  prompt?: string;
  visibility?: "private" | "public" | "system";
  status?: "active" | "inactive";
  tags?: string[];
}

/**
 * 获取AI规则列表
 * @param params 查询参数
 * @returns AI规则列表和分页信息
 */
export function getAiRuleList(params?: AiRuleQueryParams) {
  return request<{
    items: AiRule[];
    total: number;
    page: number;
    pageSize: number;
  }>({
    url: "/v1/ai-rules",
    method: "get",
    params,
  });
}

/**
 * 根据ID获取AI规则详情
 * @param id 规则ID
 * @returns AI规则详细信息
 */
export function getAiRuleById(id: string) {
  return request<AiRule>({
    url: `/v1/ai-rules/${id}`,
    method: "get",
  });
}

/**
 * 创建AI规则
 * @param data 规则数据
 * @returns 创建结果
 */
export function createAiRule(data: CreateAiRuleDto) {
  return request<{ id: string; success: boolean }>({
    url: "/v1/ai-rules",
    method: "post",
    data,
  });
}

/**
 * 更新AI规则
 * @param id 规则ID
 * @param data 更新数据
 * @returns 更新结果
 */
export function updateAiRule(id: string, data: UpdateAiRuleDto) {
  return request<{ id: string; success: boolean }>({
    url: `/v1/ai-rules/${id}/update`,
    method: "post",
    data,
  });
}

/**
 * 删除AI规则（硬删除）
 * @param id 规则ID
 * @returns 删除结果
 */
export function deleteAiRule(id: string) {
  return request<{ id: string; success: boolean }>({
    url: `/v1/ai-rules/${id}/delete`,
    method: "post",
  });
}

/**
 * 切换AI规则状态（启用/禁用）
 * @param id 规则ID
 * @returns 切换后的状态
 */
export function toggleAiRuleStatus(id: string) {
  return request<{ id: string; status: string; success: boolean }>({
    url: `/v1/ai-rules/${id}/toggle-status`,
    method: "post",
  });
}

/**
 * 复制AI规则
 * @param id 源规则ID
 * @param name 新规则名称（可选）
 * @returns 复制结果
 */
export function copyAiRule(id: string, name?: string) {
  return request<{ id: string; success: boolean }>({
    url: `/v1/ai-rules/${id}/copy`,
    method: "post",
    data: { name },
  });
}

/**
 * 获取可用的AI规则列表（用于下拉选择）
 * @param status 状态过滤
 * @returns 完整的规则列表
 */
export function getAvailableAiRules(status = "active") {
  return request<
    Array<{
      id: string;
      name: string;
      description: string;
      modelType: string;
      prompt: string;
      visibility: string;
      tags: string[];
    }>
  >({
    url: "/v1/ai-rules/available/list",
    method: "get",
    params: { status },
  });
}
