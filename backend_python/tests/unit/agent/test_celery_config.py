from app.config import settings
from app.tasks.celery_app import celery_app
from app.tasks.grading import rubric_from_ai_rule


def test_celery_uses_redis_and_durable_worker_settings():
    assert celery_app.conf.broker_url == settings.REDIS_URL
    assert celery_app.conf.result_backend == settings.REDIS_URL
    assert celery_app.conf.task_acks_late is True
    assert celery_app.conf.task_reject_on_worker_lost is True
    assert celery_app.conf.task_track_started is True
    assert celery_app.conf.task_serializer == "json"


def test_ai_rule_is_normalized_to_versioned_rubric():
    rubric = rubric_from_ai_rule({
        "version": "rule-v4",
        "maxScore": 100,
        "criteria": [
            {"id": "correctness", "title": "正确性", "maxScore": 70},
            {"id": "clarity", "title": "表达", "maxScore": 30},
        ],
    })

    assert rubric.version == "rule-v4"
    assert rubric.total_score == 100
    assert [item.criterion_id for item in rubric.criteria] == [
        "correctness",
        "clarity",
    ]


def test_legacy_ai_rule_gets_single_dimension_rubric():
    rubric = rubric_from_ai_rule({
        "prompt": "按要求批改",
        "maxScore": 80,
    })

    assert rubric.version.startswith("legacy-")
    assert rubric.total_score == 80
    assert rubric.criteria[0].criterion_id == "overall"
