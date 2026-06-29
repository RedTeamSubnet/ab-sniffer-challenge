import logging
import sys
from pathlib import Path

import pytest

# Ensure the nested challenge API package is on sys.path so that `api.*`
# imports resolve for unit tests, matching the newer challenge project layout.
_API_DIR = (
    Path(__file__).resolve().parent.parent / "src" / "abs_challenge" / "challenge"
)
if _API_DIR.is_dir() and str(_API_DIR) not in sys.path:
    sys.path.insert(0, str(_API_DIR))

_SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if _SRC_DIR.is_dir() and str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

logger = logging.getLogger(__name__)


@pytest.fixture(scope="session", autouse=True)
def setup_and_teardown():
    # Equivalent of setUp
    logger.info("Setting up...")

    yield  # This is where the testing happens!

    # Equivalent of tearDown
    logger.info("Tearing down!")
