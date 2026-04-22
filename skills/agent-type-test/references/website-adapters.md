# Website Adapters

This layer documents how website-backed tests are integrated without mixing site-specific logic into the local bank or scoring pipeline.

## Goals

- keep a separate adapter profile for each site
- decide between Playwright, API, or hybrid flow only after discovery
- avoid hard-coding site-specific logic into the shared runner

## Built-in Profiles

- `16personalities`
  - URL: `https://www.16personalities.com/`
  - strategy: `browser`
  - status: implemented
- `sbti-bilibili`
  - URL: `https://www.bilibili.com/blackboard/era/WijKT2bWuCJWPg8B.html`
  - strategy: `browser`
  - status: implemented
- `dtti`
  - URL: `https://justmonikangel.github.io/-/`
  - strategy: `browser`
  - status: implemented

## Adapter Data Model

Each profile should include at least:

- `id`
- `label`
- `family`
- `entry_url`
- `capture_strategy`
- `status`
- `notes`

## Execution Model

For browser adapters, keep the execution model in two phases:

1. discovery
  - locate entry points, buttons, question containers, and result containers
  - inspect fetch, XHR, GraphQL, and script-rendering hints
2. run
  - execute staged answers
  - follow the site’s native flow
  - extract code, label, and detail from the result page

With this split, site changes usually require adapter maintenance instead of rewriting the shared scorer.
