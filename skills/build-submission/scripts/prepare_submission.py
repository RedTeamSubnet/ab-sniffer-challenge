#!/usr/bin/env python3

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


EXPECTED_FILES = (
    "botasaurus.js",
    "headless.js",
    "nodriver.js",
    "patchright.js",
    "puppeteerextra.js",
    "pydoll.js",
    "seleniumbase.js",
    "seleniumdriverless.js",
    "zendriver.js",
)


def repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def run_validator(root: Path, source: Path) -> None:
    validator = root / "skills" / "validate-submission" / "scripts" / "validate_submission.py"
    result = subprocess.run(
        [sys.executable, str(validator), "--source", str(source)],
        cwd=root,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Validation failed for {source}")


def prepare(root: Path, source: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for stale in destination.glob("*.js"):
        stale.unlink()
    for name in EXPECTED_FILES:
        shutil.copy2(source / name, destination / name)


def main() -> int:
    root = repository_root()
    parser = argparse.ArgumentParser(description="Prepare AB Sniffer miner commit files")
    parser.add_argument(
        "--source",
        type=Path,
        default=root
        / "src"
        / "abs_challenge"
        / "challenge"
        / "templates"
        / "static"
        / "detections",
    )
    parser.add_argument(
        "--destination",
        type=Path,
        default=root / "examples" / "miner_commit" / "src" / "commit",
    )
    args = parser.parse_args()

    try:
        run_validator(root, args.source.resolve())
        prepare(root, args.source.resolve(), args.destination.resolve())
        run_validator(root, args.destination.resolve())
        print(f"Prepared submission: {args.destination.resolve()}")
        return 0
    except (OSError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
