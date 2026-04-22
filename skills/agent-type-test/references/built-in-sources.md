# Built-in Sources

## Local

### `mbti93-cn`

- Source: `karminski/llm-mbti-arena`
- Type: 93-question MBTI bank
- Generation: run `scripts/seed_mbti_bank.py`
- Purpose: default local bank for the current repository
- Provenance note: keep the upstream source and license note with the bundled copy

### `mini-ipip-en`

- Source: International Personality Item Pool (IPIP)
- Type: 20-item public-domain Big Five bank
- License: public domain
- Purpose: built-in English trait-profile bank with `dimension_scores` reporting

### `xxti-template`

- Minimal runnable template
- Useful for deriving custom `xxTI` families quickly

## Online

The runner supports `--bank-url` for remote JSON banks. Remote banks must follow `bank-schema.md`.

Good use cases:

- you maintain a separate repository of banks
- you want to host different `xxTI` families independently
- you do not want every bank bundled inside the skill package

## Why No Hard Dependency on Third-Party Scoring APIs

- third-party scoring APIs are brittle: rate limits, access restrictions, and redesigns happen frequently
- the skill should remain fully runnable from local assets first
- the default product path is a tester, not an API relay

## External Candidate Families

These are good candidates for future banks or adapters, but they are not all safe to vendor into a GPL repository as-is.

- `OJTS` / `OEJTS`
  - good English MBTI-like candidates
  - currently better treated as researched candidates because the upstream pages are published under `CC BY-NC-SA 4.0`
- `IPIP` Big Five banks
  - best default source when you want legally safe local expansion
  - public domain and easy to map into `dimension_scores`
- `Open Psychometrics` archetype tests such as Enneagram, Four Temperaments, and DISC
  - good entertainment-oriented expansion path
  - verify the exact license and whether bundling matches your release goals before vendoring
