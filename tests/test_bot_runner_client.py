from unittest.mock import Mock

import pytest
import requests
from pydantic import ValidationError

from api.core.configs._challenge import BotRunnerConfig
from api.endpoints.challenge import _bot_runner


class DummyResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}", response=self)


def make_session(*responses):
    session = Mock()
    session.post.side_effect = list(responses)
    session.get.side_effect = list(responses)
    return session


def test_bot_runner_config_defaults_are_safe():
    config = BotRunnerConfig(
        url="http://bot-runner:8000",
        api_key="super_secret_bot_runner_key",
        public_base_url="http://challenge:10001",
        framework_presets={"playwright": "playwright-local"},
    )

    assert config.device_type == "linux"
    assert config.bot == "aad-detect"
    assert config.poll_timeout_sec >= config.poll_interval_sec
    assert config.framework_presets["playwright"] == "playwright-local"


def test_bot_runner_config_rejects_too_short_api_key():
    with pytest.raises(ValidationError):
        BotRunnerConfig(
            url="http://bot-runner:8000",
            api_key="short",
            public_base_url="http://challenge:10001",
            framework_presets={"playwright": "playwright-local"},
        )


def test_build_web_url_uses_public_base_url_without_bind_host():
    assert (
        _bot_runner.build_web_url("http://challenge:10001/")
        == "http://challenge:10001/_web"
    )


def test_trigger_run_posts_authenticated_request_and_returns_batch_id():
    session = make_session(DummyResponse(202, {"batch_id": "batch-123"}))

    batch_id = _bot_runner.trigger_run(
        base_url="http://runner:8000/",
        api_key="secret-token",
        bot="aad-detect",
        driver_preset="playwright-local",
        device_type="linux",
        web_url="http://challenge:10001/_web",
        framework_name="playwright",
        request_timeout_sec=3,
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
    assert kwargs["json"]["metadata"]["framework"] == "playwright"


def test_trigger_run_retries_429_with_backoff(monkeypatch):
    session = make_session(
        DummyResponse(429, {"detail": "busy"}),
        DummyResponse(429, {"detail": "busy"}),
        DummyResponse(202, {"batch_id": "batch-ok"}),
    )
    sleeps = []
    monkeypatch.setattr(_bot_runner.time, "sleep", sleeps.append)

    batch_id = _bot_runner.trigger_run(
        base_url="http://runner:8000",
        api_key="secret-token",
        bot="aad-detect",
        driver_preset="playwright-local",
        device_type="linux",
        web_url="http://challenge:10001/_web",
        framework_name="playwright",
        request_timeout_sec=3,
        busy_retry_count=3,
        busy_backoff_initial_sec=0.5,
        busy_backoff_max_sec=2.0,
        session=session,
    )

    assert batch_id == "batch-ok"
    assert session.post.call_count == 3
    assert sleeps == [0.5, 1.0]


def test_trigger_run_does_not_retry_device_mismatch_409():
    session = make_session(DummyResponse(409, {"detail": "wrong device"}))

    with pytest.raises(requests.HTTPError):
        _bot_runner.trigger_run(
            base_url="http://runner:8000",
            api_key="secret-token",
            bot="aad-detect",
            driver_preset="playwright-local",
            device_type="mac",
            web_url="http://challenge:10001/_web",
            framework_name="playwright",
            request_timeout_sec=3,
            busy_retry_count=3,
            session=session,
        )

    assert session.post.call_count == 1


def test_wait_for_run_returns_terminal_status(monkeypatch):
    session = Mock()
    session.get.side_effect = [
        DummyResponse(200, {"status": "running"}),
        DummyResponse(200, {"status": "passed"}),
    ]
    timeline = iter([0.0, 0.1, 0.2])
    monkeypatch.setattr(_bot_runner.time, "monotonic", lambda: next(timeline))
    monkeypatch.setattr(_bot_runner.time, "sleep", lambda _: None)

    status = _bot_runner.wait_for_run(
        base_url="http://runner:8000",
        api_key="secret-token",
        batch_id="batch-123",
        poll_timeout_sec=10,
        poll_interval_sec=1,
        request_timeout_sec=3,
        session=session,
    )

    assert status == "passed"
    assert session.get.call_count == 2
    assert session.get.call_args.kwargs["headers"] == {"Authorization": "Bearer secret-token"}


def test_wait_for_run_returns_timeout(monkeypatch):
    session = Mock()
    session.get.return_value = DummyResponse(200, {"status": "running"})
    timeline = iter([0.0, 2.0, 4.0])
    monkeypatch.setattr(_bot_runner.time, "monotonic", lambda: next(timeline))
    monkeypatch.setattr(_bot_runner.time, "sleep", lambda _: None)

    status = _bot_runner.wait_for_run(
        base_url="http://runner:8000",
        api_key="secret-token",
        batch_id="batch-123",
        poll_timeout_sec=1,
        poll_interval_sec=1,
        request_timeout_sec=3,
        session=session,
    )

    assert status == "timeout"


def test_trigger_run_does_not_log_api_key(caplog):
    session = make_session(DummyResponse(202, {"batch_id": "batch-123"}))
    secret = "very-secret-token"

    _bot_runner.trigger_run(
        base_url="http://runner:8000/",
        api_key=secret,
        bot="aad-detect",
        driver_preset="playwright-local",
        device_type="linux",
        web_url="http://challenge:10001/_web",
        framework_name="playwright",
        request_timeout_sec=3,
        session=session,
    )

    assert secret not in caplog.text
