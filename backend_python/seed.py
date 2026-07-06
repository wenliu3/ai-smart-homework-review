"""种子数据初始化: 菜单 / 角色 / 用户 / AI模型

运行方式:  python seed.py
"""
import sys
import io
import bcrypt

# Windows 控制台默认 GBK 编码，无法输出 emoji，强制 stdout 使用 utf-8
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
from app.database import engine, SessionLocal, Base
from app.models import User, Role, Menu, AiModel
from app.config import settings

# 先建表
Base.metadata.create_all(bind=engine)


def hash_pwd(pwd: str) -> str:
    return bcrypt.hashpw(pwd.encode("utf-8"), bcrypt.gensalt(10)).decode("utf-8")


def main():
    db = SessionLocal()
    try:
        print("🌱 开始初始化种子数据...\n")

        # ===== 1. 创建菜单 =====
        menus_data = [
            # 管理员
            {"name": "控制台", "code": "admin-dashboard", "path": "/admin/dashboard", "component": "views/dashboard/AdminDashboard", "type": "menu", "icon": "Monitor", "sort": 1, "status": "active", "is_system": True, "meta": {"title": "控制台"}},
            {"name": "系统管理", "code": "system", "path": "/system", "component": "Layout", "type": "menu", "icon": "Setting", "sort": 2, "status": "active", "is_system": True, "meta": {"title": "系统管理"}},
            {"name": "用户管理", "code": "system-users", "path": "/system/users", "component": "views/system/users/index", "type": "menu", "icon": "User", "sort": 1, "status": "active", "is_system": True, "meta": {"title": "用户管理"}},
            {"name": "角色管理", "code": "system-roles", "path": "/system/roles", "component": "views/system/roles/index", "type": "menu", "icon": "Avatar", "sort": 2, "status": "active", "is_system": True, "meta": {"title": "角色管理"}},
            {"name": "菜单管理", "code": "system-menus", "path": "/system/menus", "component": "views/system/menus/index", "type": "menu", "icon": "Menu", "sort": 3, "status": "active", "is_system": True, "meta": {"title": "菜单管理"}},
            {"name": "AI模型管理", "code": "system-ai-model", "path": "/system/ai_model", "component": "views/system/ai_model/index", "type": "menu", "icon": "Cpu", "sort": 4, "status": "active", "is_system": True, "meta": {"title": "AI模型管理"}},
            {"name": "班级管理", "code": "system-classes", "path": "/system/classes", "component": "views/system/classes/index", "type": "menu", "icon": "School", "sort": 5, "status": "active", "is_system": True, "meta": {"title": "班级管理"}},
            {"name": "操作日志", "code": "system-logs", "path": "/system/logs", "component": "views/system/logs/index", "type": "menu", "icon": "Document", "sort": 6, "status": "active", "is_system": True, "meta": {"title": "操作日志"}},
            # 教师
            {"name": "教学中心", "code": "teacher-dashboard", "path": "/teacher/dashboard", "component": "views/dashboard/TeacherDashboard", "type": "menu", "icon": "Monitor", "sort": 1, "status": "active", "is_system": True, "meta": {"title": "教学中心"}},
            {"name": "班级管理", "code": "teacher-classes", "path": "/teacher/classes", "component": "views/teacher/classes/index", "type": "menu", "icon": "School", "sort": 2, "status": "active", "is_system": True, "meta": {"title": "班级管理"}},
            {"name": "作业管理", "code": "teacher-assignments", "path": "/teacher/assignments", "component": "views/teacher/assignments/index", "type": "menu", "icon": "Notebook", "sort": 3, "status": "active", "is_system": True, "meta": {"title": "作业管理"}},
            {"name": "AI批改规则", "code": "teacher-ai-rules", "path": "/teacher/ai-rules", "component": "views/teacher/ai-rules/index", "type": "menu", "icon": "MagicStick", "sort": 4, "status": "active", "is_system": True, "meta": {"title": "AI批改规则"}},
            {"name": "批改管理", "code": "teacher-correcting", "path": "/teacher/correcting", "component": "views/teacher/correcting/index", "type": "menu", "icon": "EditPen", "sort": 5, "status": "active", "is_system": True, "meta": {"title": "批改管理"}},
            {"name": "文档查重", "code": "teacher-plagiarism", "path": "/teacher/plagiarism", "component": "views/teacher/plagiarism/index", "type": "menu", "icon": "CopyDocument", "sort": 6, "status": "active", "is_system": True, "meta": {"title": "文档查重"}},
            # 学生
            {"name": "学习中心", "code": "student-dashboard", "path": "/student/dashboard", "component": "views/dashboard/StudentDashboard", "type": "menu", "icon": "Monitor", "sort": 1, "status": "active", "is_system": True, "meta": {"title": "学习中心"}},
            {"name": "我的班级", "code": "student-classes", "path": "/student/classes", "component": "views/student/classes/index", "type": "menu", "icon": "School", "sort": 2, "status": "active", "is_system": True, "meta": {"title": "我的班级"}},
            {"name": "我的作业", "code": "student-assignments", "path": "/student/assignments", "component": "views/student/assignments/index", "type": "menu", "icon": "Notebook", "sort": 3, "status": "active", "is_system": True, "meta": {"title": "我的作业"}},
        ]

        top_codes = {"admin-dashboard", "system", "teacher-dashboard", "teacher-classes",
                     "teacher-assignments", "teacher-ai-rules", "teacher-correcting", "teacher-plagiarism",
                     "student-dashboard", "student-classes", "student-assignments"}
        parent_map = {"system-users": "system", "system-roles": "system", "system-menus": "system",
                      "system-ai-model": "system", "system-classes": "system", "system-logs": "system"}

        created_ids = {}
        existing = db.query(Menu).count()
        if existing == 0:
            for m in menus_data:
                if m["code"] in top_codes:
                    menu = Menu(**m)
                    db.add(menu)
                    db.commit()
                    db.refresh(menu)
                    created_ids[m["code"]] = menu.id
                    print(f"  ✅ 菜单: {m['name']}")
            for m in menus_data:
                if m["code"] in parent_map:
                    m2 = dict(m)
                    m2["parent_id"] = created_ids.get(parent_map[m["code"]])
                    menu = Menu(**m2)
                    db.add(menu)
                    db.commit()
                    db.refresh(menu)
                    created_ids[m["code"]] = menu.id
                    print(f"  ✅ 菜单: {m['name']} (子菜单)")
        else:
            print("  菜单已存在，跳过初始化")
            for m in db.query(Menu).all():
                created_ids[m.code] = m.id

        # ===== 2. 创建角色 =====
        all_ids = [str(v) for v in created_ids.values()]
        admin_ids = list(created_ids.values())
        admin_ids_str = [str(i) for i in admin_ids]
        teacher_ids = [str(created_ids[m["code"]]) for m in menus_data if m["path"].startswith("/teacher") and m["code"] in created_ids]
        student_ids = [str(created_ids[m["code"]]) for m in menus_data if m["path"].startswith("/student") and m["code"] in created_ids]

        # 合并所有需要排除的id，转集合快速匹配
        exclude_set = set(student_ids + teacher_ids)

        # 过滤，保留不在排除集合内的元素
        new_admin = [aid for aid in admin_ids_str if aid not in exclude_set]

        roles = [
            {"name": "超级管理员", "code": "superadmin", "description": "系统最高权限", "menu_ids": new_admin, "permissions": new_admin, "is_system": True, "status": "active"},
            {"name": "教师", "code": "teacher", "description": "教师角色", "menu_ids": teacher_ids, "permissions": teacher_ids, "is_system": True, "status": "active"},
            {"name": "学生", "code": "student", "description": "学生角色", "menu_ids": student_ids, "permissions": student_ids, "is_system": True, "status": "active"},
        ]
        for r in roles:
            if not db.query(Role).filter(Role.code == r["code"]).first():
                db.add(Role(**r))
                db.commit()
                print(f"  ✅ 角色: {r['name']}")
            else:
                print(f"  ⏭️  角色已存在: {r['name']}")

        # ===== 3. 创建测试账号 =====
        default_pwd = hash_pwd("123456789")
        admin_pwd = hash_pwd("admin123")
        accounts = [
            {"username": "admin", "email": "admin@nengdou.com", "password": admin_pwd, "name": "系统管理员", "role": "superadmin", "must_change_password": False},
            {"username": "teacher", "email": "teacher@nengdou.com", "password": default_pwd, "name": "张老师", "role": "teacher", "must_change_password": False},
            {"username": "2024001", "email": "2024001@school.edu", "password": default_pwd, "name": "张三", "role": "student", "student_id": "2024001", "must_change_password": True},
            {"username": "2024002", "email": "2024002@school.edu", "password": default_pwd, "name": "李四", "role": "student", "student_id": "2024002", "must_change_password": True},
            {"username": "2024003", "email": "2024003@school.edu", "password": default_pwd, "name": "王五", "role": "student", "student_id": "2024003", "must_change_password": True},
        ]
        for acc in accounts:
            if not db.query(User).filter(User.username == acc["username"]).first():
                db.add(User(**acc, status="active"))
                db.commit()
                ident = acc.get("student_id") or acc["username"]
                print(f"  ✅ 用户: {acc['name']} ({ident})")
            else:
                print(f"  ⏭️  用户已存在: {acc['name']}")

        # ===== 4. 初始化 AI 模型 =====
        ai_models = [
            {"code": "deepseek", "name": "DeepSeek", "provider": "DeepSeek", "model_name": "deepseek-chat", "base_url": "https://api.deepseek.com", "status": "active", "is_default": True, "total_usage": 0, "total_tokens": 0, "last_balance": 0},
            {"code": "mimo", "name": "小米", "provider": "小米", "model_name": "mimo-v2.5", "base_url": "https://api.xiaomimimo.com/v1", "status": "active", "is_default": False, "total_usage": 0, "total_tokens": 0, "last_balance": 0},
        ]
        for m in ai_models:
            if not db.query(AiModel).filter(AiModel.code == m["code"]).first():
                db.add(AiModel(**m))
                db.commit()
                print(f"  ✅ AI模型: {m['name']}")
            else:
                print(f"  ⏭️  AI模型已存在: {m['name']}")

        print("\n🎉 种子数据初始化完成！")
        print("================================")
        print("📋 登录账号:")
        print("  管理员: admin / admin123")
        print("  教师:   teacher / 123456789")
        print("  学生:   2024001 / 123456789 (张三)")
        print("  学生:   2024002 / 123456789 (李四)")
        print("  学生:   2024003 / 123456789 (王五)")
        print("================================")
    finally:
        db.close()


if __name__ == "__main__":
    main()
