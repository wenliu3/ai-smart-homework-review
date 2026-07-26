import threading

import pytest

from app.agent import service
from app.agent.service import OrchestrationResult


@pytest.mark.parametrize(
    ("stream_name", "orchestrate_name", "actor_key"),
    [
        ("stream_student_events", "orchestrate_student_run", "student_id"),
        ("stream_admin_events", "orchestrate_admin_run", "admin_id"),
    ],
)
def test_role_stream_emits_started_before_orchestration_finishes(
    monkeypatch,
    stream_name,
    orchestrate_name,
    actor_key,
):
    release = threading.Event()
    first_event = []

    def fake_orchestrate(**kwargs):
        kwargs["event_callback"]({
            "type": "run.started",
            "data": {"run_id": "run-live-1"},
        })
        assert release.wait(timeout=2)
        return OrchestrationResult(
            run_id="run-live-1",
            final_answer="ok",
            events=[],
        )

    monkeypatch.setattr(service, orchestrate_name, fake_orchestrate)
    stream = getattr(service, stream_name)(
        **{
            actor_key: 7,
            "message": "hello",
            "session_id": "session-live-1",
            "request_id": "request-live-1",
        },
    )

    reader = threading.Thread(
        target=lambda: first_event.append(next(stream)),
        daemon=True,
    )
    reader.start()
    reader.join(timeout=0.5)

    try:
        assert not reader.is_alive(), "run.started must be yielded before graph completion"
        assert '"type": "run.started"' in first_event[0].data
        assert '"run_id": "run-live-1"' in first_event[0].data
    finally:
        release.set()
        reader.join(timeout=2)
        stream.close()
