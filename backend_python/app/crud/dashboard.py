"""看板统计 CRUD"""
import time
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..models import User, Class, ClassStudent, Assignment, Submission, AiModel
from ..core.utils import now

START_TIME = time.time()


def _max_score(assignment):
    """获取作业的满分值(从 aiRule.maxScore 读取，默认 100)"""
    if assignment.ai_rule and isinstance(assignment.ai_rule, dict):
        return assignment.ai_rule.get("maxScore", 100)
    return 100


# ========== 管理员 ==========

def get_admin_overview(db: Session) -> dict:
    """管理员看板概览 — 用户数/班级数/作业数/提交数/AI模型数 + 分布统计"""
    total_users = db.query(User).count()
    total_classes = db.query(Class).count()
    total_assignments = db.query(Assignment).count()
    total_submissions = db.query(Submission).count()
    ai_model_count = db.query(AiModel).count()

    role_rows = db.query(User.role, func.count(User.id)).group_by(User.role).all()
    user_role_distribution = [
        {"role": r, "count": c, "percentage": round(c / total_users * 100) if total_users else 0}
        for r, c in role_rows
    ]
    class_rows = db.query(Class.status, func.count(Class.id)).group_by(Class.status).all()
    class_status_distribution = [
        {"status": s, "count": c, "percentage": round(c / total_classes * 100) if total_classes else 0}
        for s, c in class_rows
    ]
    sub_rows = db.query(Submission.status, func.count(Submission.id)).group_by(Submission.status).all()
    submission_status_distribution = [
        {"status": s, "count": c, "percentage": round(c / total_submissions * 100) if total_submissions else 0}
        for s, c in sub_rows
    ]
    return {
        "totalUsers": total_users, "totalClasses": total_classes,
        "totalAssignments": total_assignments, "totalSubmissions": total_submissions,
        "aiModelCount": ai_model_count,
        "userRoleDistribution": user_role_distribution,
        "classStatusDistribution": class_status_distribution,
        "submissionStatusDistribution": submission_status_distribution,
        "lastUpdated": now().isoformat(),
    }


def get_ai_model_stats(db: Session) -> dict:
    """AI 模型使用统计 — 各模型的在线状态/余额/用量/Token数"""
    models = db.query(AiModel).all()
    result = {}
    for m in models:
        result[m.code] = {
            "isOnline": m.status == "active",
            "balance": str(m.last_balance or 0),
            "totalUsage": m.total_usage, "totalTokens": m.total_tokens,
            "todayUsage": 0,
            "lastBalanceCheck": m.last_balance_check.isoformat() if m.last_balance_check else None,
        }
    return result


def get_recent_users(db: Session, limit: int = 10) -> dict:
    """获取最近注册的用户列表"""
    users = db.query(User).order_by(User.created_at.desc()).limit(limit).all()
    return {"users": [{
        "id": str(u.id), "name": u.name, "role": u.role, "email": u.email,
        "createdAt": u.created_at.isoformat() if u.created_at else None, "status": u.status,
    } for u in users]}


def get_health() -> dict:
    """系统健康检查 — 返回运行时长和时间戳"""
    return {"status": "ok", "uptime": time.time() - START_TIME, "timestamp": now().isoformat()}


# ========== 教师 ==========

def get_teacher_stats(db: Session, teacher_id: int) -> dict:
    """教师看板统计 — 班级数/学生数/作业数/待批改/提交率/分数分析/作业状态分布"""
    my_classes = db.query(Class).filter(Class.teacher_id == teacher_id, Class.status == "active").all()
    class_ids = [c.id for c in my_classes]
    total_students = db.query(ClassStudent).filter(ClassStudent.class_id.in_(class_ids), ClassStudent.status == "active").count()
    my_assignments = db.query(Assignment).filter(Assignment.teacher_id == teacher_id).all()
    assignment_ids = [a.id for a in my_assignments]

    total_submissions = db.query(Submission).filter(Submission.assignment_id.in_(assignment_ids)).count()
    pending_reviews = db.query(Submission).filter(Submission.assignment_id.in_(assignment_ids), Submission.status == "submitted").count()

    class_submission_stats = []
    for c in my_classes:
        students = db.query(ClassStudent).filter(ClassStudent.class_id == c.id, ClassStudent.status == "active").count()
        assgn_ids = [a.id for a in my_assignments if any(cl.get("id") == str(c.id) for cl in (a.classes or []))]
        submitted = db.query(Submission).filter(Submission.assignment_id.in_(assgn_ids), Submission.class_id == c.id, Submission.status != "draft").count()
        rate = min(100, round((submitted / students) * 100)) if students else 0
        class_submission_stats.append({"classId": str(c.id), "className": c.name, "totalStudents": students, "submittedCount": submitted, "submissionRate": rate})

    submissions = db.query(Submission).filter(
        Submission.assignment_id.in_(assignment_ids),
        Submission.status.in_(["ai_reviewed", "teacher_reviewed"]),
    ).all()
    total_ai_pct = total_tch_pct = ai_count = tch_count = excellent = passed = scored = 0
    for s in submissions:
        a = next((x for x in my_assignments if x.id == s.assignment_id), None)
        ms = _max_score(a) if a else 100
        ts = s.teacher_score if s.teacher_score is not None else (s.ai_score or 0)
        pct = (ts / ms) * 100 if ms > 0 else 0
        scored += 1
        if s.teacher_score is not None:
            total_tch_pct += pct; tch_count += 1
        if s.ai_score is not None:
            total_ai_pct += (s.ai_score / ms) * 100 if ms > 0 else 0; ai_count += 1
        if pct >= 85: excellent += 1
        if pct >= 60: passed += 1

    today_start = now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_reviews = db.query(Submission).filter(Submission.assignment_id.in_(assignment_ids), Submission.status == "ai_reviewed", Submission.updated_at >= today_start).count()

    total_assns = len(my_assignments)
    draft_count = sum(1 for a in my_assignments if a.status == "draft")
    published_count = sum(1 for a in my_assignments if a.status == "published")
    terminated_count = sum(1 for a in my_assignments if a.status == "terminated")
    assignment_status_distribution = [
        {"status": "draft", "count": draft_count, "percentage": round(draft_count / total_assns * 100) if total_assns else 0},
        {"status": "published", "count": published_count, "percentage": round(published_count / total_assns * 100) if total_assns else 0},
        {"status": "terminated", "count": terminated_count, "percentage": round(terminated_count / total_assns * 100) if total_assns else 0},
    ]
    ai_reviewed_count = sum(1 for s in submissions if s.ai_score is not None)
    return {
        "myClasses": len(my_classes), "myAssignments": total_assns,
        "pendingReviews": pending_reviews, "totalStudents": total_students,
        "classSubmissionStats": class_submission_stats,
        "assignmentStatusDistribution": assignment_status_distribution,
        "aiReviewStats": {"todayReviews": today_reviews, "totalReviews": ai_reviewed_count, "failedReviews": 0, "pendingReviews": pending_reviews},
        "studentScoreAnalysis": {
            "avgAiScore": round(total_ai_pct / ai_count) if ai_count else 0,
            "avgTeacherScore": round(total_tch_pct / tch_count) if tch_count else 0,
            "scoreDifference": round((total_tch_pct / tch_count) - (total_ai_pct / ai_count)) if (tch_count and ai_count) else 0,
            "excellentRate": round(excellent / scored * 100) if scored else 0,
            "passRate": round(passed / scored * 100) if scored else 0,
        },
    }


def get_teacher_pending_tasks(db: Session, teacher_id: int) -> dict:
    """教师待办任务 — 即将截止的作业 + 最近待批改的提交"""
    assignments = db.query(Assignment).filter(Assignment.teacher_id == teacher_id, Assignment.status == "published").order_by(Assignment.end_date.asc()).limit(5).all()
    items = []
    for a in assignments:
        cids = [int(c["id"]) for c in (a.classes or []) if c.get("id")]
        total_students = db.query(ClassStudent).filter(ClassStudent.class_id.in_(cids), ClassStudent.status == "active").count()
        submitted = db.query(Submission).filter(Submission.assignment_id == a.id, Submission.status != "draft").count()
        items.append({
            "id": str(a.id), "title": a.title, "classCount": len(a.classes or []),
            "submissionRate": round((submitted / total_students) * 100) if total_students else 0,
            "status": a.status, "endDate": a.end_date.isoformat() if a.end_date else None,
        })
    all_ids = [a.id for a in assignments]
    pending_subs = db.query(Submission).filter(Submission.assignment_id.in_(all_ids), Submission.status == "submitted").order_by(Submission.submitted_at.desc()).limit(5).all()
    submissions = []
    for s in pending_subs:
        student = db.query(User).filter(User.id == s.student_id).first()
        a = next((x for x in assignments if x.id == s.assignment_id), None)
        submissions.append({
            "id": str(s.id), "studentName": student.name if student else "",
            "assignmentTitle": a.title if a else "", "status": s.status,
            "submittedAt": s.submitted_at.isoformat() if s.submitted_at else None, "aiScore": s.ai_score,
        })
    return {"assignments": items, "submissions": submissions}


def get_teacher_performance_summary() -> dict:
    return {"messages": []}


def get_teacher_quick_actions() -> dict:
    return {"actions": [{"type": "create_assignment", "label": "发布作业", "path": "/teacher/assignments"}]}


# ========== 学生 ==========

def get_student_stats(db: Session, student_id: int) -> dict:
    """学生看板统计 — 已完成提交数/平均分/加入班级数/按时提交率/待办/成绩分布"""
    all_subs = db.query(Submission).filter(
        Submission.student_id == student_id,
        Submission.status.in_(["submitted", "ai_reviewed", "teacher_reviewed"]),
    ).order_by(Submission.submitted_at.desc()).all()
    reviewed_subs = [s for s in all_subs if s.status in ("ai_reviewed", "teacher_reviewed")]
    joined_classes = db.query(ClassStudent).filter(ClassStudent.student_id == student_id, ClassStudent.status == "active").count()

    student_classes = db.query(ClassStudent).filter(ClassStudent.student_id == student_id, ClassStudent.status == "active").all()
    class_ids = [sc.class_id for sc in student_classes]
    str_class_ids = [str(c) for c in class_ids]
    published = db.query(Assignment).filter(Assignment.status == "published").all()
    published = [a for a in published if any(c.get("id") in str_class_ids for c in (a.classes or []))]

    n = now()
    pending_count = 0
    for a in published:
        sub = next((s for s in all_subs if s.assignment_id == a.id), None)
        if not sub and a.end_date and a.end_date > n:
            pending_count += 1

    on_time = 0
    for s in all_subs:
        a = next((x for x in published if x.id == s.assignment_id), None)
        if a and s.submitted_at and a.end_date and s.submitted_at <= a.end_date:
            on_time += 1
    on_time_rate = round((on_time / len(all_subs)) * 100) if all_subs else 0

    total_pct = scored = excellent = good = passed = failed = perfect = 0
    for s in reviewed_subs:
        a = next((x for x in published if x.id == s.assignment_id), None)
        ms = _max_score(a) if a else 100
        score = s.teacher_score if s.teacher_score is not None else (s.ai_score or 0)
        pct = (score / ms) * 100 if ms > 0 else 0
        total_pct += pct; scored += 1
        if pct >= 90: excellent += 1
        elif pct >= 75: good += 1
        elif pct >= 60: passed += 1
        else: failed += 1
        if pct >= 98: perfect += 1
    avg_score = round(total_pct / scored) if scored else 0

    status_map = {}
    for s in all_subs:
        label = "已批改" if s.status == "teacher_reviewed" else ("AI已评" if s.status == "ai_reviewed" else "待批改")
        status_map[label] = status_map.get(label, 0) + 1
    total = len(all_subs)
    submission_status_stats = [{"status": k, "count": v, "percentage": round(v / total * 100) if total else 0} for k, v in status_map.items()]

    recent = []
    for s in all_subs[:5]:
        a = next((x for x in published if x.id == s.assignment_id), None)
        ms = _max_score(a) if a else 100
        recent.append({
            "id": str(s.id), "assignmentTitle": a.title if a else "",
            "aiScore": s.ai_score, "teacherScore": s.teacher_score, "maxScore": ms,
            "submittedAt": s.submitted_at.isoformat() if s.submitted_at else None, "status": s.status,
        })
    return {
        "completedSubmissions": len(reviewed_subs), "averageScore": avg_score,
        "joinedClasses": joined_classes, "onTimeRate": on_time_rate,
        "pendingAssignments": pending_count, "submissionStatusStats": submission_status_stats,
        "performanceAnalysis": {
            "excellentCount": excellent, "goodCount": good, "passCount": passed,
            "failCount": failed, "totalCount": scored, "perfectScoreCount": perfect, "classRanking": "",
        },
        "pendingAssignmentsList": [], "recentSubmissions": recent,
    }


def get_student_learning_progress() -> dict:
    return {"progress": []}


def get_student_achievements() -> dict:
    return {"achievements": []}


def get_student_study_recommendations() -> dict:
    return {"recommendations": []}
