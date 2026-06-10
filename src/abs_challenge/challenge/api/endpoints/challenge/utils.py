import os
import random
import time

from pydantic import validate_call
import requests

from api.endpoints.challenge.schemas import MinerOutput, TaskStatusEnum
from api.config import config
from api.logger import logger


@validate_call
def copy_detection_files(miner_output: MinerOutput, detections_dir: str) -> None:

    logger.info(f"Copying detection files from {detections_dir}")
    try:
        os.makedirs(detections_dir, exist_ok=True)
        for _detection_file_pm in miner_output.detection_files:
            _detection_path = os.path.join(detections_dir, _detection_file_pm.file_name)
            with open(_detection_path, "w") as _detection_file:
                _detection_file.write(_detection_file_pm.content)

        logger.success("Successfully copied detection files.")

    except Exception as err:
        logger.error(f"Failed to copy detection files: {err}!")
        raise

    return


def wait_for_task_completion(
    payload_manager,
    framework_order: int,
    framework_name: str,
    bot_timeout: int,
):
    while True:
        if payload_manager.check_task_compliance(framework_order):
            logger.info(
                f"Detection completed for {framework_name} within timeout."
            )
            payload_manager.update_task_status(
                framework_order, TaskStatusEnum.COMPLETED
            )
            break

        bot_timeout -= 1
        if bot_timeout <= 0:
            logger.warning(
                f"Detection for {framework_name} timed out after {config.challenge.bot_timeout} seconds."
            )
            payload_manager.update_task_status(
                framework_order, TaskStatusEnum.TIMED_OUT
            )
            break
        time.sleep(1)
    return


def run_verification_webhook():
    logger.info("Running human verification webhook.")
    try:
        _wait_interval = int(random.uniform(7, 15))
        _startup_url = str(config.challenge.verification.startup_url).rstrip("/")
        _url = str(config.challenge.verification.endpoint).rstrip("/")

        _headers = {
            "X-API-KEY": config.challenge.verification.api_key.get_secret_value()
        }
        _body = {
            "startup_url": _startup_url,
            "timed_close_sec": _wait_interval,
            "wait_close": False,
            # "extra": config.challenge.verification.extra,
        }

        logger.info(f"Sending request to {_url}, body: {_body}")

        response = requests.post(_url, headers=_headers, json=_body)

        if response.status_code == 200:
            logger.success("Successfully ran human verification webhook.")
        else:
            logger.error(
                f"Failed to run human verification webhook! Status code: {response.status_code}"
            )
    except Exception as err:
        logger.error(f"Error running human verification webhook: {str(err)}!")
        raise

    return


__all__ = [
    "copy_detection_files",
    "run_verification_webhook",
]
