#!/usr/bin/env python3

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

EXPECTED_FUNCTIONS = {
    "botasaurus.js": "detect_botasaurus",
    "headless.js": "detect_headless_non_ua",
    "nodriver.js": "detect_nodriver",
    "patchright.js": "detect_patchright",
    "puppeteerextra.js": "detect_puppeteerextra",
    "pydoll.js": "detect_pydoll",
    "seleniumbase.js": "detect_seleniumbase",
    "seleniumdriverless.js": "detect_seleniumdriverless",
    "zendriver.js": "detect_zendriver",
}


def repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def validate_structure(source_dir: Path) -> list[str]:
    errors: list[str] = []
    if not source_dir.is_dir():
        return [f"Submission directory does not exist: {source_dir}"]

    actual = {path.name for path in source_dir.glob("*.js")}
    expected = set(EXPECTED_FUNCTIONS)
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing:
        errors.append(f"Missing files: {', '.join(missing)}")
    if extra:
        errors.append(f"Unexpected JavaScript files: {', '.join(extra)}")

    for file_name, function_name in EXPECTED_FUNCTIONS.items():
        path = source_dir / file_name
        if not path.is_file():
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as exc:
            errors.append(f"{file_name}: cannot read file: {exc}")
            continue

        line_count = len(content.splitlines())
        if line_count > 500:
            errors.append(f"{file_name}: {line_count} lines exceeds the 500-line limit")

        definition = re.compile(
            rf"\b(?:async\s+)?function\s+{re.escape(function_name)}\s*\("
        )
        export = re.compile(
            rf"\bwindow\s*\.\s*{re.escape(function_name)}\s*=\s*{re.escape(function_name)}\b"
        )
        if not definition.search(content):
            errors.append(f"{file_name}: missing function definition {function_name}()")
        if not export.search(content):
            errors.append(
                f"{file_name}: missing window.{function_name} = {function_name} export"
            )
    return errors


def resolve_eslint_runtime(conda_env: str) -> tuple[list[str], Path]:
    conda = shutil.which("conda")
    if not conda:
        raise RuntimeError("Conda is not available")
    result = subprocess.run(
        [conda, "run", "-n", conda_env, "npm", "root", "-g"],
        capture_output=True,
        text=True,
        check=False,
    )
    module_root = Path(result.stdout.strip())
    if result.returncode != 0 or not module_root.is_dir():
        detail = result.stderr.strip() or "global npm module directory was not found"
        raise RuntimeError(f"Cannot use Conda environment {conda_env}: {detail}")
    return [conda, "run", "-n", conda_env, "eslint"], module_root


def run_eslint(
    source_dir: Path,
    config_path: Path,
    root: Path,
    runtime: tuple[list[str], Path | None] | None = None,
    conda_env: str = "npm-usage",
) -> list[str]:
    if not config_path.is_file():
        return [f"ESLint configuration does not exist: {config_path}"]

    try:
        command, module_root = runtime or resolve_eslint_runtime(conda_env)
    except RuntimeError as exc:
        return [str(exc)]

    node_modules = config_path.parent / "node_modules"
    created_link = False
    try:
        if module_root and not node_modules.exists():
            node_modules.symlink_to(module_root, target_is_directory=True)
            created_link = True
        with tempfile.TemporaryDirectory(
            prefix=".eslint-submission-",
            dir=config_path.parent,
        ) as temporary_dir:
            lint_dir = Path(temporary_dir)
            files = []
            for name in sorted(EXPECTED_FUNCTIONS):
                lint_path = lint_dir / name
                shutil.copy2(source_dir / name, lint_path)
                files.append(str(lint_path))
            cmd = [
                *command,
                "--format",
                "json",
                *files,
                "--config",
                str(config_path),
            ]
            result = subprocess.run(
                cmd,
                cwd=root / "examples" / "miner_commit",
                capture_output=True,
                text=True,
                check=False,
            )
    except OSError as exc:
        return [f"Unable to run ESLint: {exc}"]
    finally:
        if created_link:
            node_modules.unlink(missing_ok=True)

    if not result.stdout.strip():
        detail = (
            result.stderr.strip() or f"ESLint exited with status {result.returncode}"
        )
        return [f"ESLint produced no JSON output: {detail}"]

    try:
        reports = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        detail = result.stderr.strip()
        suffix = f" ({detail})" if detail else ""
        return [f"Unable to parse ESLint JSON output: {exc}{suffix}"]

    errors: list[str] = []
    for report in reports:
        path = Path(report.get("filePath", "unknown")).name
        for message in report.get("messages", []):
            if message.get("severity", 0) < 2:
                continue
            line = message.get("line", "?")
            column = message.get("column", "?")
            rule = message.get("ruleId") or "eslint"
            errors.append(
                f"{path}:{line}:{column}: {message.get('message', 'ESLint error')} [{rule}]"
            )

    if result.returncode != 0 and not errors:
        detail = result.stderr.strip() or f"exit status {result.returncode}"
        errors.append(f"ESLint failed: {detail}")
    return errors


def build_parser() -> argparse.ArgumentParser:
    root = repository_root()
    parser = argparse.ArgumentParser(description="Validate an AB Sniffer submission")
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
        "--config",
        type=Path,
        default=root / "examples" / "miner_commit" / "eslint.config.mjs",
    )
    parser.add_argument(
        "--conda-env",
        default="npm-usage",
        help="Conda environment containing eslint, @eslint/js, and globals",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    root = repository_root()
    source_dir = args.source.resolve()
    errors = validate_structure(source_dir)
    if not errors:
        errors.extend(
            run_eslint(
                source_dir,
                args.config.resolve(),
                root,
                conda_env=args.conda_env,
            )
        )

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print(f"Submission validation passed: {source_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
