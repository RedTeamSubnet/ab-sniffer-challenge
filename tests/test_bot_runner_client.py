from unittest.mock import Mock
from types import SimpleNamespace

import pytest
import requests

from api.endpoints.challenge import _bot_runner


class _Secret:
    def get_secret_value(self) -> str:
        return "secret-token"


@pytest.fixture(autouse=True)
def bot_runner_config(monkeypatch):
    monkeypatch.setattr(
        _bot_runner,
        "config",
        SimpleNamespace(
            api=SimpleNamespace(prefix=""),
            challenge=SimpleNamespace(
                bot_runner=SimpleNamespace(
                    url="http://runner:8000",
                    api_key=_Secret(),
                    public_base_url="http://challenge:10001",
                    bot="aad-detect",
                    device_type="linux",
                    request_timeout_sec=3,
                    busy_retry_count=3,
                    busy_backoff_initial_sec=0.5,
                    busy_backoff_max_sec=2.0,
                )
            ),
        ),
    )


class DummyResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}", response=self)


def make_session(*responses):
    session = Mock()
    session.post.side_effect = list(responses)
    return session


def test_trigger_run_posts_authenticated_request_and_returns_batch_id():
    session = make_session(DummyResponse(202, {"batch_id": "batch-123"}))

    batch_id = _bot_runner.trigger_run(
        driver_preset="playwright-local",
        framework_name="playwright",
        session=session,
    )

    assert batch_id == "batch-123"
    session.post.assert_called_once()
    url = session.post.call_args.args[0]
    kwargs = session.post.call_args.kwargs
    assert url == "http://runner:8000/api/runs"
    assert kwargs["headers"] == {"Authorization": "Bearer secret-token"}
    assert kwargs["timeout"] == 3
    assert kwargs["json"]["bot"] == "aad-detect"
    assert kwargs["json"]["driver_preset"] == "playwright-local"
    assert kwargs["json"]["url"] == "http://challenge:10001/_web"
    assert kwargs["json"]["device_type"] == "linux"
    assert kwargs["json"]["count"] == 1
    assert kwargs["json"]["headless"] is True
    assert kwargs["json"]["metadata"] == {
        "framework": "playwright",
        "headless": True,
        "count": 1,
    }


def test_trigger_run_retries_429_with_backoff(monkeypatch):
    session = make_session(
        DummyResponse(429, {"detail": "busy"}),
        DummyResponse(429, {"detail": "busy"}),
        DummyResponse(202, {"batch_id": "batch-ok"}),
    )
    sleeps = []
    monkeypatch.setattr(_bot_runner.time, "sleep", sleeps.append)

    batch_id = _bot_runner.trigger_run(
        driver_preset="playwright-local",
        framework_name="playwright",
        session=session,
    )

    assert batch_id == "batch-ok"
    assert session.post.call_count == 3
    assert sleeps == [0.5, 1.0]


def test_trigger_run_does_not_retry_device_mismatch_409():
    session = make_session(DummyResponse(409, {"detail": "wrong device"}))

    with pytest.raises(requests.HTTPError):
        _bot_runner.trigger_run(
            driver_preset="playwright-local",
            framework_name="playwright",
            session=session,
        )

    assert session.post.call_count == 1


def test_trigger_run_does_not_log_api_key(caplog):
    session = make_session(DummyResponse(202, {"batch_id": "batch-123"}))

    _bot_runner.trigger_run(
        driver_preset="playwright-local",
        framework_name="playwright",
        session=session,
    )

    assert "secret-token" not in caplog.text
