"""生成测试数据: 教师/学生/班级/作业/提交/AI规则/聊天记录

运行方式:  python generate_test_data.py
安全: 使用 insert on duplicate / 检查已存在记录，可重复执行
"""
import sys
import io
import random
import bcrypt
from datetime import datetime, timedelta, timezone

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from app.database import engine, SessionLocal, Base
from app.models import (
    User, Class, ClassStudent, Assignment, Submission,
    AiRule, AiModel, AgentChatMessage,
)
from app.config import settings

Base.metadata.create_all(bind=engine)


def hash_pwd(pwd: str) -> str:
    return bcrypt.hashpw(pwd.encode("utf-8"), bcrypt.gensalt(10)).decode("utf-8")


# ══════════════════════════════════════════════════════════════
# 数据定义
# ══════════════════════════════════════════════════════════════

DEFAULT_PWD = hash_pwd("123456789")

# --- 教师 ---
TEACHERS = [
    {"username": "teacher2", "email": "teacher2@nengdou.com", "name": "李芳", "role": "teacher"},
    {"username": "teacher3", "email": "teacher3@nengdou.com", "name": "王建国", "role": "teacher"},
    {"username": "teacher4", "email": "teacher4@nengdou.com", "name": "刘敏", "role": "teacher"},
]

# --- 学生 (30人) ---
STUDENT_NAMES = [
    "赵一", "钱二", "孙三", "周杰", "吴桐", "郑爽", "王磊", "冯思雨", "陈晨", "褚明",
    "卫兰", "蒋涛", "沈月", "韩雪", "杨光", "朱晓", "秦风", "许诺", "张弛", "何苗",
    "吕梁", "施雅", "魏然", "华筝", "陶然", "姜维", "戚薇", "谢安", "邹宇", "柏灵",
]

STUDENTS = [
    {"username": f"2024{40+i:03d}", "email": f"2024{40+i:03d}@school.edu",
     "name": name, "role": "student", "student_id": f"2024{40+i:03d}", "must_change_password": True}
    for i, name in enumerate(STUDENT_NAMES, start=1)
]

# --- AI 批改规则 ---
AI_RULES = [
    {
        "name": "议论文评分标准", "description": "适用于议论文体裁的AI批改规则，从论点、论据、论证三个维度评分",
        "model_type": "text", "prompt": "你是一位语文老师，请对以下议论文进行批改。评分维…",
        "visibility": "public", "tags": ["议论文", "语文", "高中"], "max_score": 100,
    },
    {
        "name": "英语作文评分标准", "description": "适用于英语写作的评分规则，关注语法、词汇、结构",
        "model_type": "text", "prompt": "You are an English teacher. Please grade the following essay…",
        "visibility": "public", "tags": ["英语", "作文"], "max_score": 100,
    },
    {
        "name": "编程作业评分标准", "description": "适用于编程类作业的评分规则，关注代码正确性、风格、效率",
        "model_type": "text", "prompt": "你是一位编程老师，请对以下代码作业进行批改…",
        "visibility": "public", "tags": ["编程", "Python", "Java"], "max_score": 100,
    },
    {
        "name": "实验报告评分标准", "description": "适用于理工科实验报告的评分规则",
        "model_type": "text", "prompt": "你是一位实验课老师，请对以下实验报告进行批改…",
        "visibility": "public", "tags": ["实验报告", "理科"], "max_score": 100,
    },
]

# --- 班级 (每个教师 2~3 个班) ---
CLASSES_BY_TEACHER = {
    "teacher": [
        {"name": "计算机科学导论", "description": "计算机专业大一新生导论课程，涵盖计算机发展历史、基本原理和前沿技术"},
        {"name": "Python程序设计", "description": "面向大二学生开设的Python语言课程，从基础语法到项目实战"},
        {"name": "数据结构与算法", "description": "计算机专业核心课程，涵盖线性表、树、图、排序算法等内容"},
    ],
    "teacher2": [
        {"name": "高等数学A(上)", "description": "工科专业必修课，涵盖极限、微积分、级数等内容"},
        {"name": "线性代数", "description": "讲授矩阵理论、线性方程组、特征值与特征向量等内容"},
    ],
    "teacher3": [
        {"name": "大学英语I", "description": "大一英语基础课程，培养听说读写综合能力"},
        {"name": "大学英语II", "description": "英语进阶课程，侧重学术英语和跨文化交际"},
        {"name": "商务英语", "description": "面向商科学生的英语课程，涵盖商务场景听说读写"},
    ],
    "teacher4": [
        {"name": "大学物理A", "description": "工科专业物理基础课程，涵盖力学、热学、电磁学"},
        {"name": "马克思主义原理", "description": "思政必修课，学习马克思主义基本原理"},
    ],
}

# --- 作业标题模板 (按学科) ---
ASSIGNMENT_TITLES = {
    "computer": [
        {"title": "计算机发展史小论文", "description": "请撰写一篇关于计算机发展史的小论文，不少于800字。要求包含：1) 计算机的四个发展阶段；2) 每个阶段的代表性技术和人物；3) 你对未来计算机发展的展望。"},
        {"title": "Python基础语法练习", "description": "完成以下Python基础语法练习：1) 变量与数据类型；2) 条件判断与循环；3) 函数定义与调用。提交.py文件。"},
        {"title": "面向对象编程作业", "description": "设计一个学生成绩管理系统，使用面向对象编程思想。要求至少包含Student、Course、Grade三个类。提交代码和简要设计文档。"},
        {"title": "二分查找与排序算法实现", "description": "实现二分查找和至少两种排序算法（冒泡、快排、归并任选），分析时间复杂度。提交代码和测试用例。"},
        {"title": "二叉树遍历实验", "description": "实现二叉树的三种遍历方式（前序、中序、后序），并对给定测试数据进行遍历输出。提交代码和运行截图。"},
    ],
    "math": [
        {"title": "极限计算练习", "description": "完成10道极限计算题，要求写出详细解题步骤。涵盖：重要极限、洛必达法则、等价无穷小等。"},
        {"title": "不定积分计算", "description": "完成以下不定积分计算题，要求写出完整推导过程。包括换元积分法和分部积分法。"},
        {"title": "矩阵运算练习", "description": "完成矩阵的加法、乘法、转置、求逆运算练习。共8题，要求写出计算过程。"},
        {"title": "特征值与特征向量", "description": "求解给定矩阵的特征值和特征向量，并判断矩阵是否可对角化。提交解题过程。"},
    ],
    "english": [
        {"title": "My College Life 英语作文", "description": "Write an essay about your college life (at least 200 words). Include your study routine, extracurricular activities, and future plans."},
        {"title": "英语阅读理解练习", "description": "完成四篇阅读理解练习，每篇回答5个问题。文章主题涉及科技、文化、教育、环境。"},
        {"title": "英语演讲视频作业", "description": "录制一段2-3分钟的英语演讲视频，主题为'The Impact of AI on Education'。提交视频文件和演讲稿文本。"},
        {"title": "英语翻译练习", "description": "完成5段中译英和5段英译中翻译练习。题材包括新闻报道、科技文献、文学散文。"},
        {"title": "商务英语邮件写作", "description": "根据给定场景撰写3封商务英语邮件：询价邮件、投诉回复、会议邀请。注意格式规范和语气得体。"},
    ],
    "physics": [
        {"title": "牛顿定律应用练习", "description": "完成6道牛顿定律应用题，涉及受力分析、运动方程建立和求解。要求画出受力分析图。"},
        {"title": "电磁感应实验报告", "description": "完成电磁感应实验，记录实验数据并撰写实验报告。包含实验目的、原理、步骤、数据分析和结论。"},
        {"title": "热力学第一定律习题", "description": "完成热力学第一定律相关习题，涉及理想气体状态方程、热容量、绝热过程等概念。"},
    ],
    "politics": [
        {"title": "矛盾论读书笔记", "description": "阅读《矛盾论》节选，撰写一篇不少于1000字的读书笔记。要求结合现实生活分析矛盾的普遍性和特殊性。"},
        {"title": "社会实践调研报告", "description": "选择一个社会现象进行调研（如垃圾分类、共享经济等），运用马克思主义原理进行分析，撰写调研报告。"},
    ],
}

# 作业标题与学科的映射（用于后续匹配）
TITLE_CATEGORY_MAP = {}
for cat, titles in ASSIGNMENT_TITLES.items():
    for t in titles:
        TITLE_CATEGORY_MAP[t["title"]] = cat


# --- AI 批改结果模板 ---
AI_REVIEW_TEMPLATES = [
    {"score": 92, "content": "整体完成度很高，论点明确，论证过程严谨。建议在实例引用方面可以更加丰富。语言表达流畅，结构完整。\n\n【评分明细】\n- 内容完整性 (30/30): 涵盖所有要求的知识点\n- 逻辑结构 (28/30): 层次分明，过渡自然\n- 语言表达 (18/20): 用词准确，语句通顺\n- 创新思维 (16/20): 有一定独立思考"},
    {"score": 85, "content": "作业完成情况良好，基本掌握了核心知识点。部分计算步骤可以更详细，建议补充推导过程。\n\n【评分明细】\n- 正确率 (25/30): 大部分答案正确\n- 解题步骤 (22/25): 个别题目缺少关键步骤\n- 规范性 (20/25): 格式基本规范\n- 创新性 (18/20): 有个别独到见解"},
    {"score": 78, "content": "整体表现中规中矩，部分知识点掌握不够扎实。建议加强对核心概念的理解，多做练习巩固。\n\n【评分明细】\n- 内容完整性 (22/30): 缺少部分要点\n- 逻辑结构 (20/30): 部分段落衔接不够自然\n- 语言表达 (18/20): 表达清晰\n- 深度思考 (18/20): 有一定思考深度"},
    {"score": 66, "content": "基本完成了作业要求，但存在以下问题：1) 部分概念理解有误；2) 解题步骤不够完整；3) 缺少必要的分析说明。请认真复习相关知识点后重新提交。\n\n【评分明细】\n- 正确率 (20/30): 存在多处错误\n- 解题步骤 (16/25): 步骤不完整\n- 规范性 (15/25): 格式需要改进\n- 态度 (15/20): 看得出来努力了"},
    {"score": 95, "content": "优秀！作业完成得非常出色，对知识点的理解深入透彻。分析角度新颖，论证充分有力。继续保持！\n\n【评分明细】\n- 内容完整性 (30/30): 完美覆盖所有要点\n- 逻辑结构 (29/30): 逻辑严密，结构清晰\n- 语言表达 (19/20): 表达精准流畅\n- 创新思维 (17/20): 视角独特"},
    {"score": 72, "content": "作业达到了基本要求，但在深度和广度上还有提升空间。建议多参考相关文献，拓展知识面。\n\n【评分明细】\n- 内容完整性 (20/30): 核心内容基本涵盖\n- 逻辑结构 (22/30): 结构合理但细节不够\n- 语言表达 (16/20): 表述基本清楚\n- 文献引用 (14/20): 参考文献不足"},
]

TEACHER_REVIEW_TEMPLATES = [
    {"score": 90, "content": "批改认真，整体完成度好。你的分析能力有了明显进步，继续保持！注意第三题的计算过程可以更简洁一些。"},
    {"score": 82, "content": "不错，大部分题目都做对了。有几个小错误我已经标注了，仔细看看。下次注意书写规范。"},
    {"score": 75, "content": "做得还可以，但是有几个关键概念没有理解透彻。请着重复习课堂笔记中的第三章内容，有疑问随时来问。"},
    {"score": 88, "content": "很好！看得出来你很用心。特别是实验数据分析部分做得非常仔细。建议在结论部分可以更加深入地讨论误差来源。"},
    {"score": 68, "content": "作业整体完成度一般，有些题目没有按照要求完成。请对照标准答案重新检查，下周之前补交一份修改版。"},
]

# --- 学生提交内容样本 ---
SUBMISSION_CONTENTS = [
    "在本论文中，我将围绕计算机的发展历程展开论述。第一代计算机采用电子管作为主要元件，体积庞大、功耗惊人。ENIAC是这一时期的代表，它重达30吨，占地170平方米。第二代计算机引入了晶体管技术，使计算机体积大幅缩小，可靠性显著提升。第三代计算机开始使用集成电路，计算速度达到每秒百万次级别。第四代计算机采用超大规模集成电路，个人计算机(PC)应运而生，互联网技术也随之蓬勃发展。\n\n展望未来，我认为量子计算和生物计算将成为下一代计算机的核心技术。量子计算机利用量子叠加态进行计算，在某些特定问题上将展现出远超经典计算机的性能。而生物计算机则可能彻底改变我们对'计算'的理解。",
    "def fibonacci(n):\n    '''计算斐波那契数列的第n项'''\n    if n <= 0:\n        return 0\n    elif n == 1:\n        return 1\n    else:\n        a, b = 0, 1\n        for _ in range(2, n + 1):\n            a, b = b, a + b\n        return b\n\n\ndef is_prime(num):\n    '''判断一个数是否为素数'''\n    if num < 2:\n        return False\n    for i in range(2, int(num ** 0.5) + 1):\n        if num % i == 0:\n            return False\n    return True\n\n\n# 测试代码\nif __name__ == '__main__':\n    print('斐波那契数列前10项:')\n    for i in range(1, 11):\n        print(f'F({i}) = {fibonacci(i)}')\n    \n    print('\\n100以内的素数:')\n    primes = [n for n in range(2, 101) if is_prime(n)]\n    print(primes)",
    "My college life has been a wonderful journey so far. When I first entered the university, I was both excited and nervous. The campus is beautiful with lots of green trees and modern buildings.\n\nMy daily routine starts at 7 AM. After breakfast, I attend lectures from 8 AM to noon. In the afternoon, I usually study in the library or work on assignments. I also joined the debate club, which has helped me improve my public speaking skills.\n\nIn the future, I plan to pursue a master's degree in computer science. I believe that artificial intelligence will play a crucial role in shaping our world, and I want to be part of that transformation.",
    "解：\n(1) 计算极限 lim(x→0) sin(3x)/x\n   使用重要极限 lim(x→0) sin(x)/x = 1\n   lim(x→0) sin(3x)/x = lim(x→0) 3·sin(3x)/(3x) = 3·1 = 3\n\n(2) 计算极限 lim(x→∞) (1 + 1/x)^x\n   这是重要极限，结果为 e\n\n(3) 计算极限 lim(x→0) (e^x - 1)/x\n   使用洛必达法则：lim(x→0) (e^x - 1)/x = lim(x→0) e^x/1 = 1",
    "1. 求矩阵 A = [[2, 1], [1, 2]] 的特征值和特征向量\n\n解：\n特征方程 |A - λI| = 0\n|2-λ  1  |\n|1   2-λ| = 0\n\n(2-λ)² - 1 = 0\nλ² - 4λ + 3 = 0\n(λ-1)(λ-3) = 0\n\n所以特征值为 λ₁ = 1, λ₂ = 3\n\n当 λ₁ = 1 时：(A-I)x = 0\n[[1, 1], [1, 1]] [x₁, x₂]ᵀ = 0\n解得 x₁ = -x₂，特征向量为 k₁[1, -1]ᵀ\n\n当 λ₂ = 3 时：(A-3I)x = 0\n[[-1, 1], [1, -1]] [x₁, x₂]ᵀ = 0\n解得 x₁ = x₂，特征向量为 k₂[1, 1]ᵀ",
    "This essay explores the impact of artificial intelligence on modern education. AI has revolutionized the way students learn and teachers teach. With intelligent tutoring systems, students can receive personalized learning experiences tailored to their individual needs.\n\nMoreover, AI-powered grading tools can save teachers countless hours on routine assessment tasks, allowing them to focus more on providing meaningful feedback and guidance. However, we must also be cautious about over-reliance on technology. The human element in education remains irreplaceable.\n\nIn conclusion, AI should be viewed as a powerful assistant rather than a replacement for human educators.",
    "实验目的：验证法拉第电磁感应定律\n\n实验器材：线圈、磁铁、检流计、导线、铁芯\n\n实验步骤：\n1. 将线圈与检流计串联连接\n2. 将条形磁铁快速插入线圈，观察检流计指针偏转\n3. 将磁铁从线圈中快速抽出，观察检流计指针偏转方向\n4. 改变磁铁运动速度，观察检流计偏转幅度变化\n\n实验数据：\n| 磁铁运动速度 | 检流计偏转格数 |\n| 慢速 | 3格 |\n| 中速 | 7格 |\n| 快速 | 12格 |\n\n实验结论：感应电动势的大小与磁通量变化率成正比，符合法拉第电磁感应定律。",
    "矛盾存在于一切事物的发展过程中，这是矛盾的普遍性原理。毛泽东同志在《矛盾论》中指出，事物发展的根本原因在于事物内部的矛盾性。\n\n矛盾的普遍性体现在两个方面：一是矛盾存在于一切事物的发展过程中；二是每一事物的发展过程中存在着自始至终的矛盾运动。\n\n矛盾的特殊性是指不同事物的矛盾具有不同的特点。在分析问题时，我们既要看到矛盾的普遍性，也要注意矛盾的特殊性，具体问题具体分析。这是我读《矛盾论》后最深刻的体会。",
]


def main():
    db = SessionLocal()
    try:
        print("🚀 开始生成测试数据...\n")
        now = datetime.now()

        # ════════════════════════════════════════════════════════
        # 1. 新增教师
        # ════════════════════════════════════════════════════════
        print("━ 1. 教师账号 ━")
        teacher_ids = {}
        # 先获取已存在的 teacher
        existing_teacher = db.query(User).filter(User.username == "teacher").first()
        if existing_teacher:
            teacher_ids["teacher"] = existing_teacher.id
            print(f"  ⏭️  教师已存在: 张老师 (id={existing_teacher.id})")
        else:
            print("  ⚠️  默认teacher不存在，请先运行 seed.py")

        for t in TEACHERS:
            existing = db.query(User).filter(User.username == t["username"]).first()
            if existing:
                teacher_ids[t["username"]] = existing.id
                print(f"  ⏭️  教师已存在: {t['name']} (id={existing.id})")
            else:
                user = User(
                    username=t["username"],
                    email=t["email"],
                    password=DEFAULT_PWD,
                    name=t["name"],
                    role=t["role"],
                    status="active",
                    must_change_password=False,
                )
                db.add(user)
                db.commit()
                db.refresh(user)
                teacher_ids[t["username"]] = user.id
                print(f"  ✅ 教师: {t['name']} (id={user.id}, 密码: 123456789)")

        # ════════════════════════════════════════════════════════
        # 2. 新增学生
        # ════════════════════════════════════════════════════════
        print("\n━ 2. 学生账号 ━")
        student_ids = {}
        # 已存在的学生
        for sid in ["2024001", "2024002", "2024003"]:
            existing = db.query(User).filter(User.username == sid).first()
            if existing:
                student_ids[sid] = existing.id
        if student_ids:
            print(f"  ⏭️  已有学生: {len(student_ids)} 人")

        new_count = 0
        for s in STUDENTS:
            existing = db.query(User).filter(User.username == s["username"]).first()
            if existing:
                student_ids[s["username"]] = existing.id
            else:
                user = User(
                    username=s["username"],
                    email=s["email"],
                    password=DEFAULT_PWD,
                    name=s["name"],
                    role="student",
                    status="active",
                    student_id=s["student_id"],
                    must_change_password=True,
                )
                db.add(user)
                db.commit()
                db.refresh(user)
                student_ids[s["username"]] = user.id
                new_count += 1
        print(f"  ✅ 新增学生: {new_count} 人，学生总数: {len(student_ids)} 人")

        # ════════════════════════════════════════════════════════
        # 3. 创建班级 + 分配学生
        # ════════════════════════════════════════════════════════
        print("\n━ 3. 班级 & 学生分配 ━")
        all_student_usernames = list(student_ids.keys())
        random.seed(42)  # 可重复的随机分配

        class_records = []  # [(class_obj, teacher_username)]
        class_code_counter = 1001

        # 先创建所有班级
        for teacher_uname, class_list in CLASSES_BY_TEACHER.items():
            tid = teacher_ids.get(teacher_uname)
            if not tid:
                print(f"  ⚠️  跳过 {teacher_uname}: 教师不存在")
                continue

            for cls_info in class_list:
                code = f"CLS{class_code_counter}"
                class_code_counter += 1

                existing = db.query(Class).filter(Class.code == code).first()
                if existing:
                    cls_obj = existing
                    print(f"  ⏭️  班级已存在: {cls_info['name']} ({code})")
                else:
                    cls_obj = Class(
                        name=cls_info["name"],
                        code=code,
                        teacher_id=tid,
                        description=cls_info["description"],
                        status="active",
                        max_students=50,
                        student_count=0,
                    )
                    db.add(cls_obj)
                    db.commit()
                    db.refresh(cls_obj)
                    print(f"  ✅ 班级: {cls_info['name']} ({code}) — 教师: {teacher_uname}")

                class_records.append((cls_obj, teacher_uname))

        # 分配学生：每个学生随机加入 2~4 个班级
        print("\n  分配学生到班级...")
        for suname in all_student_usernames:
            sid = student_ids[suname]
            # 每个学生随机选择 2~4 个班级加入
            num_classes = random.randint(2, 4)
            chosen = random.sample(class_records, min(num_classes, len(class_records)))
            for cls_obj, _ in chosen:
                existing_cs = db.query(ClassStudent).filter(
                    ClassStudent.class_id == cls_obj.id,
                    ClassStudent.student_id == sid,
                ).first()
                if not existing_cs:
                    cs = ClassStudent(
                        class_id=cls_obj.id,
                        student_id=sid,
                        join_method="code",
                        status="active",
                        joined_at=now - timedelta(days=random.randint(30, 180)),
                        total_submissions=0,
                    )
                    db.add(cs)
        db.commit()

        # 更新每个班级的学生人数
        for cls_obj, teacher_uname in class_records:
            actual_count = db.query(ClassStudent).filter(
                ClassStudent.class_id == cls_obj.id,
                ClassStudent.status == "active",
            ).count()
            cls_obj.student_count = actual_count
            print(f"  📋 {cls_obj.name}: {actual_count} 名学生")
        db.commit()

        # ════════════════════════════════════════════════════════
        # 4. 创建作业 (按教师维度，合并同一教师的所有班级)
        # ════════════════════════════════════════════════════════
        print("\n━ 4. 作业 ━")
        total_assignments = 0

        # 按教师分组班级，为每个教师创建作业
        teacher_classes = {}  # {teacher_uname: [cls_obj, ...]}
        for cls_obj, teacher_uname in class_records:
            teacher_classes.setdefault(teacher_uname, []).append(cls_obj)

        for teacher_uname, cls_list in teacher_classes.items():
            tid = teacher_ids[teacher_uname]
            teacher = db.query(User).filter(User.id == tid).first()
            if not teacher:
                continue

            # 取第一个班级名来判断学科（同一教师通常教同一学科）
            cls_name = cls_list[0].name
            if any(kw in cls_name for kw in ["计算机", "Python", "数据", "程序"]):
                category = "computer"
            elif any(kw in cls_name for kw in ["数学", "代数"]):
                category = "math"
            elif any(kw in cls_name for kw in ["英语", "商务"]):
                category = "english"
            elif any(kw in cls_name for kw in ["物理"]):
                category = "physics"
            elif any(kw in cls_name for kw in ["马克思", "思政"]):
                category = "politics"
            else:
                category = "computer"

            titles = ASSIGNMENT_TITLES.get(category, ASSIGNMENT_TITLES["computer"])
            num_assignments = min(len(titles), random.randint(4, 5))
            selected_titles = random.sample(titles, num_assignments)

            # 构建该教师所有班级的引用
            classes_ref = [{"id": c.id, "name": c.name} for c in cls_list]

            for t in selected_titles:
                start_offset = random.randint(10, 60)
                start_date = now - timedelta(days=start_offset)
                end_date = start_date + timedelta(days=random.randint(14, 30))

                if end_date > now:
                    status = random.choices(
                        ["published", "in_progress", "draft"],
                        weights=[50, 30, 20],
                    )[0]
                else:
                    status = random.choices(
                        ["closed", "published"],
                        weights=[70, 30],
                    )[0]

                # 检查唯一性：同一教师 + 同一标题 = 已存在
                existing = db.query(Assignment).filter(
                    Assignment.title == t["title"],
                    Assignment.teacher_id == tid,
                ).first()
                if existing:
                    # 更新其 classes 字段（合并班级）
                    existing_classes = existing.classes or []
                    existing_ids = {c["id"] for c in existing_classes}
                    for c in classes_ref:
                        if c["id"] not in existing_ids:
                            existing_classes.append(c)
                    existing.classes = existing_classes
                    db.commit()
                    print(f"  🔄 合并班级: {t['title']} → {len(existing_classes)} 个班")
                    total_assignments += 1
                    continue

                assignment = Assignment(
                    title=t["title"],
                    description=t["description"],
                    teacher_id=tid,
                    teacher_name=teacher.name,
                    classes=classes_ref,
                    start_date=start_date,
                    end_date=end_date,
                    status=status,
                    allow_attachments=(category in ["computer", "english", "physics"]),
                    attachments=[],
                )
                db.add(assignment)
                db.commit()
                db.refresh(assignment)
                total_assignments += 1
                class_names = ", ".join(c["name"] for c in classes_ref)
                print(f"  ✅ 作业: {t['title']} [{status}] → {class_names} ({start_date.date()} ~ {end_date.date()})")

        print(f"  📊 共 {total_assignments} 个作业")

        # ════════════════════════════════════════════════════════
        # 5. 创建提交记录
        # ════════════════════════════════════════════════════════
        print("\n━ 5. 提交记录 ━")
        total_submissions = 0

        all_assignments = db.query(Assignment).all()
        random.seed(123)

        for assignment in all_assignments:
            # 获取该作业对应的班级
            if not assignment.classes:
                continue
            for cls_ref in assignment.classes:
                cls_id = cls_ref.get("id")
                if not cls_id:
                    continue

                # 获取该班级的学生
                class_students = db.query(ClassStudent).filter(
                    ClassStudent.class_id == cls_id,
                    ClassStudent.status == "active",
                ).all()

                for cs in class_students:
                    # 70% 的学生提交了作业
                    if random.random() > 0.70:
                        continue

                    student = db.query(User).filter(User.id == cs.student_id).first()
                    if not student:
                        continue

                    # 提交状态分布
                    if assignment.status in ["draft"]:
                        sub_status = "draft"
                    else:
                        sub_status = random.choices(
                            ["submitted", "reviewed", "reviewed", "draft"],
                            weights=[30, 50, 10, 10],
                        )[0]

                    # 已存在检查
                    existing_sub = db.query(Submission).filter(
                        Submission.assignment_id == assignment.id,
                        Submission.student_id == cs.student_id,
                    ).first()
                    if existing_sub:
                        continue

                    submitted_at = assignment.start_date + timedelta(
                        days=random.randint(1, max(2, (assignment.end_date - assignment.start_date).days))
                    )

                    content = random.choice(SUBMISSION_CONTENTS)
                    word_count = len(content)

                    sub = Submission(
                        assignment_id=assignment.id,
                        student_id=cs.student_id,
                        class_id=cls_id,
                        content=content,
                        word_count=word_count,
                        status=sub_status,
                        submitted_at=submitted_at if sub_status != "draft" else None,
                        is_draft=(sub_status == "draft"),
                        attachments=[],
                    )

                    # AI 评分 (60% 概率)
                    if sub_status in ["submitted", "reviewed"] and random.random() > 0.40:
                        ai_review = random.choice(AI_REVIEW_TEMPLATES)
                        sub.ai_score = ai_review["score"]
                        sub.ai_review_content = ai_review["content"]

                    # 教师评分 (reviewed 状态)
                    if sub_status == "reviewed":
                        teacher_review = random.choice(TEACHER_REVIEW_TEMPLATES)
                        sub.teacher_score = teacher_review["score"]
                        sub.teacher_review_content = teacher_review["content"]
                        sub.teacher_reviewed_at = submitted_at + timedelta(days=random.randint(1, 5))

                    db.add(sub)
                    total_submissions += 1

        db.commit()
        print(f"  ✅ 共创建 {total_submissions} 条提交记录")

        # 更新 class_students 的提交统计
        print("\n━ 6. 更新提交统计 ━")
        all_cs = db.query(ClassStudent).all()
        updated = 0
        for cs in all_cs:
            sub_count = db.query(Submission).filter(
                Submission.student_id == cs.student_id,
                Submission.class_id == cs.class_id,
            ).count()
            if sub_count > 0:
                last_sub = db.query(Submission).filter(
                    Submission.student_id == cs.student_id,
                    Submission.class_id == cs.class_id,
                ).order_by(Submission.submitted_at.desc()).first()
                cs.total_submissions = sub_count
                cs.last_submission_time = last_sub.submitted_at if last_sub else None
                updated += 1
        db.commit()
        print(f"  ✅ 更新了 {updated} 条班级-学生关联记录")

        # ════════════════════════════════════════════════════════
        # 7. AI 批改规则
        # ════════════════════════════════════════════════════════
        print("\n━ 7. AI 批改规则 ━")
        # 取第一个教师作为规则创建者
        first_teacher = db.query(User).filter(User.role == "teacher").first()
        creator = {"id": first_teacher.id, "name": first_teacher.name} if first_teacher else None

        for rule in AI_RULES:
            existing = db.query(AiRule).filter(AiRule.name == rule["name"]).first()
            if existing:
                print(f"  ⏭️  AI规则已存在: {rule['name']}")
            else:
                db.add(AiRule(
                    name=rule["name"],
                    description=rule["description"],
                    model_type=rule["model_type"],
                    prompt=rule["prompt"],
                    status="active",
                    visibility=rule["visibility"],
                    tags=rule["tags"],
                    max_score=rule["max_score"],
                    created_by=creator,
                ))
                db.commit()
                print(f"  ✅ AI规则: {rule['name']}")

        # ════════════════════════════════════════════════════════
        # 8. AI 助手聊天记录 (可选)
        # ════════════════════════════════════════════════════════
        print("\n━ 8. AI 助手聊天记录 ━")
        chat_teacher = db.query(User).filter(User.username == "teacher").first()
        if chat_teacher:
            existing_chat = db.query(AgentChatMessage).filter(
                AgentChatMessage.teacher_id == chat_teacher.id
            ).count()
            if existing_chat > 0:
                print(f"  ⏭️  聊天记录已存在 ({existing_chat} 条)")
            else:
                sessions = [
                    {
                        "session_id": "demo-session-1",
                        "messages": [
                            ("user", "如何提高学生的课堂参与度？"),
                            ("assistant", "提高学生课堂参与度可以从以下几个方面入手：\n\n1. **互动式教学**：多提问，让学生参与到问题讨论中来\n2. **小组合作**：将学生分成小组，布置合作任务\n3. **运用技术**：使用在线投票、实时答题等工具增加互动\n4. **联系实际**：将知识点与现实生活中的案例结合\n5. **及时反馈**：对学生的回答给予积极的回应和鼓励\n\n您需要我针对某个方面详细展开吗？"),
                            ("user", "帮我设计一个Python课程的作业，要考察面向对象编程的知识点"),
                            ("assistant", "好的，我为您设计一个Python面向对象编程的作业：\n\n**【学生成绩管理系统】**\n\n**要求：**\n1. 创建 `Student` 类，包含属性：姓名、学号、各科成绩\n2. 创建 `Course` 类，包含属性：课程名、学分、成绩列表\n3. 创建 `GradeManager` 类，实现以下功能：\n   - 添加学生\n   - 录入成绩\n   - 计算GPA\n   - 成绩排名\n   - 生成成绩单\n\n**提交要求：**\n- 提交 `.py` 源文件\n- 包含充分的注释\n- 附带简单的测试代码\n\n这份作业难度适中，适合已经学过面向对象基础的学生。需要我调整难度或添加其他要求吗？"),
                        ],
                    },
                    {
                        "session_id": "demo-session-2",
                        "messages": [
                            ("user", "我们班的作业提交率有点低，有什么好办法？"),
                            ("assistant", "关于提高作业提交率，这里有几个策略供您参考：\n\n**1. 调整截止时间**\n- 避免在周末或节假日设置截止日期\n- 将截止时间设在晚上10点而非凌晨\n\n**2. 设置提醒机制**\n- 在截止前24小时发送提醒\n- 利用班级群公告\n\n**3. 激励机制**\n- 按时提交给予少量加分\n- 评选优秀作业展示\n\n**4. 降低提交门槛**\n- 允许草稿多次提交\n- 对格式要求适当放宽\n\n**5. 沟通原因**\n- 了解学生未提交的原因\n- 可能存在作业量过大或难度过高的问题\n\n您班上的作业提交率大概是多少？我可以帮您更具体地分析。"),
                        ],
                    },
                ]
                msg_count = 0
                for sess in sessions:
                    for role, content in sess["messages"]:
                        db.add(AgentChatMessage(
                            teacher_id=chat_teacher.id,
                            session_id=sess["session_id"],
                            role=role,
                            content=content,
                        ))
                        msg_count += 1
                db.commit()
                print(f"  ✅ 创建了 {msg_count} 条聊天记录 (2 个会话)")

        # ════════════════════════════════════════════════════════
        # 9. 汇总
        # ════════════════════════════════════════════════════════
        print("\n" + "=" * 50)
        print("🎉 测试数据生成完成！")
        print("=" * 50)
        print(f"📊 数据统计:")
        print(f"  教师: {db.query(User).filter(User.role == 'teacher').count()} 人")
        print(f"  学生: {db.query(User).filter(User.role == 'student').count()} 人")
        print(f"  班级: {db.query(Class).count()} 个")
        print(f"  作业: {db.query(Assignment).count()} 个")
        print(f"  提交: {db.query(Submission).count()} 条")
        print(f"  AI规则: {db.query(AiRule).count()} 条")
        print(f"  聊天记录: {db.query(AgentChatMessage).count()} 条")
        print("=" * 50)
        print("\n📋 新增账号 (密码均为 123456789):")
        for t in TEACHERS:
            print(f"  教师: {t['username']} — {t['name']}")
        print(f"  学生: 2024040 ~ 2024069 (30人)")
        print("=" * 50)

    finally:
        db.close()


if __name__ == "__main__":
    main()
