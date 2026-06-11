from api.endpoints.challenge import utils
from api.endpoints.challenge.schemas import TaskStatusEnum


class _PayloadManager:
    def __init__(self, completed: bool):
        self.completed = completed
        self.updated = []

    def check_task_compliance(self, _order_number):
        return self.completed

    def update_task_status(self, order_number, status):
        self.updated.append((order_number, status))


def test_wait_for_task_completion_marks_completed():
    payload_manager = _PayloadManager(completed=True)

    result = utils.wait_for_task_completion(
        payload_manager=payload_manager,
        framework_order=2,
        framework_name="nodriver",
        timeout=5,
    )

    assert result is True
    assert payload_manager.updated == [(2, TaskStatusEnum.COMPLETED)]


def test_wait_for_task_completion_marks_timed_out(monkeypatch):
    payload_manager = _PayloadManager(completed=False)
    monkeypatch.setattr(utils.time, "sleep", lambda _: None)

    result = utils.wait_for_task_completion(
        payload_manager=payload_manager,
        framework_order=3,
        framework_name="human",
        timeout=2,
    )

    assert result is False
    assert payload_manager.updated == [(3, TaskStatusEnum.TIMED_OUT)]
