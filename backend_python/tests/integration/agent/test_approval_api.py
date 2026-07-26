def test_teacher_can_create_approve_and_idempotently_replay_ai_rule(
    client, teacher, auth_header,
):
    headers = auth_header(teacher)
    draft = client.post(
        "/api/assistant/approvals",
        headers=headers,
        json={
            "actionType": "create_ai_rule",
            "targetType": "ai_rule",
            "parameters": {
                "name": "结构化评分规则",
                "description": "",
                "modelType": "deepseek",
                "prompt": "按评分量表逐项评价",
                "status": "inactive",
                "visibility": "private",
                "maxScore": 100,
            },
            "summary": "创建一条 AI 评分规则草案",
            "riskLevel": "medium",
        },
    )
    assert draft.status_code == 200
    approval = draft.json()["data"]
    assert approval["status"] == "pending"

    approved = client.post(
        f"/api/assistant/approvals/{approval['approvalId']}/approve",
        headers=headers,
        json={"payload": approval["parameters"]},
    )
    assert approved.status_code == 200
    result = approved.json()["data"]["result"]
    assert result["success"] is True

    replay = client.post(
        f"/api/assistant/approvals/{approval['approvalId']}/approve",
        headers=headers,
        json={"payload": approval["parameters"]},
    )
    assert replay.status_code == 200
    assert replay.json()["data"]["result"] == result


def test_approval_api_rejects_payload_tampering(client, teacher, auth_header):
    headers = auth_header(teacher)
    response = client.post(
        "/api/assistant/approvals",
        headers=headers,
        json={
            "actionType": "create_ai_rule",
            "targetType": "ai_rule",
            "parameters": {
                "name": "原始规则",
                "modelType": "deepseek",
                "prompt": "原始提示",
            },
            "summary": "创建规则",
            "riskLevel": "medium",
        },
    )
    approval_id = response.json()["data"]["approvalId"]

    tampered = client.post(
        f"/api/assistant/approvals/{approval_id}/approve",
        headers=headers,
        json={"payload": {
            "name": "篡改规则",
            "modelType": "deepseek",
            "prompt": "篡改提示",
        }},
    )

    assert tampered.status_code == 400
    assert "载荷" in tampered.json()["message"]


def test_approval_api_rejects_ai_rule_orm_field_injection(
    client, teacher, auth_header,
):
    response = client.post(
        "/api/assistant/approvals",
        headers=auth_header(teacher),
        json={
            "actionType": "create_ai_rule",
            "targetType": "ai_rule",
            "parameters": {
                "name": "unsafe rule",
                "modelType": "deepseek",
                "prompt": "grade",
                "createdAt": "2000-01-01T00:00:00",
            },
            "summary": "field injection",
            "riskLevel": "medium",
        },
    )

    assert response.status_code == 400
    assert "字段" in response.json()["message"]
