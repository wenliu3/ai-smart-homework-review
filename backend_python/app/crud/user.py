"""用户 CRUD"""
from sqlalchemy.orm import Session
from sqlalchemy import or_
from ..models import User
from ..core.security import hash_password, verify_password
from ..core.exceptions import BadRequestException, NotFoundException, ConflictException
from ..core.utils import camel_to_snake
from ..config import settings


def get_users(db: Session, page: int = 1, limit: int = 10,
              role: str | None = None, keyword: str | None = None,
              sort_field: str = "createdAt", sort_order: str = "desc") -> dict:
    """分页查询用户列表 — 支持按角色过滤、关键字模糊搜索、字段排序"""
    query = db.query(User)
    if role:
        query = query.filter(User.role == role)
    if keyword:
        kw = f"%{keyword}%"
        query = query.filter(or_(
            User.name.ilike(kw), User.username.ilike(kw),
            User.email.ilike(kw), User.student_id.ilike(kw),
        ))
    total = query.count()
    col = getattr(User, camel_to_snake(sort_field), User.created_at)
    col = col.asc() if sort_order == "asc" else col.desc()
    items = query.order_by(col).offset((page - 1) * limit).limit(limit).all()
    return {"items": [u.to_dict(exclude={"password"}) for u in items], "total": total, "page": page, "limit": limit}


def get_user_by_id(db: Session, user_id: int) -> User:
    """根据 ID 查询用户，不存在则抛出 NotFoundException"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise NotFoundException(10015, "用户不存在")
    return user


def create_user(db: Session, data: dict) -> dict:
    """创建用户 — 校验用户名/邮箱唯一性后写入，密码做 bcrypt 哈希"""
    username = data.get("username")
    email = data.get("email")
    existing = db.query(User).filter(or_(User.username == username, User.email == email)).first()
    if existing:
        raise ConflictException(10009, "用户名或邮箱已存在")
    user = User(
        username=username, email=email, password=hash_password(data.get("password", "")),
        name=data.get("name", ""), role=data.get("role", "student"),
        status=data.get("status", "active"), student_id=data.get("studentId"),
        phone=data.get("phone"), must_change_password=data.get("mustChangePassword", False),
    )
    db.add(user)
    db.commit()
    return user.to_dict(exclude={"password"})


def update_user(db: Session, user_id: int, data: dict) -> dict:
    """更新用户信息 — 若包含 password 字段则重新哈希"""
    user = get_user_by_id(db, user_id)
    for k, v in data.items():
        col = camel_to_snake(k)
        if col == "password" and v:
            user.password = hash_password(v)
        elif hasattr(user, col) and col != "id":
            setattr(user, col, v)
    db.commit()
    return user.to_dict(exclude={"password"})


def update_profile(db: Session, user: User, data: dict) -> dict:
    """用户更新自己的资料 — 不可修改 id 和 password"""
    for k, v in data.items():
        col = camel_to_snake(k)
        if hasattr(user, col) and col not in ("id", "password"):
            setattr(user, col, v)
    db.commit()
    return user.to_dict(exclude={"password"})


def _cleanup_assistant_relations(user_id: int) -> list[str]:
    """清理 PostgreSQL 会话库中该用户的所有 Agent 数据，返回其审批幂等键列表。

    - AgentSession 的 runs/steps/artifacts/messages 虽有 ondelete=CASCADE，
      但测试用 sqlite 默认不启用外键级联，因此显式逐表删除（生产 PG 级联只是兜底）。
    - LangGraph checkpoint 表（checkpoints/checkpoint_writes 等，thread_id=run.id）
      做 best-effort 原生 SQL 清理：表可能不存在（如测试环境），逐表 try/except。
    - 返回的幂等键供调用方清理 MySQL 侧 agent_action_executions 账本。
    """
    from sqlalchemy import bindparam, text
    from ..assistant_database import AssistantSessionLocal
    from ..models import (
        AgentApproval, AgentArtifact, AgentChatMessage,
        AgentMessage, AgentRun, AgentSession, AgentStep,
    )
    with AssistantSessionLocal() as sdb:
        # 删除前先收集会话/运行 ID 和审批幂等键（用于级联删除与跨库账本清理）
        session_ids = [
            row[0] for row in
            sdb.query(AgentSession.id).filter(AgentSession.user_id == user_id).all()
        ]
        run_ids = [
            row[0] for row in
            sdb.query(AgentRun.id).filter(AgentRun.user_id == user_id).all()
        ]
        approval_keys = [
            row[0] for row in
            sdb.query(AgentApproval.idempotency_key).filter(
                AgentApproval.requester_user_id == user_id,
            ).all()
        ]
        # 旧版聊天记录
        sdb.query(AgentChatMessage).filter(AgentChatMessage.teacher_id == user_id).delete()
        # 新多智能体表：按 run -> session 反向逐表显式删除
        if run_ids:
            sdb.query(AgentStep).filter(AgentStep.run_id.in_(run_ids)).delete(
                synchronize_session=False)
            sdb.query(AgentArtifact).filter(AgentArtifact.run_id.in_(run_ids)).delete(
                synchronize_session=False)
        if session_ids:
            sdb.query(AgentMessage).filter(AgentMessage.session_id.in_(session_ids)).delete(
                synchronize_session=False)
        sdb.query(AgentRun).filter(AgentRun.user_id == user_id).delete(
            synchronize_session=False)
        sdb.query(AgentSession).filter(AgentSession.user_id == user_id).delete(
            synchronize_session=False)
        sdb.query(AgentApproval).filter(AgentApproval.requester_user_id == user_id).delete(
            synchronize_session=False)
        sdb.commit()
        # LangGraph checkpoint 表 best-effort 清理（表可能不存在，逐表独立提交）
        if run_ids:
            stmt_template = "DELETE FROM {table} WHERE thread_id IN :ids"
            for table in ("checkpoint_writes", "checkpoint_blobs", "checkpoints"):
                try:
                    sdb.execute(
                        text(stmt_template.format(table=table)).bindparams(
                            bindparam("ids", expanding=True),
                        ),
                        {"ids": run_ids},
                    )
                    sdb.commit()
                except Exception:
                    sdb.rollback()
    return approval_keys


def _cleanup_user_relations(db: Session, user_id: int) -> None:
    """删除用户相关的所有关联记录（外键约束的表），并同步更新班级人数。

    注意：Agent 会话/运行/审批等数据在 PostgreSQL 会话库（AssistantBase），
    MySQL 业务库中没有这些表，需用独立的 AssistantSessionLocal 清理；
    RefreshToken/ClassStudent/Submission/审批账本/班级人数同步仍走 MySQL 业务库 db。
    """
    from ..models import (
        RefreshToken, ClassStudent, Submission,
        AgentActionExecution, Class as ClassModel,
    )
    # 先查出该学生所在的班级 ID（用于后续更新 student_count）
    affected_class_ids = [
        row[0] for row in
        db.query(ClassStudent.class_id).filter(ClassStudent.student_id == user_id).all()
    ]
    # 刷新令牌
    db.query(RefreshToken).filter(RefreshToken.user_id == user_id).delete()
    # PostgreSQL 会话库：聊天记录 + Agent 会话/运行/审批 + checkpoint
    approval_keys = _cleanup_assistant_relations(user_id)
    # MySQL 审批执行账本（通过该用户审批记录的幂等键关联）
    if approval_keys:
        db.query(AgentActionExecution).filter(
            AgentActionExecution.idempotency_key.in_(approval_keys),
        ).delete(synchronize_session=False)
    # 班级-学生关联
    db.query(ClassStudent).filter(ClassStudent.student_id == user_id).delete()
    # 提交记录
    db.query(Submission).filter(Submission.student_id == user_id).delete()
    db.flush()
    # 同步更新每个受影响班级的学生人数
    for cid in affected_class_ids:
        actual = db.query(ClassStudent).filter(
            ClassStudent.class_id == cid,
            ClassStudent.status == "active",
        ).count()
        db.query(ClassModel).filter(ClassModel.id == cid).update(
            {ClassModel.student_count: actual}
        )


def delete_user(db: Session, user_id: int) -> dict:
    """删除用户 — 先清理关联数据（刷新令牌/聊天/班级关联/提交），再删用户"""
    user = get_user_by_id(db, user_id)

    # 检查是否有不可自动清理的数据
    from ..models import Assignment, Class as ClassModel
    classes_count = db.query(ClassModel).filter(ClassModel.teacher_id == user_id).count()
    assignments_count = db.query(Assignment).filter(Assignment.teacher_id == user_id).count()

    if classes_count > 0 or assignments_count > 0:
        raise BadRequestException(
            10016,
            f"该用户关联了 {classes_count} 个班级和 {assignments_count} 个作业，"
            "请先将班级转移给其他教师或删除班级/作业后再删除此用户"
        )

    _cleanup_user_relations(db, user_id)
    db.delete(user)
    db.commit()
    return {"success": True, "message": "删除成功"}


def change_password(db: Session, user: User, current_password: str, new_password: str) -> dict:
    """用户修改自己的密码 — 需校验原密码"""
    if not verify_password(current_password, user.password):
        raise BadRequestException(10008, "当前密码错误")
    user.password = hash_password(new_password)
    db.commit()
    return {"success": True, "message": "密码修改成功"}


def update_user_password(db: Session, user_id: int, old_password: str, new_password: str) -> dict:
    """管理员修改指定用户密码 — 需校验旧密码"""
    user = get_user_by_id(db, user_id)
    if not verify_password(old_password, user.password):
        raise BadRequestException(10008, "当前密码错误")
    user.password = hash_password(new_password)
    db.commit()
    return {"success": True, "message": "密码修改成功"}


def reset_user_password(db: Session, user_id: int, new_password: str | None) -> dict:
    """管理员重置用户密码 — 重置后强制用户首次登录改密"""
    user = get_user_by_id(db, user_id)
    password = new_password or settings.DEFAULT_PASSWORD
    user.password = hash_password(password)
    user.must_change_password = True
    db.commit()
    return {"success": True, "message": f"密码已重置为: {password}"}


def import_users_batch(db: Session, users: list[dict]) -> dict:
    """批量导入用户 — 逐条校验唯一性，重复则记录到 failures"""
    results = {"success": True, "total": len(users), "successCount": 0, "failureCount": 0, "failures": []}
    default_pwd = settings.DEFAULT_PASSWORD
    for u in users:
        try:
            username = u.get("username") or u.get("studentId") or u.get("name")
            email = u.get("email") or f"{u.get('studentId')}@school.edu"
            student_id = str(u.get("studentId")) if u.get("studentId") else None
            existing = db.query(User).filter(or_(User.username == username, User.email == email)).first()
            if student_id:
                existing = existing or db.query(User).filter(User.student_id == student_id).first()
            if existing:
                results["failureCount"] += 1
                results["failures"].append({
                    "studentId": student_id or u.get("name"), "userName": u.get("name"),
                    "reason": "用户已存在（学号/邮箱/用户名重复）",
                })
                continue
            user = User(
                username=username, email=email, password=hash_password(default_pwd),
                name=u.get("name"), role=u.get("role", "student"),
                student_id=student_id, must_change_password=True, status="active",
            )
            db.add(user)
            db.commit()
            results["successCount"] += 1
        except Exception as e:
            db.rollback()
            results["failureCount"] += 1
            results["failures"].append({"studentId": u.get("studentId"), "userName": u.get("name"), "reason": str(e)})
    return results


def delete_users_batch(db: Session, user_ids: list[str]) -> dict:
    """批量删除用户 — 超级管理员不可删除，有班级/作业的教师不可删除"""
    from ..models import Assignment, Class as ClassModel
    results = {"success": True, "total": len(user_ids), "successCount": 0, "failureCount": 0, "failures": []}
    for uid in user_ids:
        try:
            user = db.query(User).filter(User.id == int(uid)).first()
            if not user:
                results["failureCount"] += 1
                results["failures"].append({"userId": uid, "reason": "用户不存在"})
                continue
            if user.role == "superadmin":
                results["failureCount"] += 1
                results["failures"].append({"userId": uid, "reason": "不能删除超级管理员"})
                continue
            # 检查教师关联
            classes_count = db.query(ClassModel).filter(ClassModel.teacher_id == user.id).count()
            assignments_count = db.query(Assignment).filter(Assignment.teacher_id == user.id).count()
            if classes_count > 0 or assignments_count > 0:
                results["failureCount"] += 1
                results["failures"].append({
                    "userId": uid,
                    "reason": f"关联了 {classes_count} 个班级和 {assignments_count} 个作业，请先处理",
                })
                continue
            _cleanup_user_relations(db, user.id)
            db.delete(user)
            db.commit()
            results["successCount"] += 1
        except Exception as e:
            db.rollback()
            results["failureCount"] += 1
            results["failures"].append({"userId": uid, "reason": str(e)})
    return results
