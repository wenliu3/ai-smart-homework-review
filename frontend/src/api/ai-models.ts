import request from "@/utils/request";

// AI模型接口
export interface AiModel {
  code: string; // 'deepseek' | 'mimo'
  name: string; // 'DeepSeek' | '豆包'
  provider: string; // 'DeepSeek' | 'ByteDance'
  modelName: string; // 'deepseek-chat' | 'mimo-v2.5'
  baseUrl: string; // API地址（只读）
  apiKey: string; // API密钥（可编辑）
  accessKey?: string; // 访问密钥（豆包必填）
  secretKey?: string; // 私有密钥（豆包必填）
  status: "active" | "inactive"; // 状态（可编辑）
  isDefault: boolean; // 是否默认（可编辑）
  totalUsage: number; // 总使用次数（统计）
  totalTokens: number; // 总Token消耗（统计）
  lastUsedAt?: Date; // 最后使用时间（统计）
  lastBalance: number; // 最后查询的余额
  balanceCurrency: string; // 余额货币
  lastBalanceCheck?: Date; // 最后余额检查时间
}

// 模型余额接口
export interface ModelBalance {
  balance: number;
  currency: string;
  lastUpdated: Date;
  status: "success" | "error";
  message?: string;
  details?: {
    // DeepSeek额外信息
    grantedBalance?: number;
    toppedUpBalance?: number;
    // 豆包额外信息
    accountId?: number;
    cashBalance?: number;
    arrearsBalance?: number;
    freezeAmount?: number;
    creditLimit?: number;
  };
}

// 模型列表响应
export interface AiModelListResponse {
  models: AiModel[];
  summary: {
    totalModels: number;
    activeModels: number;
    totalUsage: number;
    totalBalance: number;
  };
}

// 模型统计接口
export interface ModelStats {
  dailyUsage: { date: string; count: number }[];
  monthlyUsage: { month: string; count: number }[];
  recentActivity: {
    assignmentId: string;
    assignmentTitle: string;
    usedAt: Date;
    tokenUsed: number;
  }[];
}

// 连接测试结果
export interface ConnectionTestResult {
  success: boolean;
  responseTime: number;
  message: string;
}

// 更新模型配置数据
export interface UpdateAiModelData {
  name?: string;
  provider?: string;
  modelName?: string;
  baseUrl?: string;
  apiKey?: string;
  accessKey?: string;
  secretKey?: string;
  status?: "active" | "inactive";
  isDefault?: boolean;
}

// 设置默认模型结果
export interface SetDefaultResult {
  success: boolean;
  message: string;
}

/**
 * AI模型管理API服务
 */
export const aiModelApi = {
  /**
   * 获取模型列表和汇总信息
   */
  getList(): Promise<AiModelListResponse> {
    return request({
      url: "/admin/ai-models",
      method: "GET",
    });
  },

  /**
   * 获取单个模型详情
   */
  getDetail(code: string): Promise<AiModel> {
    return request({
      url: `/admin/ai-models/${code}`,
      method: "GET",
    });
  },

  /**
   * 更新模型配置
   */
  updateConfig(code: string, data: UpdateAiModelData): Promise<AiModel> {
    return request({
      url: `/admin/ai-models/${code}`,
      method: "PUT",
      data,
    });
  },

  /**
   * 设置默认模型
   */
  setDefault(code: string): Promise<SetDefaultResult> {
    return request({
      url: `/admin/ai-models/${code}/default`,
      method: "POST",
    });
  },

  /**
   * 获取模型余额（后端统一提供）
   */
  getBalance(code: string): Promise<ModelBalance> {
    return request({
      url: `/admin/ai-models/${code}/balance`,
      method: "GET",
    });
  },

  /**
   * 测试模型连接
   */
  testConnection(code: string): Promise<ConnectionTestResult> {
    return request({
      url: `/admin/ai-models/${code}/test`,
      method: "POST",
    });
  },

  /**
   * 获取模型使用统计
   */
  getStats(code: string): Promise<ModelStats> {
    return request({
      url: `/admin/ai-models/${code}/stats`,
      method: "GET",
    });
  },

  /**
   * 获取活跃的模型列表（用于前端下拉框）
   */
  getActiveModels(): Promise<AiModel[]> {
    return request({
      url: "/admin/ai-models/active",
      method: "GET",
    });
  },

  /**
   * 初始化预置模型（开发调试用）
   */
  initializeModels(): Promise<{ success: boolean; message: string }> {
    return request({
      url: "/admin/ai-models/initialize",
      method: "POST",
    });
  },
};

export default aiModelApi;
