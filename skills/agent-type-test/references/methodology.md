# Methodology

## Why Blind + Staged

If the tested AI sees the full bank, test name, dimensions, and scoring model up front, the run becomes closer to “how well can it role-play the test” than “how would it actually answer right now”.

Default method:

- hidden family
- staged disclosure
- strict JSON output
- repeated rounds

## Recommended Defaults

- `batch_size = 4`
- `rounds = 2` or `3`
- full questionnaire by default
- use `limit_questions` only when the user explicitly wants a shorter partial run

## Smoke Test vs Full Test

- smoke test
  - goal: verify that the skill, bank, transport, and reporting pipeline all work
  - recommended: `rounds = 1`, `limit_questions = 8`, `batch_size = 4`, and an explicit partial-run opt-in
- full test
  - goal: inspect aggregate results and stability
  - recommended: `rounds = 2~3`

`limit_questions` means “maximum questions asked per round”, not “questions per batch”.

## Reporting

At minimum, look at:

- per-round code
- aggregate code
- left/right score totals per dimension
- stability metrics

## Stability

The runner reports two stability views:

- `code_consistency`
  - modal full-code ratio across rounds
- `dimension_consistency`
  - modal winner ratio for each dimension across rounds

Entertainment-oriented tests do not need to be perfectly stable, but drift should be visible.

## Failure Handling

- invalid JSON: fail fast and keep the raw response
- missing answers: fail fast
- wrong answer ids: fail fast
- invalid choice mapping: fail fast

Do not silently “fix” bad outputs. Auditability matters more than convenience.
