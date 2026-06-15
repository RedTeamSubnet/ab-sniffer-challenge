import time
from typing import Any

import requests

from api.config import config
from api.logger import logger

_TERMINAL_STATUSES = {"passed", "failed", "partial", "error"}


def _auth_headers(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"}


def _join_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def trigger_run(
    *,
    server_url: str,
    device_type: str,
    driver_preset: str,
    framework_name: str,
    count: int = 1,
    headless: bool = True,
    session: requests.Session | None = None,
) -> str:
    """Start one bot-runner framework run and return its batch id.

    Only 429 responses are retried because they represent the runner's bounded
    concurrency cap. Other errors, especially 409 device mismatches, fail fast.
    """
    bot_runner_config = config.challenge.bot_runner
    http = session or requests.Session()
    web_url = _join_url(
        str(bot_runner_config.public_base_url),
        _join_url(config.api.prefix, "/_web"),
    )
    logger.info(f"web_url for bot-runner: {web_url}")
    payload: dict[str, Any] = {
        "bot": bot_runner_config.bot,
        "driver_preset": driver_preset,
        "device_type": device_type,
        "url": web_url,
        "count": count,
        "headless": headless,
        "metadata": {
            "framework": framework_name,
            "headless": headless,
            "count": count,
        },
    }
    url = _join_url(server_url, "/api/runs")
    max_attempts = bot_runner_config.busy_retry_count + 1
    backoff = bot_runner_config.busy_backoff_initial_sec

    for attempt in range(max_attempts):
        response = http.post(
            url,
            json=payload,
            headers=_auth_headers(bot_runner_config.api_key.get_secret_value()),
            timeout=bot_runner_config.request_timeout_sec,
        )
        if response.status_code == 429 and attempt < bot_runner_config.busy_retry_count:
            delay = min(backoff, bot_runner_config.busy_backoff_max_sec)
            logger.info(
                f"bot-runner is busy for framework {framework_name}; "
                f"retrying in {delay:.2f}s"
            )
            time.sleep(delay)
            backoff = delay * 2 if delay > 0 else 0
            continue

        response.raise_for_status()
        data = response.json()
        batch_id = data.get("batch_id")
        if not batch_id:
            raise ValueError("bot-runner response did not include batch_id")
        return str(batch_id)

    raise RuntimeError("unreachable bot-runner retry state")


def wait_for_run(
    batch_id: str,
    server_url: str,
) -> str:
    """Check bot-runner status up to five times."""
    bot_runner_config = config.challenge.bot_runner
    url = _join_url(server_url, f"/api/runs/{batch_id}")

    for attempt in range(5):
        try:
            response = requests.get(
                url,
                headers=_auth_headers(bot_runner_config.api_key.get_secret_value()),
                timeout=bot_runner_config.request_timeout_sec,
            )
            response.raise_for_status()
            status = str(response.json().get("status", ""))
            if status in _TERMINAL_STATUSES:
                return status
        except requests.RequestException:
            if attempt == 4:
                raise

        if attempt < 4:
            time.sleep(2**attempt)

    return "timeout"


__all__ = [
    "trigger_run",
    "wait_for_run",
]
