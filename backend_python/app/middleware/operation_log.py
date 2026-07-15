"""操作日志中间件 — 自动记录 POST/PUT/DELETE 以及登录/退出操作"""
import time
import json
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from app.database import SessionLocal
from app.crud.operation_log import create_log
from app.core.security import decode_access_token

# 哪些路径完全不记录（高频查询/轮询/静态资源）
SKIP_PREFIXES = [
    "/api/admin/logs",           # 查日志本身不记
    "/api/admin/ai-models/active",
    "/api/admin/ai-models/",     # GET 余额/列表不记
    "/api/users/profile",
    "/api/dashboard",
    "/api/docs",
    "/api/openapi.json",
    "/api/chat",                 # AI 助手聊天内容不记操作日志
]

# HTTP 方法 → 操作类型映射
METHOD_ACTION_MAP = {
    "POST": "创建",
    "PUT": "更新",
    "PATCH": "更新",
    "DELETE": "删除",
    "GET": "查询",
}

# URL 路径关键词 → 模块名映射（按匹配顺序，先匹配到的生效）
MODULE_MAP = [
    ("/admin/ai-models", "AI模型配置"),
    ("/admin/logs", "操作日志"),
    ("/auth/login", "登录认证"),
    ("/auth/logout", "登录认证"),
    ("/auth/register", "登录认证"),
    ("/users", "用户管理"),
    ("/roles", "角色管理"),
    ("/menus", "菜单管理"),
    ("/classes", "班级管理"),
    ("/assignments", "作业管理"),
    ("/submissions", "批改管理"),
    ("/correcting", "批改管理"),
    ("/plagiarism", "文档查重"),
    ("/ai-rules", "AI批改规则"),
    ("/dashboard", "数据看板"),
    ("/upload", "文件上传"),
    ("/chat", "AI助手"),
    ("/permissions", "权限管理"),
]


def _determine_module(path: str) -> str:
    """根据请求路径判断所属模块"""
    for keyword, module_name in MODULE_MAP:
        if keyword in path:
            return module_name
    return "其他"


def _should_log(path: str, method: str) -> bool:
    """判断是否需要记录此请求 — 记录所有 API 写操作（POST/PUT/PATCH/DELETE）"""
    # 只记录 /api/ 下的请求
    if not path.startswith("/api/"):
        return False
    # 跳过白名单
    if any(path.startswith(p) for p in SKIP_PREFIXES):
        return False
    # GET 请求默认跳过
    if method == "GET":
        return False
    return True


def _extract_user(request: Request) -> tuple[str, str]:
    """从请求头中提取用户信息"""
    username = "anonymous"
    name = "匿名用户"
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        try:
            payload = decode_access_token(auth[7:])
            username = payload.get("username", "anonymous")
            name = payload.get("username", "匿名用户")  # JWT 不含 name，用 username
        except Exception:
            pass
    return username, name


class OperationLogMiddleware(BaseHTTPMiddleware):
    """自动记录管理操作日志"""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        method = request.method

        # 只对需要记录的请求进行处理
        should_log = _should_log(path, method)

        # 正常处理请求
        response: Response = await call_next(request)

        if should_log:
            try:
                username, name = _extract_user(request)
                action = METHOD_ACTION_MAP.get(method, method)
                module = _determine_module(path)
                description = f"{action} - {module}"
                ip = request.client.host if request.client else ""

                # 用独立 session 写日志（不阻塞主请求）
                db = SessionLocal()
                try:
                    create_log(
                        db=db,
                        operator=username,
                        operator_name=name,
                        action=action,
                        module=module,
                        description=description,
                        ip=ip,
                        method=method,
                        endpoint=path,
                        status_code=response.status_code,
                    )
                finally:
                    db.close()
            except Exception:
                pass  # 日志记录失败不影响正常请求

        return response
