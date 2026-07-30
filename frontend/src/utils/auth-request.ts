const PUBLIC_AUTH_PATHS = new Set([
  "/v1/auth/login",
  "/v1/auth/register",
  "/v1/auth/forgot-password",
  "/v1/auth/reset-password",
  "/v1/auth/refresh-token",
  "/auth/login",
  "/auth/register",
]);

function normalizeRequestPath(url = ""): string {
  const pathname = new URL(url, "http://local.test").pathname;
  return pathname.replace(/^\/api(?=\/)/, "");
}

export function isPublicAuthRequest(url?: string): boolean {
  return PUBLIC_AUTH_PATHS.has(normalizeRequestPath(url));
}

export function shouldAttachAccessToken(url?: string): boolean {
  return !isPublicAuthRequest(url);
}

export function shouldAttemptTokenRefresh(
  status: number | undefined,
  url: string | undefined,
  alreadyRetried: boolean
): boolean {
  return status === 401 && !alreadyRetried && !isPublicAuthRequest(url);
}

export function getResponseErrorMessage(
  data: unknown,
  fallback: string
): string {
  if (data && typeof data === "object") {
    const message = (data as { message?: unknown }).message;
    if (typeof message === "string" && message.trim()) return message;
  }
  return fallback;
}
