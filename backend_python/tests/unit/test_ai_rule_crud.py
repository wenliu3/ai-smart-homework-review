"""AI 规则多维度评分标准（criteria）CRUD 往返测试。

覆盖 schema（AiRuleCreate/Update）→ crud（create/update/copy）→ to_dict
整条链路上的 criteria 透传，防止 Pydantic 剥离未知字段导致 criteria 丢列。
"""
from app.crud import ai_rule as ai_rule_crud


def _criteria():
    return [
        {
            "id": "criterion-content",
            "title": "内容完整性",
            "maxScore": 60,
            "instructions": "要点齐全、论证充分",
        },
        {
            "id": "criterion-expression",
            "title": "表达规范",
            "maxScore": 40,
            "instructions": "表达通顺",
        },
    ]


def test_create_rule_round_trips_criteria(db):
    result = ai_rule_crud.create(db, {
        "name": "多维度规则",
        "modelType": "zhipu",
        "prompt": "按维度评分",
        "criteria": _criteria(),
    })

    fetched = ai_rule_crud.get_by_id(db, int(result["id"]))
    assert fetched["criteria"] == _criteria()


def test_update_rule_replaces_criteria(db):
    result = ai_rule_crud.create(db, {
        "name": "多维度规则",
        "modelType": "zhipu",
        "prompt": "按维度评分",
        "criteria": _criteria(),
    })
    rule_id = int(result["id"])

    new_criteria = [
        {"id": "criterion-a", "title": "维度A", "maxScore": 100, "instructions": ""},
    ]
    ai_rule_crud.update(db, rule_id, {"criteria": new_criteria}, actor_role="superadmin")

    fetched = ai_rule_crud.get_by_id(db, rule_id)
    assert fetched["criteria"] == new_criteria


def test_copy_rule_carries_criteria(db):
    result = ai_rule_crud.create(db, {
        "name": "多维度规则",
        "modelType": "zhipu",
        "prompt": "按维度评分",
        "criteria": _criteria(),
    })
    rule_id = int(result["id"])

    copied = ai_rule_crud.copy(db, rule_id, "多维度规则副本")
    fetched = ai_rule_crud.get_by_id(db, int(copied["id"]))

    assert fetched["name"] == "多维度规则副本"
    assert fetched["criteria"] == _criteria()
    assert fetched["status"] == "inactive"
