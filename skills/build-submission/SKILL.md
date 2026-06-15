---
name: build-submission
description: Prepare, build, and publish the AB Sniffer miner Docker image after validation and scoring. Use only when the human has accepted the latest score and wants to create a private linux/amd64 submission image.
---

# Build Submission

This workflow has two mandatory human confirmation gates.

## Prepare and Build

1. Confirm the human followed `docs/Testing_manuals.md` and tested through the documented
   `/score` endpoint.
2. Ask the human for the achieved score and whether it is satisfactory. Repeat the stated
   score back and stop unless the human explicitly confirms.
3. Ask for a fully tagged private repository, for example
   `redteamsubnet61/submission-abs-challenge:6.0.0`, and confirm it is private.
4. Run the source validator.
5. Prepare the miner commit directory:

   ```bash
   python3 skills/build-submission/scripts/prepare_submission.py
   ```

6. Validate the prepared directory.
7. Show the exact build command and ask for the first confirmation.
8. After confirmation, run from `examples/miner_commit`:

   ```bash
   docker build --platform linux/amd64 -t <repository:tag> .
   ```

Stop on any failure. Do not substitute the invalid form `docker build ... . <repo>`.

Do not invoke or depend on `skills/challenge-score`; that local helper is intentionally
ignored because it does not represent the miner testing workflow.

## Push

After a successful build, show the image name and ask for a separate push confirmation.
Only then run:

```bash
docker push <repository:tag>
```

Report the pushed digest when Docker returns one. Never log Docker credentials or place them
in repository files.
