from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock

from app.routers import submissions


def test_submit_stays_successful_when_grading_dispatch_fails(monkeypatch):
    persisted = SimpleNamespace(
        id=21,
        assignment_id=9,
        student_id=7,
        status="submitted",
        submitted_at=datetime(2026, 7, 25, 10, 0, 0),
        updated_at=datetime(2026, 7, 25, 10, 0, 0),
        is_draft=False,
        submission_count=1,
    )
    monkeypatch.setattr(
        submissions.submission_crud,
        "submit",
        lambda *_: persisted,
    )
    monkeypatch.setattr(
        submissions,
        "enqueue_grading_job",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("redis unavailable"),
        ),
    )
    assistant_db = Mock()
    body = SimpleNamespace(isDraft=False, model_dump=lambda: {})
    user = SimpleNamespace(id=7, role="student")

    response = submissions.submit(body, user, Mock(), assistant_db)

    assert response["code"] == 200
    assert response["data"]["status"] == "submitted"
    assert response["data"]["gradingRunId"] is None
    assert response["data"]["gradingSchedulingStatus"] == "failed"
    assistant_db.rollback.assert_called_once_with()
