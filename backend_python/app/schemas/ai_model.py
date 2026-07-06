"""AI 模型相关 schemas"""
from pydantic import BaseModel


class AiModelUpdate(BaseModel):
    name: str | None = None
    provider: str | None = None
    modelName: str | None = None
    baseUrl: str | None = None
    apiKey: str | None = None
    accessKey: str | None = None
    secretKey: str | None = None
    status: str | None = None
    isDefault: bool | None = None
