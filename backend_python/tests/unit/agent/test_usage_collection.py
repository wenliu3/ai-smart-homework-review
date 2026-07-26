"""Token 用量聚合（规划阶段 4.1）。

- collect_invoke_usage 从一次 agent.invoke 结果求和新增 AI 消息的用量。
- merge_usage 键级相加，供批改重试等多次调用累加。
- 键名对齐 contracts.UsageSummary（prompt_tokens/completion_tokens/total_tokens）。
"""
from langchain_core.messages import AIMessage, HumanMessage

from app.agent.subagents.messages import collect_invoke_usage, merge_usage


def _ai(prompt: int, completion: int) -> AIMessage:
    return AIMessage(
        content="回答",
        usage_metadata={
            "input_tokens": prompt,
            "output_tokens": completion,
            "total_tokens": prompt + completion,
        },
    )


def test_collect_invoke_usage_sums_ai_messages_with_usage():
    result = {"messages": [
        HumanMessage(content="问题"),
        AIMessage(content="历史回答，无用量元数据"),
        _ai(120, 30),
        _ai(10, 5),
    ]}

    assert collect_invoke_usage(result) == {
        "prompt_tokens": 130,
        "completion_tokens": 35,
        "total_tokens": 165,
    }


def test_collect_invoke_usage_returns_empty_without_usage():
    assert collect_invoke_usage({"messages": [HumanMessage(content="x")]}) == {}
    assert collect_invoke_usage({}) == {}
    assert collect_invoke_usage(None) == {}


def test_merge_usage_adds_keys():
    merged = merge_usage(
        {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
        {"prompt_tokens": 50, "completion_tokens": 5, "total_tokens": 55},
    )

    assert merged == {
        "prompt_tokens": 150,
        "completion_tokens": 25,
        "total_tokens": 175,
    }


def test_merge_usage_tolerates_empty_sides():
    usage = {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12}

    assert merge_usage({}, usage) == usage
    assert merge_usage(usage, {}) == usage
    assert merge_usage({}, {}) == {}
