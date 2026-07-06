export interface Log {
  id: string;
  username?: string;
  userId?: string;
  ip: string;
  method: string;
  endpoint: string;
  statusCode: number;
  timestamp: string;
  responseTime: number;
  requestParams?: any;
  responseData?: any;
}

export interface LogQueryParams {
  page: number;
  limit: number;
  username?: string;
  userId?: string;
  ip?: string;
  endpoint?: string;
  startDate?: string;
  endDate?: string;
  sortField?: string;
  sortOrder?: "asc" | "desc";
}

export interface LogsResponse {
  items: Log[];
  total: number;
  page: number;
  limit: number;
}
