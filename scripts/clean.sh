#!/bin/bash
set -euo pipefail


## --- Base --- ##
# Getting path of this script file:
_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
_PROJECT_DIR="$(cd "${_SCRIPT_DIR}/.." >/dev/null 2>&1 && pwd)"
cd "${_PROJECT_DIR}" || exit 2
## --- Base --- ##


## --- Main --- ##
main()
{
	echo "[INFO]: Cleaning..."

	find . -type f -name ".DS_Store" -print -delete || exit 2
	find . -type f -name ".Thumbs.db" -print -delete || exit 2
	find . -type f -name ".coverage*" -print -delete || exit 2

	find . -type d -name "__pycache__" -exec rm -rfv {} + || exit 2
	find . -type d -name ".benchmarks" -exec rm -rfv {} + || exit 2
	find . -type d -name ".pytest_cache" -exec rm -rfv {} + || exit 2

	find . -type d -name ".git" -prune -o -type d -name "logs" -exec rm -rfv {} + || exit 2

	rm -rfv ./build || exit 2
	rm -rfv ./dist || exit 2
	rm -rfv ./site || exit 2
	find . -type d -name "*.egg-info" -exec rm -rfv {} + || exit 2

	echo "[OK]: Done."
}

main "${@:-}"
## --- Main --- ##
