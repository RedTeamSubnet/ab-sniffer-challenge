---
name: research-bot-detection
description: Research recent browser automation detection and bot classification changes for AB Sniffer. Use when investigating papers, browser documentation, official engineering articles, or bot-detection provider research before designing or revising detection JavaScript.
---

# Research Bot Detection

Research at execution time. Do not rely on a frozen list of techniques because browser
automation and anti-bot behavior changes frequently.

## Workflow

1. Read `references/research-policy.md`.
2. Inspect the current challenge files and target framework versions or presets.
3. Search for material published or updated recently.
4. Prefer primary sources: papers, browser specifications/documentation, project release
   notes, and provider engineering research.
5. Cross-check consequential vendor claims with an independent source when possible.
6. Separate observations into:
   - compliant automation leaks or behavioral signals;
   - fingerprinting or identity-linking methods prohibited by this challenge;
   - speculative or weakly supported claims.
7. Report actionable experiments, not copied detector code.

## Required Output

For every finding include:

- title, publisher, publication/update date, and direct URL;
- source type and confidence;
- affected browser, automation framework, or execution mode;
- what changed and why it matters;
- a compliant AB Sniffer experiment;
- false-positive and human-collision risks.

End with a prioritized test matrix for the current nine detection files. Explicitly label
fingerprinting findings as prohibited and do not implement or recommend them.
