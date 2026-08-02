"""测试数据工厂：批改结果 / 用量构造助手，供多个测试模块共享。

自 test_grading_jobs / test_run_usage_persistence 的私有助手迁移而来，
避免跨测试模块导入兄弟测试模块的私有函数。
"""
from app.agent.contracts import CriterionGrade, GradingDraft, GradingOutcome


def _outcome(needs_human_review: bool = False) -> GradingOutcome:
    """构造一份确定性批改结果：主/复核同分 88、无分差，按需请求人工复核。"""
    primary = GradingDraft(
        rubric_version="rubric-v3",
        items=[
            CriterionGrade(
                criterion_id="quality",
                title="质量",
                score=88,
                max_score=100,
                feedback="完成良好",
                evidence_refs=["submission:text:1"],
            ),
        ],
        summary="总体完成良好",
    )
    review = primary.model_copy(deep=True)
    return GradingOutcome(
        primary=primary,
        review=review,
        score_difference=0,
        needs_human_review=needs_human_review,
    )


def _usage(prompt: int, completion: int) -> dict:
    """构造 prompt/completion/total 三键用量字典。"""
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": prompt + completion,
    }
