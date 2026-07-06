import axios from "axios";
import type { AxiosRequestConfig, AxiosResponse, AxiosError } from "axios";
import { ElMessage, ElMessageBox, ElLoading } from "element-plus";
import router from "@/router";
import store from "@/store";
import { getAuthConfig } from "./auth-codes";

// 创建axios实例
const service = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "/api",
  timeout: 15000,
  headers: {
    "Content-Type": "application/json",
  },
});

// 标记是否正在处理401错误，防止多次弹框
let isHandling401 = false;
// 标记是否正在刷新token，防止多次刷新
let isRefreshing = false;
// 等待刷新完成的请求队列
let failedQueue: Array<{ resolve: Function; reject: Function }> = [];

// 处理等待队列中的请求
const processQueue = (error: any, token: string | null = null) => {
  failedQueue.forEach(({ resolve, reject }) => {
    if (error) {
      reject(error);
    } else {
      resolve(token);
    }
  });

  failedQueue = [];
};

// 请求拦截器
service.interceptors.request.use(
  async (config) => {
    // 从localStorage获取token，确保取到最新值
    const token = localStorage.getItem("token");

    if (token) {
      try {
        // 检查token是否有效（不包含非ASCII字符）
        if (/^[\x00-\x7F]*$/.test(token)) {
          // 设置token到请求头
          config.headers["Authorization"] = `Bearer ${token}`;
        } else {
          // token包含非法字符，移除它并触发重新登录
          console.error("Invalid token format detected, removing token");
          store.dispatch("auth/clearPermissions", null, { root: true });
          // 注意：这里不直接跳转，避免中断当前请求
        }
      } catch (e) {
        console.error("Error processing token:", e);
        // 出错时清除token
        store.dispatch("auth/clearPermissions", null, { root: true });
      }
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// 响应拦截器
service.interceptors.response.use(
  // 成功响应处理
  (response: AxiosResponse) => {
    // 如果是二进制数据，直接返回
    if (response.config.responseType === "blob") {
      return response;
    }

    const res = response.data;

    // 处理后端标准响应格式（code/message/data结构）
    if (res.code === 200) {
      return res.data;
    } else if (
      res.code === 401 ||
      [10002, 10003, 10004, 10006, 10012, 10015].includes(
        res.code
      )
    ) {
      // 处理401错误和认证相关错误码（移除10001登录失败、10005账户禁用、10014用户未激活，它们现在通过HTTP状态码处理）

      console.log("处理401错误和认证相关错误码", res);
      const errorMsg = res.message || "未授权，请重新登录";
      const errorCode = res.code || res.errorCode;
      handleAuthError(errorMsg, errorCode);
      return Promise.reject(new Error(errorMsg));
    } else {
      // 业务错误
      const errorMsg = res.message || "请求失败";
      ElMessage.error(errorMsg);
      return Promise.reject(new Error(errorMsg));
    }
  },

  // 错误响应处理
  async (error: AxiosError) => {
    const originalRequest = error.config as any;
    console.log("处理HTTP状态码", error.response?.status, originalRequest?.url);
    
    // 处理HTTP 403状态码 - 仅提示权限不足，不清除登录状态
    if (error.response?.status === 403) {
      let errorMessage = "权限不足，无法访问该资源";
      if (error.response?.data && typeof error.response.data === "object") {
        const data = error.response.data as any;
        errorMessage = data.message || errorMessage;
      }
      ElMessage.error(errorMessage);
      return Promise.reject(error);
    }
    
    // 处理HTTP 401状态码
    if (error.response?.status === 401 && !originalRequest._retry) {
      // 如果是刷新token接口本身返回401，直接处理认证错误，不要重试
      if (originalRequest.url?.includes("/auth/refresh-token")) {
        console.log("刷新token接口返回401，停止重试");
        // 提取错误信息
        let errorMessage = "登录会话已过期，请重新登录";
        let errorCode = 10012;
        handleAuthError(errorMessage, errorCode);
        return Promise.reject(error);
      }
      // 如果正在刷新token，将请求加入队列
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        }).then((token) => {
          if (token) {
            originalRequest.headers["Authorization"] = `Bearer ${token}`;
            return service(originalRequest);
          }
          return Promise.reject(error);
        });
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        console.log("尝试刷新token");
        // 尝试刷新token
        await store.dispatch("user/refreshToken");
        const newToken = localStorage.getItem("token");

        if (newToken) {
          console.log("刷新token成功");
          // 刷新成功，处理队列中的请求
          processQueue(null, newToken);
          originalRequest.headers["Authorization"] = `Bearer ${newToken}`;
          return service(originalRequest);
        } else {
          throw new Error("刷新后未获取到新token");
        }
      } catch (refreshError: any) {
        console.log("刷新token失败", refreshError);
        // 刷新失败，处理队列并跳转登录
        processQueue(refreshError, null);

        // 从刷新token的错误中提取错误信息
        let errorMessage = "登录已过期，请重新登录";
        let errorCode = "";

        if (
          refreshError.response?.data &&
          typeof refreshError.response.data === "object"
        ) {
          const data = refreshError.response.data as any;
          errorMessage = data.message || errorMessage;
          errorCode = data.code || "";
        }

        handleAuthError(errorMessage, errorCode);
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    // 其他错误处理
    let errorMessage = "请求失败";
    if (error.response && typeof error.response.data === "object") {
      const responseData = error.response.data as any;
      errorMessage =
        responseData?.message || responseData?.error?.message || errorMessage;
    }

    // 显示错误消息
    ElMessage.error(errorMessage);
    return Promise.reject(error);
  }
);

/**
 * 处理授权错误，防止死循环
 * @param message 错误信息
 * @param code 错误码
 */
function handleAuthError(message: string, code?: string | number) {
  console.log("handleAuthError 被调用:", { message, code, isHandling401 });

  // 如果已经在处理401错误，不再重复处理
  if (isHandling401) {
    console.log("已在处理401错误，跳过");
    return;
  }

  isHandling401 = true; // 立即标记为正在处理

  // 获取对应的认证配置
  const config = getAuthConfig(code);
  console.log("认证错误配置:", config);

  ElMessageBox.confirm(config.message, config.title, {
    confirmButtonText: config.confirmButtonText,
    showCancelButton: config.showCancelButton,
    type: config.type,
  }).finally(() => {
    console.log("弹框关闭，开始清理状态");

    // 清除登录状态
    try {
      store.dispatch("auth/clearPermissions", null, { root: true });
      console.log("权限清理完成");
    } catch (error) {
      console.error("清理权限时出错:", error);
    }

    // 如果需要重定向到登录页
    if (config.needRedirect) {
      // 获取重定向路径，避免循环
      const getRedirectPath = () => {
        const { pathname, search } = window.location;

        // 不在登录页面，直接使用当前路径
        if (pathname !== "/login") return pathname + search;

        // 在登录页面，提取有效的redirect参数
        const redirect = new URLSearchParams(search).get("redirect");
        return redirect && !redirect.includes("/login")
          ? decodeURIComponent(redirect)
          : "/";
      };

      // 跳转到登录页
      const redirectUrl = `/login?redirect=${encodeURIComponent(
        getRedirectPath()
      )}`;
      console.log("准备跳转到登录页:", redirectUrl);

      // 使用已静态导入的 router 跳转，避免白屏
      try {
        router.push(redirectUrl);
      } catch (routerError) {
        console.error("使用router跳转失败，使用window.location:", routerError);
        window.location.href = redirectUrl;
      }
    }

    // 延迟重置处理状态
    setTimeout(() => {
      isHandling401 = false;
      console.log("401处理状态已重置");
    }, 800);
  });
}

/**
 * 验证是否为Blob对象
 * @param data 响应数据
 * @returns 是否为Blob
 */
const isBlob = (data: any): boolean => {
  return data instanceof Blob && data.type !== "application/json";
};

/**
 * 通用文件下载方法
 * @param url 下载地址
 * @param params 请求参数
 * @param filename 文件名
 * @param config 额外配置
 */
export const downloadFile = async (
  url: string,
  params?: any,
  filename?: string,
  config?: any
) => {
  // 创建loading实例
  const loadingInstance = ElLoading.service({
    text: "正在下载文件，请稍候",
    background: "rgba(0, 0, 0, 0.7)",
  });

  try {
    const response = await service({
      url,
      method: "get",
      params,
      responseType: "blob",
      ...config,
    });

    // 验证响应是否为Blob
    if (isBlob(response.data)) {
      // 创建Blob对象
      const blob = new Blob([response.data]);

      // 创建下载链接
      const link = document.createElement("a");
      link.href = window.URL.createObjectURL(blob);
      link.download = filename || "download";

      // 触发下载
      document.body.appendChild(link);
      link.click();

      // 清理
      document.body.removeChild(link);
      window.URL.revokeObjectURL(link.href);

      ElMessage.success("文件下载成功");
    } else {
      // 如果不是Blob，尝试解析错误信息
      const text = await response.data.text();
      try {
        const errorData = JSON.parse(text);
        ElMessage.error(errorData.message || "下载失败");
      } catch {
        ElMessage.error("下载失败，请稍后重试");
      }
    }
  } catch (error: any) {
    console.error("文件下载错误:", error);
    ElMessage.error(error.message || "下载文件出现错误，请联系管理员");
  } finally {
    // 关闭loading
    loadingInstance.close();
  }
};

// 导出请求方法
export default function request<T = any>(
  config: AxiosRequestConfig
): Promise<T> {
  return service(config) as unknown as Promise<T>;
}
