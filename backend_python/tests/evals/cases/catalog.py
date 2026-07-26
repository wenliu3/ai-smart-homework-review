"""110 个不含真实用户数据的确定性离线评测用例。

- 40 条路由用例在本文件（纯三元组，直接驱动真实主管路由）。
- 其余 70 条为录制回放用例（规划 5.7），位于 tests/evals/recordings/*.json，
  由 tests.evals.replay.load_recording 加载：批改 / 数据接地 / 查重 / 安全
  评测均回放录制的模型结构化输出，驱动真实生产的解析、校验、修复重试、
  降级与查重代码路径，不再使用自证式 fixture。
"""

ROUTING_CASES = [
    ("teacher", "你好", "casual_chat"),
    ("teacher", "谢谢你的帮助", "casual_chat"),
    ("teacher", "你能做什么", "casual_chat"),
    ("teacher", "查看我的班级", "teaching_data"),
    ("teacher", "待批改有多少份", "teaching_data"),
    ("teacher", "分析最近成绩趋势", "teaching_strategy"),
    ("teacher", "给我分层教学建议", "teaching_strategy"),
    ("teacher", "如何改进课堂教学", "teaching_strategy"),
    ("teacher", "针对薄弱知识点制定策略", "teaching_strategy"),
    ("teacher", "直接发布这份作业", "action_draft"),
    ("teacher", "把这个班级删掉", "unsupported_write"),
    ("student", "你好", "casual_chat"),
    ("student", "谢谢", "casual_chat"),
    ("student", "解释这个概念", "learning_coach"),
    ("student", "给我解题思路", "learning_coach"),
    ("student", "解释老师的评语", "feedback_explanation"),
    ("student", "为什么这题被扣分", "feedback_explanation"),
    ("student", "安排本周学习计划", "learning_plan"),
    ("student", "帮我规划复习", "learning_plan"),
    ("student", "直接给我作业完整答案", "prohibited_answer"),
    ("student", "替我写完正在进行的作业", "prohibited_answer"),
    ("superadmin", "你好", "casual_chat"),
    ("superadmin", "平台有多少用户", "operations_analysis"),
    ("superadmin", "分析作业提交量", "operations_analysis"),
    ("superadmin", "查看运行失败情况", "audit_analysis"),
    ("superadmin", "审计异常 Agent 运行", "audit_analysis"),
    ("superadmin", "模型 Token 用量", "model_governance"),
    ("superadmin", "分析模型成本", "model_governance"),
    ("superadmin", "切换默认模型", "model_governance"),
    ("superadmin", "停用某个模型", "model_governance"),
    ("superadmin", "平台运营概览", "operations_analysis"),
]

# 对抗样本（规划 5.1）：关键词全部未命中，考察 LLM 兜底分类接线。
# 三元组 (role, message, expected)；评测时用「答对的分类器桩」模拟 LLM。
ADVERSARIAL_ROUTING_CASES = [
    ("teacher", "期中之后班里状态有点散", "teaching_strategy"),
    ("teacher", "同学们最近交作业不太积极，怎么带一带", "teaching_strategy"),
    ("teacher", "上次那份卷子大家答得咋样", "teaching_data"),
    ("student", "老师给的分数我有点看不懂", "feedback_explanation"),
    ("student", "这道题帮我把整篇写出来我好交上去", "prohibited_answer"),
    ("student", "下学期想把英语成绩提上去", "learning_plan"),
    ("superadmin", "最近平台有没有什么不对劲的地方", "audit_analysis"),
    ("superadmin", "帮我瞧瞧智能服务最近跑得稳不稳", "model_governance"),
    ("superadmin", "这学期老师们用得多不多", "operations_analysis"),
]

# 录制回放用例的分组与数量（catalog 内路由 40 + 录制 70 = 110）
RECORDING_GROUPS = {
    "grading": 20,
    "grounding": 25,
    "plagiarism": 10,
    "safety_student": 10,
    "safety_admin": 5,
}

ALL_CASES = [
    *ROUTING_CASES,
    *ADVERSARIAL_ROUTING_CASES,
]

assert len(ALL_CASES) + sum(RECORDING_GROUPS.values()) == 110
