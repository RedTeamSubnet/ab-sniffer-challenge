# Submission Contract

Required files and browser globals:

| File | Global function |
| --- | --- |
| `botasaurus.js` | `window.detect_botasaurus` |
| `headless.js` | `window.detect_headless_non_ua` |
| `nodriver.js` | `window.detect_nodriver` |
| `patchright.js` | `window.detect_patchright` |
| `puppeteerextra.js` | `window.detect_puppeteerextra` |
| `pydoll.js` | `window.detect_pydoll` |
| `seleniumbase.js` | `window.detect_seleniumbase` |
| `seleniumdriverless.js` | `window.detect_seleniumdriverless` |
| `zendriver.js` | `window.detect_zendriver` |

Every file must:

- be JavaScript and use its exact filename;
- contain no more than 500 lines;
- define and expose the expected function;
- return or resolve to a value interpreted as a boolean by the challenge page;
- pass `examples/miner_commit/eslint.config.mjs`.
