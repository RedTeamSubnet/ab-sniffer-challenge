from types import SimpleNamespace

from api.endpoints.challenge import service
from api.endpoints.challenge.schemas import DetectionFilePM, MinerOutput


class _Secret:
    def get_secret_value(self) -> str:
        return "test-secret-value"


class _DummySettings:
    def __init__(self):
        self.challenge = SimpleNamespace(
            bot_timeout=5,
            bot_runner=SimpleNamespace(
                url="http://bot-runner.local:8000",
                api_key=_Secret(),
                public_base_url="https://challenge.example",
                device_type="linux",
                bot="aad-detect",
                poll_timeout_sec=20,
                poll_interval_sec=1,
                request_timeout_sec=3,
                busy_retry_count=2,
                busy_backoff_initial_sec=0,
                busy_backoff_max_sec=0,
                framework_presets={"dummy-fw": "dummy-local"},
                shuffle_runs=True,
            ),
        )
        self.env = "TEST"


class _DummyPayloadManager:
    def __init__(self):
        self.current_task = None
        self.submitted_payloads = {}
        self.tasks = {
            0: {
                "name": "dummy-fw",
                "headless": False,
                "order_number": 0,
            }
        }
        self.updated = []

    def restart_manager(self):
        pass

    def update_task_status(self, order_number, status):
        self.updated.append((order_number, status))

    def check_task_compliance(self, _order_number):
        return True

    def calculate_score(self):
        return 1.0


def _miner_output() -> MinerOutput:
    return MinerOutput.model_construct(
        detection_files=[
            DetectionFilePM(file_name="dummy.js", content="window.__detected = true;")
        ]
    )


def _patch_common_score_helpers(monkeypatch, payload_manager):
    monkeypatch.setattr(service, "payload_manager", payload_manager)
    monkeypatch.setattr(service.ch_utils, "copy_detection_files", lambda **_: None)


def test_score_uses_bot_runner(monkeypatch):
    payload_manager = _DummyPayloadManager()
    monkeypatch.setattr(service, "config", _DummySettings())
    _patch_common_score_helpers(monkeypatch, payload_manager)

    trigger_calls = []

    def _trigger_run(**kwargs):
        trigger_calls.append(kwargs)
        return "batch-1"

    monkeypatch.setattr(
        service._bot_runner, "build_web_url", lambda base_url, api_prefix="": f"{base_url}{api_prefix}/_web"
    )
    monkeypatch.setattr(service._bot_runner, "trigger_run", _trigger_run)
    monkeypatch.setattr(service._bot_runner, "wait_for_run", lambda **_: "passed")

    result = service.score(
        miner_output=_miner_output(), web_url="https://challenge.example/_web"
    )

    assert result == 1.0
    assert len(trigger_calls) == 1
    assert [call["headless"] for call in trigger_calls] == [False]
    assert [call["count"] for call in trigger_calls] == [1]
    for trigger_call in trigger_calls:
        assert trigger_call["bot"] == "aad-detect"
        assert trigger_call["driver_preset"] == "dummy-local"
        assert trigger_call["device_type"] == "linux"
        assert trigger_call["web_url"] == "https://challenge.example/_web"
