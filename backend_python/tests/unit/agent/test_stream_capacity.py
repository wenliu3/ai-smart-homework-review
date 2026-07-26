import json

import pytest

from app.agent import service


class _NoCapacity:
    def acquire(self, *, blocking):
        assert blocking is False
        return False


@pytest.mark.parametrize("stream_kind", ["teacher", "role"])
def test_stream_rejects_when_worker_capacity_is_exhausted(
    monkeypatch,
    stream_kind,
):
    monkeypatch.setattr(service, "_STREAM_WORKER_SLOTS", _NoCapacity())
    monkeypatch.setattr(
        service.threading,
        "Thread",
        lambda **_kwargs: pytest.fail("容量耗尽时不应创建后台线程"),
    )

    if stream_kind == "teacher":
        events = list(service.stream_assistant_events(
            teacher_id=1,
            message="hi",
            session_id="session-1",
            request_id="request-1",
        ))
    else:
        events = list(service._stream_role_events(
            actor_id=1,
            request_id="request-1",
            orchestrate=lambda **_kwargs: pytest.fail("不应执行编排"),
            orchestrate_kwargs={},
            container_factory=lambda _db: pytest.fail("不应创建容器"),
        ))

    payload = json.loads(events[0].data)
    assert payload["type"] == "run.failed"
    assert payload["data"]["error_code"] == "AGENT_CAPACITY_EXCEEDED"
    assert events[-1].event == "done"


def test_stream_concurrency_default_leaves_headroom_for_session_pool():
    """并发默认值必须低于会话库连接池容量（pool_size + max_overflow = 15），
    否则满载时多出的 worker 会阻塞等待连接直至池超时。"""
    from app.assistant_database import assistant_engine
    from app.config import Settings

    default = Settings.model_fields["AGENT_STREAM_MAX_CONCURRENCY"].default
    pool_capacity = (
        assistant_engine.pool.size() + assistant_engine.pool._max_overflow
    )

    assert default == 12
    assert default < pool_capacity
