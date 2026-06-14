import random
from dataclasses import dataclass

from pydantic import validate_call
from api.config import config
from api.logger import logger
from api.endpoints.challenge.schemas import TaskStatusEnum

HUMAN_TASK_NAME = "human"
FRAMEWORK_SCORE_WEIGHT = 0.9
HEADLESS_SCORE_WEIGHT = 0.1
HEADLESS_ALLOWED_MISSES = 3


@dataclass
class ScoringTelemetry:
    request_id: str | None = None
    total_file_size_bytes: int = 0
    runtime_seconds: float = 0.0
    network_rx_bytes: int = 0
    network_tx_bytes: int = 0
    score: float | None = None


class ScoringTelemetryManager:
    def __init__(self):
        self._latest = ScoringTelemetry()

    def set_telemetry(
        self,
        request_id: str | None = None,
        total_file_size_bytes: int = 0,
        runtime_seconds: float = 0.0,
        network_rx_bytes: int = 0,
        network_tx_bytes: int = 0,
        score: float | None = None,
    ) -> None:
        self._latest = ScoringTelemetry(
            request_id=request_id,
            total_file_size_bytes=total_file_size_bytes,
            runtime_seconds=runtime_seconds,
            network_rx_bytes=network_rx_bytes,
            network_tx_bytes=network_tx_bytes,
            score=score,
        )
        logger.info(
            f"[Telemetry] Recorded: runtime={runtime_seconds:.2f}s, "
            f"net_rx={network_rx_bytes}, net_tx={network_tx_bytes}"
        )

    def get_telemetry(self) -> ScoringTelemetry:
        return self._latest

    def reset(self) -> None:
        self._latest = ScoringTelemetry()


def build_run_schedule(
    framework_names: list[str],
    servers: list[dict],
    *,
    headed_count: int,
    headless_count: int,
    human_count: int,
    shuffle: bool,
) -> list[dict]:
    """Build the per-run task schedule for one scoring cycle.

    Each framework contributes ``headed_count`` headed runs and
    ``headless_count`` headless runs on every configured server. Human runs are
    appended once and are not assigned to a bot-runner server.
    """
    units: list[dict] = []
    for name in framework_names:
        for server in servers:
            for _ in range(headed_count):
                units.append(
                    {
                        "name": name,
                        "headless": False,
                        "server_url": server["url"],
                        "device_type": server["device_type"],
                    }
                )
            for _ in range(headless_count):
                units.append(
                    {
                        "name": name,
                        "headless": True,
                        "server_url": server["url"],
                        "device_type": server["device_type"],
                    }
                )
    for _ in range(human_count):
        units.append(
            {
                "name": HUMAN_TASK_NAME,
                "headless": None,
                "server_url": None,
                "device_type": None,
            }
        )

    if shuffle:
        random.shuffle(units)
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
        self, framework_names: list[str], payload: dict, headless: bool
    ) -> None:
        try:
            _expected_fm = self.expected_order[payload["order_number"]]
            _expected_headless = self.tasks[payload["order_number"]]["headless"]
            _is_detected = _expected_fm in framework_names
            _is_collided = len(framework_names) > 1
            _headless_failed = False

            if _expected_fm == "human":
                _is_detected = True if len(framework_names) == 0 else False
                _is_collided = True if len(framework_names) > 0 else False
            else:
                _headless_failed = (
                    headless != _expected_headless or len(framework_names) == 0
                )

            self.submitted_payloads[payload["order_number"]] = {
                "expected_framework": _expected_fm,
                "expected_headless": _expected_headless,
                "submitted_framework": framework_names,
                "detected": _is_detected,
                "collided": _is_collided,
                "headless": headless,
                "headless_failed": _headless_failed,
                "server_url": self.tasks[payload["order_number"]]["server_url"],
                "device_type": self.tasks[payload["order_number"]]["device_type"],
            }

        except Exception as err:
            logger.error(f"Failed to add submitted payload: {err}!")
            raise
        return

    def calculate_score(self) -> float:
        if not self._score_human():
            return 0.0

        framework_score = self._score_framework()
        if framework_score == 0.0:
            logger.warning("Framework score is zero, final score is zero")
            return 0.0

        headless_score = self._score_headless()
        self.score = framework_score + headless_score
        logger.info(
            f"Final score calculated: {self.score} "
            f"(framework={framework_score}, headless={headless_score})"
        )
        return self.score

    def _score_human(self) -> bool:
        for submission in self.submitted_payloads.values():
            if submission["expected_framework"] == "human" and (
                submission["collided"]
                or not submission["detected"]
                or submission["headless"]
            ):
                logger.warning("Couldn't detect human correctly, score is zero")
                return False
        return True

    def _score_framework(self) -> float:
        framework_weights = {
            framework.name: framework.weight
            for framework in config.challenge.framework_images
        }
        total_weight = sum(framework_weights.values())
        if total_weight == 0:
            logger.warning("No framework weights found, framework score is zero")
            return 0.0

        weighted_accuracy = 0.0
        for framework_name, framework_weight in framework_weights.items():
            expected_count = sum(
                1
                for expected_framework in self.expected_order.values()
                if expected_framework == framework_name
            )
            if expected_count == 0:
                continue

            earned_points = sum(
                0.1 if submission["collided"] else 1.0
                for submission in self.submitted_payloads.values()
                if submission["expected_framework"] == framework_name
                and submission["detected"]
            )
            framework_accuracy = earned_points / expected_count
            weighted_accuracy += framework_accuracy * framework_weight
            logger.info(
                f"Framework {framework_name}: accuracy={framework_accuracy}, "
                f"weight={framework_weight}"
            )

        return FRAMEWORK_SCORE_WEIGHT * (weighted_accuracy / total_weight)

    def _score_headless(self) -> float:
        headless_failures = sum(
            1
            for submission in self.submitted_payloads.values()
            if submission["expected_framework"] != HUMAN_TASK_NAME
            and submission["headless_failed"]
        )
        penalty = HEADLESS_SCORE_WEIGHT / HEADLESS_ALLOWED_MISSES
        score = max(0.0, HEADLESS_SCORE_WEIGHT - (headless_failures * penalty))
        logger.info(
            f"Headless detection: failures={headless_failures}, score={score}"
        )
        return score

    def gen_ran_framework_sequence(self) -> None:
        _bot_runner_cfg = config.challenge.bot_runner
        _framework_names = [fw.name for fw in config.challenge.framework_images]
        _servers = [
            {
                "url": str(server.url),
                "device_type": server.device_type,
            }
            for server in _bot_runner_cfg.servers
        ]

        _schedule = build_run_schedule(
            _framework_names,
            _servers,
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
                "server_url": _unit["server_url"],
                "device_type": _unit["device_type"],
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
scoring_telemetry_manager = ScoringTelemetryManager()

__all__ = [
    "PayloadManager",
    "payload_manager",
    "ScoringTelemetry",
    "ScoringTelemetryManager",
    "scoring_telemetry_manager",
]
