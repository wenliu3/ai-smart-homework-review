"""FastAPI 应用入口"""
import traceback
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from .config import settings
from .database import engine, Base, SessionLocal
from .core.exceptions import BizException
from .routers import (
    auth, users, classes, assignments, submissions,
    correcting, dashboard, permissions, ai_models, ai_rules, upload,
    plagiarism, chat,
)

# 启动时自动建表（开发期便捷；生产建议用 alembic 迁移）
Base.metadata.create_all(bind=engine)

# 启动时清理过期/已撤销的 RefreshToken，避免历史堆积
from .crud.auth import cleanup_expired_tokens
with SessionLocal() as _db:
    _deleted = cleanup_expired_tokens(_db)
    if _deleted:
        print(f"[startup] 清理过期/已撤销 RefreshToken {_deleted} 条")

app = FastAPI(title="AI智能作业批改系统 - 后端服务", docs_url="/api/docs", redoc_url=None)

# CORS（与原 NestJS 配置一致）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080", "http://localhost:5173", "http://ai.dslcv.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ===== 全局异常处理（对齐 NestJS HttpExceptionFilter 的 { code, message } 格式）=====
@app.exception_handler(BizException)
async def biz_exception_handler(request: Request, exc: BizException):
    return JSONResponse({"code": exc.code, "message": exc.message}, status_code=exc.status_code)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse({"code": exc.status_code, "message": str(exc.detail)}, status_code=exc.status_code)


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    msgs = "; ".join(f"{'.'.join(str(p) for p in e.get('loc', []))}: {e.get('msg', '')}" for e in exc.errors())
    return JSONResponse({"code": 10001, "message": msgs}, status_code=422)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    traceback.print_exc()
    return JSONResponse({"code": 10000, "message": "服务器内部错误"}, status_code=500)


# ===== 静态文件服务（/uploads 不带 api 前缀）=====
app.mount("/uploads", StaticFiles(directory=str(settings.upload_path)), name="uploads")

# ===== 注册路由（全局前缀 /api）=====
for r in (auth, users, classes, assignments, submissions,
          correcting, dashboard, permissions, ai_models, ai_rules, upload,
          plagiarism, chat):
    app.include_router(r.router, prefix="/api")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.PORT, reload=True)
