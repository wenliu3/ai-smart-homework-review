"""应用配置 - 通过环境变量 / .env 文件读取"""
import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # 数据库
    DATABASE_URL: str = "mysql+pymysql://root:123456@localhost:3306/ai_smart_review?charset=utf8mb4"
    # AI 助手会话库（PostgreSQL）：存储 AI 聊天历史；业务数据仍在 MySQL
    ASSISTANT_DATABASE_URL: str = "postgresql://langgraph_user:123456@localhost:5432/ai_smart_review?sslmode=disable"
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT
    JWT_SECRET: str = "ai-smart-review-secret-key-2026"
    JWT_EXPIRES_IN: int = 7200
    JWT_REFRESH_EXPIRES_IN: int = 604800

    # 服务
    PORT: int = 83
    DEFAULT_PASSWORD: str = "123456789"
    UPLOAD_DIR: str = "uploads"
    # 助手流式 worker 并发上限：必须低于会话库连接池容量
    # （assistant_database.py: pool_size=5 + max_overflow=10 = 15），
    # 留出余量给普通请求，避免满载时 worker 等待连接直至池超时（默认 30 秒）。
    AGENT_STREAM_MAX_CONCURRENCY: int = 12
    # 多智能体助手总开关（规划 5.6）：False 时新版 /assistant/runs/stream 整体关闭
    MULTI_AGENT_ENABLED: bool = True
    # 教师白名单灰度：逗号分隔教师 ID；空串 = 全部教师放行。
    # 只约束教师角色，学生/管理员不受影响。
    MULTI_AGENT_TEACHER_WHITELIST: str = ""

    def multi_agent_teacher_allowed(self, teacher_id: int) -> bool:
        whitelist = self.MULTI_AGENT_TEACHER_WHITELIST.strip()
        if not whitelist:
            return True
        allowed = {
            item.strip()
            for item in whitelist.split(",")
            if item.strip()
        }
        return str(teacher_id) in allowed

    @property
    def upload_path(self) -> Path:
        p = Path(self.UPLOAD_DIR)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def plagiarism_path(self) -> Path:
        """文档查重临时文件目录（独立子目录，缓存过期自动清理）"""
        p = self.upload_path / "plagiarism_tmp"
        p.mkdir(parents=True, exist_ok=True)
        return p


settings = Settings()
