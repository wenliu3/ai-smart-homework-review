"""AI 规则相关 schemas"""
from pydantic import BaseModel


class AiRuleCreate(BaseModel):
    name: str
    description: str = ""
    modelType: str
    prompt: str
    status: str = "active"
    visibility: str = "private"
    tags: list[str] = []
    maxScore: int = 100
    createdBy: dict | None = None


class AiRuleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    modelType: str | None = None
    prompt: str | None = None
    status: str | None = None
    visibility: str | None = None
    tags: list[str] | None = None
    maxScore: int | None = None


class CopyRuleRequest(BaseModel):
    name: str | None = None
