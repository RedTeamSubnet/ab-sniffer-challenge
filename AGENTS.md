# AB Sniffer Agent Guide

## Objective

Develop nine browser-side JavaScript detectors that identify the expected automation
framework without firing on human-driven browsers. Work only from evidence that is permitted
by the challenge; browser fingerprinting is prohibited.

## Required Workflow

1. Use `research-bot-detection` for current papers, official project changes, and provider
   research. Mark fingerprinting findings as prohibited.
2. Edit the files in
   `src/abs_challenge/challenge/templates/static/detections`.
3. Use `validate-submission` before every score attempt.
4. Follow `docs/Testing_manuals.md` to start the challenge, call `/score`, and complete any
   requested human verification. The local score helper is not usable in miner workflows.
5. Review the score and available challenge output, then diagnose missed frameworks,
   collisions, human failures, and headless failures; iterate.
6. Use `build-submission` only after the human states the achieved score and confirms it is
   satisfactory.

## Submission Files

The submission contains exactly:

- `botasaurus.js`
- `headless.js`
- `nodriver.js`
- `patchright.js`
- `puppeteerextra.js`
- `pydoll.js`
- `seleniumbase.js`
- `seleniumdriverless.js`
- `zendriver.js`

Keep the existing function and `window` export names. Each file must be at most 500 lines and
must pass `examples/miner_commit/eslint.config.mjs`.

## Scoring Model

- Framework detection contributes 90% of the current local score.
- Headless detection contributes 10%.
- Collisions receive reduced credit.
- Any framework or headless detection during a human task makes the final score zero.
- The protected endpoints use `X-API-Key` with `ABS_CHALLENGE_API_KEY`.

## Important Paths

- Detection source:
  `src/abs_challenge/challenge/templates/static/detections`
- API schema and endpoints:
  `src/abs_challenge/challenge/api/endpoints/challenge`
- Scoring implementation:
  `src/abs_challenge/challenge/api/endpoints/challenge/_payload_manager.py`
- Miner image template:
  `examples/miner_commit`
- Prepared image files:
  `examples/miner_commit/src/commit`
- Manual scoring instructions:
  `docs/Testing_manuals.md`
- Repository skills:
  `skills`

Do not publish an image without separate human confirmations for build and push. Use only a
fully tagged private Docker repository and build for `linux/amd64`.
