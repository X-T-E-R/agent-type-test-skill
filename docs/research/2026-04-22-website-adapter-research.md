# Website Adapter Research

Date: `2026-04-22`

This note keeps dated implementation research outside the shipped skill package. The skill itself should only contain stable operational docs.

## 16Personalities

- Entry:
  - `https://www.16personalities.com/`
  - `https://www.16personalities.com/free-personality-test`
- Flow:
  - The test page mounts a front-end quiz component and advances through 10 native steps.
  - The runner can answer the real browser flow and then read the result page.
- Network hints:
  - Vite chunks
  - `build/assets/boot.*.js`
  - several lazy-loaded scripts
- Result extraction:
  - personality type code
  - type label
  - five result dimensions
- Risks:
  - front-end chunk changes
  - locale or cookie differences may affect result rendering

## SBTI Bilibili

- Entry:
  - `https://www.bilibili.com/blackboard/era/WijKT2bWuCJWPg8B.html`
- Flow:
  - Thin shell page with the main app inside a Bilibili activity bundle.
  - The runner can extract the full question list after entering the test and then submit through the page itself.
- Network hints:
  - `activity.hdslb.com/.../index-*.js`
  - `ReporterPb`
  - `biliMirror`
  - `log-reporter`
- Result extraction:
  - main type
  - match percentage
  - matched dimension count
  - 15 dimension cards
- Risks:
  - larger bundle surface
  - more front-end and anti-automation churn than local banks

## DTTI

- Entry:
  - `https://justmonikangel.github.io/-/`
- Flow:
  - Single-page app
  - questions and character profiles are exposed in page scripts
  - local scoring is feasible without a site API
- Network hints:
  - almost no business API
  - mostly React, Babel, and Tailwind CDN assets
- Result extraction:
  - scripted local extraction plus staged runner
- Risks:
  - very little API value
  - mostly a DOM and script extraction problem

