"""班级路由 — 仅做路由转发，业务逻辑在 crud/class_.py"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from ..database import get_db
from ..deps import get_current_user
from ..models import User
from ..core.response import ok
from ..schemas.class_ import ClassCreate, ClassUpdate, JoinClassRequest, AddStudentsRequest, UpdateStudentStatusRequest
from ..crud import class_ as class_crud

router = APIRouter()


@router.get("/classes/list")
def get_list(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """分页查询班级列表 — 支持状态/教师过滤、名称/邀请码搜索，自动按角色做数据隔离"""
    q = request.query_params
    return ok(class_crud.get_list(
        db, page=int(q.get("page", 1)), limit=int(q.get("limit", 10)),
        status=q.get("status"), search=q.get("search"),
        teacher_id=int(q["teacherId"]) if q.get("teacherId") else None,
        sort_field=q.get("sortField", "createdAt"), sort_order=q.get("sortOrder", "desc"),
        user_id=current_user.id, user_role=current_user.role,
    ))


@router.get("/classes/{class_id}")
def get_detail(class_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """获取班级详情 — 含教师姓名"""
    return ok(class_crud.get_detail(db, class_id))


@router.post("/classes/create")
def create_class(body: ClassCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """创建班级 — 自动生成唯一邀请码"""
    return ok(class_crud.create_class(db, current_user.id, body.model_dump()))


@router.post("/classes/{class_id}/edit")
def update_class(class_id: int, body: ClassUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """更新班级信息 — 仅班级创建教师可操作"""
    return ok(class_crud.update_class(db, class_id, current_user.id, body.model_dump(exclude_unset=True)))


@router.post("/classes/{class_id}/close")
def disband_class(class_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """解散班级 — 状态置 disbanded，学生状态置 left"""
    return ok(class_crud.disband_class(db, class_id, current_user.id))


@router.post("/classes/{class_id}/regenerate-code")
def regenerate_code(class_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """重新生成班级邀请码"""
    return ok(class_crud.regenerate_code(db, class_id, current_user.id))


@router.get("/classes/{class_id}/students")
def get_students(class_id: int, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """分页查询班级学生列表 — 支持状态过滤、姓名/学号搜索"""
    q = request.query_params
    return ok(class_crud.get_students(
        db, class_id, page=int(q.get("page", 1)), limit=int(q.get("limit", 20)),
        status=q.get("status"), search=q.get("search"),
    ))


@router.post("/classes/{class_id}/students")
def add_students(class_id: int, body: AddStudentsRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """教师批量添加学生到班级"""
    return ok(class_crud.add_students(db, class_id, current_user.id, body.studentIds))


@router.post("/classes/join")
def join_class(body: JoinClassRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """学生通过邀请码加入班级"""
    return ok(class_crud.join_class(db, current_user.id, body.code))


@router.post("/classes/{class_id}/students/status")
def update_student_status(class_id: int, body: UpdateStudentStatusRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """教师批量更新班级学生状态"""
    return ok(class_crud.update_student_status(db, class_id, current_user.id, body.studentIds, body.status))


@router.post("/classes/{class_id}/leave")
def leave_class(class_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """学生退出班级"""
    return ok(class_crud.leave_class(db, class_id, current_user.id))
