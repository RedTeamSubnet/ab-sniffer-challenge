---
name: validate-submission
description: Validate AB Sniffer JavaScript submissions for required files, function exports, line limits, and the repository ESLint configuration. Use before scoring, copying files into the miner image, building, or publishing a submission.
---

# Validate Submission

Run from the challenge root:

```bash
python3 skills/validate-submission/scripts/validate_submission.py
```

The validator checks the exact nine filenames, maximum 500 lines per file, expected global
detector functions, and ESLint using `examples/miner_commit/eslint.config.mjs`. By default it
runs ESLint from the `npm-usage` Conda environment; override that with `--conda-env`.

Validation fails closed when Node, ESLint, its dependencies, the configuration, or JSON
output is unavailable. Do not bypass a failed check for scoring or publishing.

The Conda environment must contain global `eslint`, `@eslint/js`, and `globals` packages.

To validate prepared miner files:

```bash
python3 skills/validate-submission/scripts/validate_submission.py \
  --source examples/miner_commit/src/commit
```

Read `references/submission-contract.md` when changing filenames or detector entry points.
