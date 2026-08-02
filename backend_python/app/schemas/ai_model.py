"""AI 模型相关 schemas"""
from pydantic import BaseModel, model_validator


class GradingStructurerBindingUpdate(BaseModel):
    enabled: bool
    modelCode: str | None = None

    @model_validator(mode="after")
    def require_model_when_enabled(self):
        if self.enabled and not (self.modelCode or "").strip():
            raise ValueError("启用独立结构化模型时必须选择模型")
        if not self.enabled:
            self.modelCode = None
        return self


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
