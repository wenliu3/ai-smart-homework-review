"""权限相关 schemas"""
from pydantic import BaseModel


class MenuCreate(BaseModel):
    name: str
    code: str
    path: str
    component: str | None = None
    redirect: str | None = None
    type: str
    parentId: int | None = None
    icon: str | None = None
    sort: int = 0
    hidden: bool = False
    status: str = "active"
    meta: dict | None = None
    isSystem: bool = False


class MenuUpdate(BaseModel):
    name: str | None = None
    path: str | None = None
    component: str | None = None
    redirect: str | None = None
    type: str | None = None
    parentId: int | None = None
    icon: str | None = None
    sort: int | None = None
    hidden: bool | None = None
    status: str | None = None
    meta: dict | None = None


class RoleCreate(BaseModel):
    name: str
    code: str
    description: str = ""
    menuIds: list[str] = []
    permissions: list[str] = []
    isSystem: bool = False
    status: str = "active"


class RoleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    menuIds: list[str] | None = None
    permissions: list[str] | None = None
    status: str | None = None


class AssignMenusRequest(BaseModel):
    menuIds: list[str]
