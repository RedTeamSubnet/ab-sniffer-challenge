import time
from typing import Any

import requests

from api.logger import logger

_TERMINAL_STATUSES = {"passed", "failed", "partial", "error"}


def _auth_headers(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"}


def _join_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def build_web_url(public_base_url: str, api_prefix: str = "") -> str:
    """Build the externally reachable detection page URL for bot-runner."""
    return _join_url(public_base_url, _join_url(api_prefix, "/_web"))


def trigger_run(
    *,
    base_url: str,
    api_key: str,
    bot: str,
    driver_preset: str,
    device_type: str,
    web_url: str,
    framework_name: str,
    request_timeout_sec: int,
    count: int = 1,
    headless: bool = True,
    busy_retry_count: int = 3,
    busy_backoff_initial_sec: float = 0.5,
    busy_backoff_max_sec: float = 5.0,
    session: requests.Session | None = None,
) -> str:
    """Start one bot-runner framework run and return its batch id.

    Only 429 responses are retried because they represent the runner's bounded
    concurrency cap. Other errors, especially 409 device mismatches, fail fast.
    """
    http = session or requests.Session()
    payload: dict[str, Any] = {
        "bot": bot,
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
    url = _join_url(base_url, "/api/runs")
    max_attempts = busy_retry_count + 1
    backoff = busy_backoff_initial_sec

    for attempt in range(max_attempts):
        response = http.post(
            url,
            json=payload,
            headers=_auth_headers(api_key),
            timeout=request_timeout_sec,
        )
        if response.status_code == 429 and attempt < busy_retry_count:
            delay = min(backoff, busy_backoff_max_sec)
            logger.info(
                "bot-runner is busy for framework %s; retrying in %.2fs",
                framework_name,
                delay,
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
    *,
    base_url: str,
    api_key: str,
    batch_id: str,
    poll_timeout_sec: int,
    poll_interval_sec: int,
    request_timeout_sec: int,
    session: requests.Session | None = None,
) -> str:
    """Poll bot-runner until a terminal status or timeout."""
    http = session or requests.Session()
    url = _join_url(base_url, f"/api/runs/{batch_id}")
    deadline = time.monotonic() + poll_timeout_sec

    while time.monotonic() < deadline:
        response = http.get(
            url,
            headers=_auth_headers(api_key),
            timeout=request_timeout_sec,
        )
        response.raise_for_status()
        status = str(response.json().get("status", ""))
        if status in _TERMINAL_STATUSES:
            return status
        time.sleep(poll_interval_sec)

    return "timeout"


__all__ = [
    "build_web_url",
    "trigger_run",
    "wait_for_run",
]
