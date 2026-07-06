import request from "@/utils/request";
import type { LogQueryParams, LogsResponse } from "@/types/logs";

/**
 * 分页查询访问日志
 * @param params 查询参数
 */
export function getLogs(params: LogQueryParams): Promise<LogsResponse> {
  return request({
    url: "/logs",
    method: "get",
    params,
  });
}
