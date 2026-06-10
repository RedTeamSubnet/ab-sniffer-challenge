import random
from collections import defaultdict

from pydantic import validate_call
from api.config import config
from api.logger import logger
from api.endpoints.challenge.schemas import TaskStatusEnum

HUMAN_TASK_NAME = "human"

# Use OS entropy (CSPRNG) for the schedule so the run order/mode cannot be
# predicted by a miner even though this challenge code is public. Security here
# rests on unpredictable entropy, not on the algorithm being secret: the
# order_number -> framework mapping (`expected_order`) is the real secret and is
# never sent to the detection page.
_schedule_rng = random.SystemRandom()


def _spread_by_name(units: list[dict]) -> list[dict]:
    """Order units so the same framework never lands in two adjacent slots.

    Greedy by most-remaining count with a randomized tie-break: this is the
    standard arrangement that guarantees no two consecutive items share a name
    whenever it is feasible (max per-name count <= ceil(n / 2)), while staying
    unpredictable across cycles. If a name is so dominant that no valid spread
    exists, it degrades gracefully by allowing an adjacency rather than looping.
    """
    buckets: dict[str, list[dict]] = defaultdict(list)
    for unit in units:
        buckets[unit["name"]].append(unit)
    # Randomize the headed/headless order within each framework's bucket.
    for bucket in buckets.values():
        _schedule_rng.shuffle(bucket)

    ordered: list[dict] = []
    previous_name: str | None = None
    total = len(units)

    while len(ordered) < total:
        available = [name for name, bucket in buckets.items() if bucket]
        candidates = [name for name in available if name != previous_name] or available
        most_remaining = max(len(buckets[name]) for name in candidates)
        top = [name for name in candidates if len(buckets[name]) == most_remaining]
        chosen = _schedule_rng.choice(top)
        ordered.append(buckets[chosen].pop())
        previous_name = chosen

    return ordered


def build_run_schedule(
    framework_names: list[str],
    *,
    headed_count: int,
    headless_count: int,
    human_count: int,
    shuffle: bool,
) -> list[dict]:
    """Build the per-run task schedule for one scoring cycle.

    Each framework contributes ``headed_count`` headed runs and
    ``headless_count`` headless runs; ``human_count`` human-verification runs are
    appended. Every run is an independent unit (its own scoring slot). When
    ``shuffle`` is true the units are interleaved so neither the framework nor the
    mode follows a predictable order and the same framework is never adjacent;
    when false they are emitted deterministically for debugging.
    """
    units: list[dict] = []
    for name in framework_names:
        for _ in range(headed_count):
            units.append({"name": name, "headless": False})
        for _ in range(headless_count):
            units.append({"name": name, "headless": True})
    for _ in range(human_count):
        units.append({"name": HUMAN_TASK_NAME, "headless": None})

    if shuffle:
        return _spread_by_name(units)
    return units


class PayloadManager:
    @validate_call
    def __init__(self):
        self.tasks: dict[int, dict] = {}
        self.current_task: dict | None = None
        self.submitted_payloads: dict[int, dict] = {}
        self.expected_order: dict[int, str] = {}
        self.score: float = 0.0

        self.gen_ran_framework_sequence()
        return

    def restart_manager(self) -> None:
        self.tasks = {}
        self.current_task = None
        self.submitted_payloads = {}
        self.expected_order = {}
        self.score = 0.0

        self.gen_ran_framework_sequence()
        return

    def submit_task(
        self, framework_names: list[str], payload: dict, headless_non_ua: bool
    ) -> None:
        try:
            _expected_fm = self.expected_order[payload["order_number"]]
            _is_detected = _expected_fm in framework_names
            _is_collided = len(framework_names) > 1

            if _expected_fm == "human":
                _is_detected = True if len(framework_names) == 0 else False
                _is_collided = True if len(framework_names) > 0 else False

            self.submitted_payloads[payload["order_number"]] = {
                "expected_framework": _expected_fm,
                "submitted_framework": framework_names,
                "detected": _is_detected,
                "collided": _is_collided,
                "headless_non_ua": headless_non_ua,
            }

        except Exception as err:
            logger.error(f"Failed to add submitted payload: {err}!")
            raise
        return

    def calculate_score(self) -> float:
        _total_tasks = len(self.expected_order)

        for submission in self.submitted_payloads.values():
            if submission["expected_framework"] == "human" and (
                submission["collided"] or not submission["detected"]
            ):
                logger.warning("Couldn't detect human correctly, score is zero")
                return 0.0

        _correct_detections = sum(
            1 if not submission["collided"] else 0.1
            for submission in self.submitted_payloads.values()
            if submission["detected"]
        )

        if _total_tasks == 0:
            logger.warning("No tasks found, score is zero")
            return 0.0

        self.score = _correct_detections / _total_tasks
        return self.score

    def gen_ran_framework_sequence(self) -> None:
        _bot_runner_cfg = config.challenge.bot_runner
        _framework_names = [fw.name for fw in config.challenge.framework_images]

        _schedule = build_run_schedule(
            _framework_names,
            headed_count=_bot_runner_cfg.run_counts.headed,
            headless_count=_bot_runner_cfg.run_counts.headless,
            human_count=config.challenge.human_count,
            shuffle=_bot_runner_cfg.shuffle_runs,
        )

        for _index, _unit in enumerate(_schedule):
            self.expected_order[_index] = _unit["name"]
            self.tasks[_index] = {
                "name": _unit["name"],
                "headless": _unit["headless"],
                "order_number": _index,
                "status": TaskStatusEnum.CREATED,
            }

        return

    def update_task_status(self, order_number: int, new_status: TaskStatusEnum):
        if self.tasks[order_number] and self.tasks[order_number]["status"]:
            self.tasks[order_number]["status"] = new_status
        else:
            logger.error(
                f"Couldn't update status of task with order_number: {order_number}"
            )

    def check_task_compliance(self, order_number: int) -> bool:
        if order_number in self.submitted_payloads:
            return True
        return False

    def get_submission_report(self) -> dict[int, dict]:
        return self.submitted_payloads


payload_manager = PayloadManager()

__all__ = [
    "PayloadManager",
    "payload_manager",
]
