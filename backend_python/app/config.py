"""应用配置 - 通过环境变量 / .env 文件读取"""
import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # 数据库
    DATABASE_URL: str = "mysql+pymysql://root:123456@localhost:3306/ai_smart_review?charset=utf8mb4"

    # JWT
    JWT_SECRET: str = "ai-smart-review-secret-key-2026"
    JWT_EXPIRES_IN: int = 7200
    JWT_REFRESH_EXPIRES_IN: int = 604800

    # 服务
    PORT: int = 83
    DEFAULT_PASSWORD: str = "123456789"
    UPLOAD_DIR: str = "uploads"

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
