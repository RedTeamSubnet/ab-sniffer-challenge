from pathlib import Path

from api.endpoints.challenge import service
from api.endpoints.challenge.schemas import PayloadPM, SubmissionPayloadsPM, _frameworks_names


_ROOT = Path(__file__).resolve().parent.parent
_TEMPLATE_DIR = _ROOT / "src" / "abs_challenge" / "challenge" / "templates"


def test_headless_detector_is_loaded_before_framework_detectors():
    index_html = (_TEMPLATE_DIR / "index.html").read_text()

    headless_idx = index_html.index('static/detections/headless_non_ua.js')
    framework_idx = index_html.index('static/detections/botasaurus.js')

    assert headless_idx < framework_idx


def test_bundle_calls_headless_detector_before_framework_detectors():
    bundle = (_TEMPLATE_DIR / "static" / "js" / "main.e9cd64cf.js").read_text()

    headless_idx = bundle.index("detect_headless_non_ua")
    framework_loop_idx = bundle.index("window.ASB_FRAMEWORK_NAMES", headless_idx)

    assert headless_idx < framework_loop_idx
    assert "headless_non_ua" in bundle


def test_headless_detector_does_not_use_user_agent():
    detector = (
        _TEMPLATE_DIR / "static" / "detections" / "headless_non_ua.js"
    ).read_text()
    executable_source = "\n".join(
        line for line in detector.splitlines() if not line.strip().startswith("*")
    )

    assert "navigator.userAgent" not in executable_source
    assert "navigator.userAgentData" not in executable_source


def test_submission_payload_accepts_headless_non_ua_field():
    payload = SubmissionPayloadsPM(
        results=[
            PayloadPM(detected=False, raw=False, framework_name=f"fw-{i}")
            for i in range(len(_frameworks_names))
        ],
        headless_non_ua=True,
        order_number=0,
    )

    assert payload.headless_non_ua is True
    assert payload.model_dump()["headless_non_ua"] is True


def test_submit_payload_preserves_headless_non_ua_in_payload_manager(monkeypatch):
    captured = {}

    class _Manager:
        def submit_task(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(service, "payload_manager", _Manager())
    payload = SubmissionPayloadsPM(
        results=[
            PayloadPM(detected=False, raw=False, framework_name=f"fw-{i}")
            for i in range(len(_frameworks_names))
        ],
        headless_non_ua=True,
        order_number=0,
    )

    service.submit_payload(payload)

    assert captured["headless_non_ua"] is True
    assert captured["payload"]["headless_non_ua"] is True
