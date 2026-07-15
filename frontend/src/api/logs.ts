import request from "@/utils/request";

export interface LogItem {
  id: number;
  operator: string;
  operatorName: string;
  action: string;
  module: string;
  description: string;
  ip: string;
  method: string;
  endpoint: string;
  statusCode: number;
  createdAt: string;
}

export interface LogQueryParams {
  page?: number;
  pageSize?: number;
  operator?: string;
  action?: string;
  module?: string;
  keyword?: string;
  startDate?: string;
  endDate?: string;
}

export interface LogsResponse {
  items: LogItem[];
  total: number;
  page: number;
  pageSize: number;
}

/**
 * 分页查询操作日志
 */
export function getLogs(params: LogQueryParams): Promise<LogsResponse> {
  return request({
    url: "/admin/logs",
    method: "get",
    params,
  });
}
