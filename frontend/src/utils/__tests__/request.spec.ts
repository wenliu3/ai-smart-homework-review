import { AxiosError } from "axios";
import type {
  AxiosAdapter,
  AxiosResponse,
  InternalAxiosRequestConfig,
} from "axios";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  dispatch: vi.fn(),
  routerPush: vi.fn(),
  messageError: vi.fn(),
  messageSuccess: vi.fn(),
  confirm: vi.fn(),
}));

vi.mock("@/store", () => ({
  default: { dispatch: mocks.dispatch },
}));

vi.mock("@/router", () => ({
  default: { push: mocks.routerPush },
}));

vi.mock("element-plus", () => ({
  ElMessage: {
    error: mocks.messageError,
    success: mocks.messageSuccess,
  },
  ElMessageBox: { confirm: mocks.confirm },
  ElLoading: {
    service: vi.fn(() => ({ close: vi.fn() })),
  },
}));

function unauthorizedResponse(
  config: InternalAxiosRequestConfig,
  message = "登录已过期"
): AxiosError {
  const response: AxiosResponse = {
    data: { code: 401, message, data: null },
    status: 401,
    statusText: "Unauthorized",
    headers: {},
    config,
    request: {},
  };
  return new AxiosError(
    "Request failed with status code 401",
    AxiosError.ERR_BAD_REQUEST,
    config,
    {},
    response
  );
}

function successResponse(
  config: InternalAxiosRequestConfig,
  data: unknown
): AxiosResponse {
  return {
    data: { code: 200, message: "操作成功", data },
    status: 200,
    statusText: "OK",
    headers: {},
    config,
    request: {},
  };
}

function getAuthorization(config: InternalAxiosRequestConfig): string | undefined {
  const headers = config.headers as any;
  return headers?.get?.("Authorization") ?? headers?.Authorization;
}

function deferred<T = void>() {
  let resolve!: (value: T | PromiseLike<T>) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((promiseResolve, promiseReject) => {
    resolve = promiseResolve;
    reject = promiseReject;
  });
  return { promise, resolve, reject };
}

describe("request auth response interceptor", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
    vi.resetModules();
    mocks.confirm.mockResolvedValue("confirm");
  });

  it("登录请求 401 保留账号密码错误且不刷新、不弹认证对话框", async () => {
    const { default: request } = await import("../request");
    const adapter: AxiosAdapter = async (config) => {
      throw unauthorizedResponse(config, "账号或密码错误");
    };

    await expect(
      request({ url: "/v1/auth/login", method: "post", adapter })
    ).rejects.toThrow("账号或密码错误");

    expect(mocks.dispatch).not.toHaveBeenCalled();
    expect(mocks.confirm).not.toHaveBeenCalled();
  });

  it("两个并发受保护 401 只刷新一次，并携带新 token 重放两个请求", async () => {
    const { default: request } = await import("../request");
    localStorage.setItem("token", "old-token");
    const refreshGate = deferred();
    mocks.dispatch.mockImplementation((type: string) => {
      if (type === "user/refreshToken") return refreshGate.promise;
      return Promise.resolve();
    });
    const attempts = new Map<string, number>();
    const adapter: AxiosAdapter = async (config) => {
      const url = config.url!;
      const count = (attempts.get(url) ?? 0) + 1;
      attempts.set(url, count);
      if (count === 1) throw unauthorizedResponse(config);
      return successResponse(config, {
        url,
        authorization: getAuthorization(config),
      });
    };

    const firstRequest = request({
      url: "/teacher/assignments",
      method: "get",
      adapter,
    });
    const secondRequest = request({
      url: "/teacher/classes",
      method: "get",
      adapter,
    });
    await vi.waitFor(() => {
      expect(attempts.get("/teacher/assignments")).toBe(1);
      expect(attempts.get("/teacher/classes")).toBe(1);
      expect(mocks.dispatch).toHaveBeenCalledTimes(1);
    });

    localStorage.setItem("token", "new-token");
    refreshGate.resolve();

    await expect(Promise.all([firstRequest, secondRequest])).resolves.toEqual([
      {
        url: "/teacher/assignments",
        authorization: "Bearer new-token",
      },
      {
        url: "/teacher/classes",
        authorization: "Bearer new-token",
      },
    ]);
    expect(mocks.dispatch).toHaveBeenCalledTimes(1);
    expect(mocks.dispatch).toHaveBeenCalledWith("user/refreshToken");
    expect(attempts.get("/teacher/assignments")).toBe(2);
    expect(attempts.get("/teacher/classes")).toBe(2);
  });

  it("刷新失败时拒绝全部队列，只清理和提示跳转一次", async () => {
    const { default: request } = await import("../request");
    localStorage.setItem("token", "old-token");
    const refreshGate = deferred();
    mocks.dispatch.mockImplementation((type: string) => {
      if (type === "user/refreshToken") return refreshGate.promise;
      return Promise.resolve();
    });
    const attempts = new Map<string, number>();
    const adapter: AxiosAdapter = async (config) => {
      const url = config.url!;
      attempts.set(url, (attempts.get(url) ?? 0) + 1);
      throw unauthorizedResponse(config);
    };

    const firstRequest = request({
      url: "/teacher/assignments",
      method: "get",
      adapter,
    });
    const secondRequest = request({
      url: "/teacher/classes",
      method: "get",
      adapter,
    });
    await vi.waitFor(() => {
      expect(attempts.get("/teacher/assignments")).toBe(1);
      expect(attempts.get("/teacher/classes")).toBe(1);
      expect(mocks.dispatch).toHaveBeenCalledTimes(1);
    });

    const refreshError = new Error("refresh failed");
    refreshGate.reject(refreshError);
    const results = await Promise.allSettled([firstRequest, secondRequest]);

    expect(results).toEqual([
      { status: "rejected", reason: refreshError },
      { status: "rejected", reason: refreshError },
    ]);
    expect(mocks.dispatch).toHaveBeenCalledWith("user/clearSession");
    expect(mocks.dispatch).toHaveBeenCalledWith("auth/clearPermissions");
    expect(
      mocks.dispatch.mock.calls.filter(
        ([type]) => type === "user/clearSession"
      )
    ).toHaveLength(1);
    expect(
      mocks.dispatch.mock.calls.filter(
        ([type]) => type === "auth/clearPermissions"
      )
    ).toHaveLength(1);
    expect(mocks.confirm).toHaveBeenCalledTimes(1);
    await vi.waitFor(() => expect(mocks.routerPush).toHaveBeenCalledTimes(1));
  });
});
