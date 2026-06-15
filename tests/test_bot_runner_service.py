from types import SimpleNamespace

from api.endpoints.challenge import service
from api.endpoints.challenge.schemas import DetectionFilePM, MinerOutput


class _DummySettings:
    def __init__(self):
        self.challenge = SimpleNamespace(
            bot_timeout=5,
            framework_images=[SimpleNamespace(name="dummy-fw", preset="dummy-local")],
            bot_runner=SimpleNamespace(
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
                "server_url": "http://runner-2:8000",
                "device_type": "mac",
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
        commit_files=[
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
    wait_calls = []
    call_order = []

    def _trigger_run(**kwargs):
        call_order.append("trigger_run")
        trigger_calls.append(kwargs)
        return "batch-1"

    monkeypatch.setattr(service._bot_runner, "trigger_run", _trigger_run)
    monkeypatch.setattr(
        service.ch_utils,
        "wait_for_task_completion",
        lambda **_: call_order.append("wait_for_task_completion") or True,
    )
    monkeypatch.setattr(
        service._bot_runner,
        "wait_for_run",
        lambda batch_id, server_url: (
            call_order.append("wait_for_run"),
            wait_calls.append((batch_id, server_url)),
            "passed",
        )[-1],
    )

    result = service.score(
        miner_output=_miner_output(), web_url="https://challenge.example/_web"
    )

    assert result == 1.0
    assert len(trigger_calls) == 1
    assert wait_calls == [("batch-1", "http://runner-2:8000")]
    assert call_order == [
        "trigger_run",
        "wait_for_task_completion",
        "wait_for_run",
    ]
    assert [call["headless"] for call in trigger_calls] == [False]
    assert [call["count"] for call in trigger_calls] == [1]
    for trigger_call in trigger_calls:
        assert trigger_call["driver_preset"] == "dummy-local"
        assert trigger_call["server_url"] == "http://runner-2:8000"
        assert trigger_call["device_type"] == "mac"
