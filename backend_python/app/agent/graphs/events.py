"""Graph 执行结构化事件（规格 13.1）。

每个节点在执行关键步骤时追加事件到 state["events"]。
事件按发生顺序排列，图执行完成后从 result["events"] 读取。

事件类型：
- run.started — 图启动
- route.selected — 路由决策完成
- agent.started — specialist 开始执行
- agent.completed — specialist 执行完成
- content.delta — 内容增量（阶段 1 不产生真实增量，占位）
- run.completed — 图正常结束
- run.failed — 图异常结束
"""


def make_event(event_type: str, data: dict | None = None) -> dict:
    """构造单个事件。"""
    return {"type": event_type, "data": data or {}}


def append_events(state: dict, *new_events: dict) -> dict:
    """返回包含追加事件后的 events 字段更新。"""
    events = [*state.get("events", []), *new_events]
    return {"events": events}
