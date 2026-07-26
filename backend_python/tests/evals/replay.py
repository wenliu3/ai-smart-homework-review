"""录制回放评测基座（规划 5.7）。

recordings/*.json 保存脱敏后的录制数据（输入 + 模型结构化输出 + 人工评分）。
评测时用 ReplayAgent 按录制顺序原样回放模型输出，驱动真实的生产
解析 / 校验 / 修复重试 / 降级代码路径——而不是让 fixture 自证其构造。
"""
from __future__ import annotations

import json
from pathlib import Path

RECORDINGS_DIR = Path(__file__).parent / "recordings"
ASSETS_DIR = RECORDINGS_DIR / "assets"

# 录制格式兼容规则：主版本一致即可回放，次版本允许向后新增字段
SUPPORTED_SCHEMA_MAJOR = 1


def load_recording(name: str) -> list[dict]:
    """加载一组录制用例；schema_version 主版本不兼容时显式报错。"""
    path = RECORDINGS_DIR / f"{name}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    version = str(payload.get("schema_version", ""))
    major = version.split(".", 1)[0]
    if not major.isdigit() or int(major) != SUPPORTED_SCHEMA_MAJOR:
        raise ValueError(
            f"不兼容的录制格式版本：{name} schema_version={version!r}"
        )
    return payload["cases"]


class ReplayAgent:
    """按录制顺序回放结构化输出的 Agent 桩，兼容 ``agent.invoke`` 协议。

    - ``structured_responses`` 中的 ``None`` 表示该次调用没有结构化输出
      （回放「模型未按契约返回」的录制场景）。
    - ``prompts`` 记录每次 invoke 的入参，供评测断言真实管线的重试回喂等行为。
    - 回放次数超过录制数量视为管线行为回归，直接失败。
    """

    def __init__(self, structured_responses: list, messages: list | None = None):
        self._responses = list(structured_responses)
        self._messages = list(messages or [])
        self.prompts: list = []

    def invoke(self, payload: dict) -> dict:
        self.prompts.append(payload)
        if not self._responses:
            raise AssertionError("录制的模型输出已耗尽，回放次数超出录制预期")
        structured = self._responses.pop(0)
        result: dict = {"messages": list(self._messages)}
        if structured is not None:
            result["structured_response"] = structured
        return result


class ReplayRegistry:
    """``get_specialist`` 协议的回放注册表：按名称提供 ReplayAgent。"""

    def __init__(self, agents: dict[str, ReplayAgent]):
        self._agents = agents

    def get_specialist(self, name: str, db=None) -> ReplayAgent:
        if name not in self._agents:
            raise AssertionError(f"评测未录制该 specialist 的输出：{name}")
        return self._agents[name]


__all__ = [
    "ASSETS_DIR",
    "RECORDINGS_DIR",
    "ReplayAgent",
    "ReplayRegistry",
    "load_recording",
]
