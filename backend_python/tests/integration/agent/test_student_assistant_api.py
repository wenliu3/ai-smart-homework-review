def test_student_can_create_role_isolated_assistant_session(
    client, student, teacher, auth_header,
):
    created = client.post(
        "/api/assistant/sessions",
        headers=auth_header(student),
        json={"title": "我的学习助手"},
    )

    assert created.status_code == 200
    session_id = created.json()["data"]["sessionId"]
    own = client.get(
        f"/api/assistant/sessions/{session_id}/messages",
        headers=auth_header(student),
    )
    cross_role = client.get(
        f"/api/assistant/sessions/{session_id}/messages",
        headers=auth_header(teacher),
    )

    assert own.status_code == 200
    assert own.json()["data"]["messages"] == []
    assert cross_role.status_code == 200
    assert cross_role.json()["data"]["messages"] == []


def test_student_orchestration_persists_student_graph_steps(
    assistant_db, student,
):
    from app.agent.contracts import ReviewResult
    from app.agent.service import orchestrate_student_run
    from app.crud.agent_session import create_session

    class Agents:
        def learning_coach(self, state):
            return {"candidate_answer": "先说说你的思路。", "evidence_refs": []}

        def feedback_explainer(self, state):
            return {"candidate_answer": "反馈解释", "evidence_refs": ["e"]}

        def learning_planner(self, state):
            return {"candidate_answer": "学习计划", "evidence_refs": ["e"]}

        def final_reviewer(self, state):
            return {"review": ReviewResult(approved=True)}

    session = create_session(
        assistant_db,
        user_id=student.id,
        actor_role="student",
        title="学生会话",
    )
    result = orchestrate_student_run(
        student_id=student.id,
        message="请给我完整答案",
        session_id=session.id,
        request_id="req-student-1",
        subagents=Agents(),
        assistant_db=assistant_db,
    )

    assert result.status == "completed"
    assert "不能代写" in result.final_answer
    run = result.run_id
    from app.models import AgentRun
    saved = assistant_db.query(AgentRun).filter(AgentRun.id == run).one()
    assert saved.graph_version == "student-v1"
    assert [step.node_name for step in saved.steps] == [
        "student_supervisor",
        "prohibited_answer",
        "student_final_reviewer",
        "finalize",
    ]


def test_stream_endpoint_dispatches_by_student_role(
    client, student, auth_header, monkeypatch,
):
    created = client.post(
        "/api/assistant/sessions",
        headers=auth_header(student),
        json={"title": "学习助手"},
    )
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
        "app.routers.assistant.stream_student_events",
        fake_stream,
    )
    response = client.post(
        "/api/assistant/runs/stream",
        headers=auth_header(student),
        json={"session_id": session_id, "message": "你好"},
    )

    assert response.status_code == 200
    assert calls[0]["student_id"] == student.id
