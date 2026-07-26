def test_admin_can_create_session_and_stream_uses_admin_runtime(
    client, user_factory, auth_header, monkeypatch,
):
    admin = user_factory("root_admin", "superadmin")
    created = client.post(
        "/api/assistant/sessions",
        headers=auth_header(admin),
        json={"title": "治理助手"},
    )
    assert created.status_code == 200
    session_id = created.json()["data"]["sessionId"]
    calls = []

    def fake_stream(**kwargs):
        from app.agent.service import ChatStreamEvent

        calls.append(kwargs)
        yield ChatStreamEvent(
            event=None,
            data='{"type":"run.completed","data":{}}',
        )
        yield ChatStreamEvent(event="done", data="[DONE]")

    monkeypatch.setattr(
        "app.routers.assistant.stream_admin_events",
        fake_stream,
    )
    response = client.post(
        "/api/assistant/runs/stream",
        headers=auth_header(admin),
        json={"session_id": session_id, "message": "查看运营数据"},
    )

    assert response.status_code == 200
    assert calls[0]["admin_id"] == admin.id
