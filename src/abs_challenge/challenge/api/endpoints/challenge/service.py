import pathlib
from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import validate_call

from api.core.exceptions import BaseHTTPException
from api.core.constants import EnvEnum
from api.config import config
from api.endpoints.challenge.schemas import (
    MinerInput,
    MinerOutput,
    SubmissionPayloadsPM,
    TaskStatusEnum,
)
from api.endpoints.challenge import utils as ch_utils
from api.logger import logger
from api.endpoints.challenge._payload_manager import payload_manager
from api.endpoints.challenge import _bot_runner

_src_dir = pathlib.Path(__file__).parent.parent.parent.parent.resolve()


def get_task() -> MinerInput:
    """Return a new challenge task."""
    return MinerInput()


@validate_call
def score(
    miner_output: MinerOutput,
    web_url: str,
) -> float:

    _score = 0.0
    global payload_manager
    payload_manager.restart_manager()
    _all_tasks = payload_manager.tasks

    try:
        # Copy the detection script to the templates directory
        _detections_dir = str(_src_dir / "templates" / "static" / "detections")

        ch_utils.copy_detection_files(
            miner_output=miner_output,
            detections_dir=_detections_dir,
        )

        _bot_runner_config = config.challenge.bot_runner
        _framework_presets = {
            fw.name: fw.preset for fw in config.challenge.framework_images
        }

        _driver_tasks = [t for t in _all_tasks.values() if t["name"] != "human"]
        _human_tasks = len(_all_tasks) - len(_driver_tasks)
        _headed = sum(1 for t in _driver_tasks if t["headless"] is False)
        _headless_total = sum(1 for t in _driver_tasks if t["headless"] is True)
        _run_order = (
            "shuffled" if _bot_runner_config.shuffle_runs else "deterministic"
        )
        logger.info(
            f"Scoring schedule: {len(_all_tasks)} runs "
            f"({len(_driver_tasks)} driver [{_headed} headed / "
            f"{_headless_total} headless] + {_human_tasks} human), "
            f"order={_run_order}"
        )

        for _framework in _all_tasks.values():
            _framework_name = str(_framework["name"])
            _framework_order = _framework["order_number"]
            _headless = _framework["headless"]
            _server_url = _framework["server_url"]
            _device_type = _framework["device_type"]
            payload_manager.current_task = _framework
            if _framework_name == "human":
                logger.warning(
                    f"Please visit endpoint {web_url} to complete human verification for the task."
                )

                if config.env == EnvEnum.PRODUCTION:
                    ch_utils.run_verification_webhook()

                _bot_timeout = config.challenge.human_timeout
            else:
                _bot_timeout = config.challenge.bot_timeout

                payload_manager.update_task_status(
                    _framework_order, TaskStatusEnum.RUNNING
                )
                logger.info(f"Running detection against {_framework_name}")
                try:
                    _driver_preset = _framework_presets.get(_framework_name)
                    if not _driver_preset:
                        raise ValueError(
                            f"No bot-runner driver preset configured for {_framework_name}"
                        )

                    _mode = "headless" if _headless else "headed"
                    logger.info(
                        f"Running {_framework_name} in {_mode} mode on "
                        f"{_server_url} ({_device_type}, order {_framework_order})"
                    )
                    _batch_id = _bot_runner.trigger_run(
                        server_url=_server_url,
                        device_type=_device_type,
                        driver_preset=_driver_preset,
                        framework_name=_framework_name,
                        count=1,
                        headless=_headless,
                    )
                    _run_status = _bot_runner.wait_for_run(
                        _batch_id,
                        server_url=_server_url,
                    )
                    if _run_status not in {"passed", "partial"}:
                        logger.warning(
                            f"bot-runner returned {_run_status} for "
                            f"{_framework_name} in {_mode} mode"
                        )
                except Exception as err:
                    logger.error(
                        f"Error running detection for {_framework_name}: {str(err)}"
                    )
                    payload_manager.update_task_status(
                        _framework_order, TaskStatusEnum.FAILED
                    )
                    continue

            ch_utils.wait_for_task_completion(
                payload_manager=payload_manager,
                framework_order=_framework_order,
                framework_name=_framework_name,
                timeout=_bot_timeout,
            )
        _score = payload_manager.calculate_score()
        payload_manager.submitted_payloads["final_score"] = _score
        logger.info(f"Final score calculated: {_score}")

    except Exception as err:
        if isinstance(err, BaseHTTPException):
            raise
        logger.error(f"Failed to score the miner output: {str(err)}!")
        raise

    return _score


def get_results() -> dict:
    global payload_manager
    logger.info("Sending detection results...")

    try:
        _submission_report = payload_manager.get_submission_report()
        if _submission_report:
            logger.info("Returning detection results")
            return _submission_report
        else:
            logger.warning("No detection results available")
            return {}

    except Exception as err:
        logger.error(f"Error retrieving results: {str(err)}")
        return {}


def submit_payload(_payload: SubmissionPayloadsPM):
    global payload_manager
    try:
        _final_results = _payload.get_final_results()
        payload_manager.submit_task(
            framework_names=_final_results,
            payload=_payload.model_dump(),
            headless_non_ua=_payload.headless_non_ua,
        )
    except Exception as err:
        logger.error(f"Error submitting payload: {str(err)}")
        raise


@validate_call(config={"arbitrary_types_allowed": True})
def get_web(request: Request) -> HTMLResponse:
    global payload_manager
    _current_task = payload_manager.current_task
    if _current_task and _current_task["order_number"]:
        _order_number = _current_task["order_number"]
    else:
        _order_number = 0
    templates = Jinja2Templates(directory=str(_src_dir / "templates"))
    _abs_result_endpoint = _bot_runner._join_url(
        str(config.challenge.bot_runner.public_base_url), "/_payload"
    )
    logger.info(
        f"serving web page at {_abs_result_endpoint} for order number {_order_number}"
    )

    html_response = templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "abs_result_endpoint": _abs_result_endpoint,
            "abs_session_order_number": _order_number,
            "asb_framework_names": [
                fw.name for fw in config.challenge.framework_images
            ],
        },
    )
    return html_response


__all__ = [
    "get_task",
    "get_web",
    "score",
    "get_results",
]
