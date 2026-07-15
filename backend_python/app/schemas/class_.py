"""班级相关 schemas"""
from pydantic import BaseModel


class ClassCreate(BaseModel):
    name: str
    description: str = ""
    code: str | None = None
    maxStudents: int = 200
    teacherId: int | None = None  # 管理员代教师创建时指定


class ClassUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    maxStudents: int | None = None
    teacherId: int | None = None
    status: str | None = None
    status: str | None = None


class JoinClassRequest(BaseModel):
    code: str


class AddStudentsRequest(BaseModel):
    studentIds: list[str]


class UpdateStudentStatusRequest(BaseModel):
    studentIds: list[str]
    status: str
