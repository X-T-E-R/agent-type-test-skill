---
name: agent-type-test
description: Use when an AI agent needs to be tested with staged MBTI or other xxTI-style questionnaires, especially when the user wants gradual disclosure, blind prompts, local or online question banks, reusable scoring, repeatable runs, or protocol-friendly execution through manual handoff, subprocess bridges, or OpenAI-compatible chat APIs.
---

# AgentTypeTest

## Overview

This skill turns “test an AI with a personality questionnaire” into a repeatable workflow instead of a one-off prompt trick. It loads question banks, sends staged batches, collects answers, scores them, aggregates stability, and avoids exposing the full bank or scoring rules to the tested AI.

## Default Intent

- If a human shares this repo and says “try it”, “play with it”, “试玩一下”, or “测测你自己”, assume they want **you**, the current agent, to take the test.
- In that situation, you are the **test subject**, not the repo maintainer.
- Do **not** begin with install audits, smoke tests, sample adapters, or site probes unless the human explicitly asks you to verify the repo itself.

## Workflow

### 0. Decide Your Role First

- `self-subject mode`
  - default when the human wants you to try the skill on yourself
  - if no specific test is named, default to `mbti93-cn` for the first run instead of stopping at maintainer checks
  - prefer `prepare-session` + `finalize-session` if you do not already have a bridge that can feed prompts back into your own runtime
- `maintainer mode`
  - only when the human explicitly asks whether the repo works, asks you to install it, or asks you to debug / verify / develop it

### 1. Choose the Test First

- If the user directly names a supported test, use that test.
- If the user gives one of the supported website tests by name or URL, route directly to the matching website adapter:
  - `16personalities`
  - `sbti-bilibili`
  - `dtti`
- If the user does **not** specify a test and they want you to try the skill on yourself, default to `mbti93-cn` for the first pass.
- If the user does **not** specify a test and the request is genuinely about choosing among multiple tests, then ask them to choose.
- The current built-in choices are:
  - local banks: `mbti93-cn`, `mini-ipip-en`
  - website adapters: `16personalities`, `sbti-bilibili`, `dtti`

### 2. Choose the Bank Source

- For local MBTI-style runs, prefer the built-in local bank: `mbti93-cn`.
- For local trait-profile runs, prefer the built-in local bank: `mini-ipip-en`.
- If the user provides a remote bank URL, use the remote JSON bank.
- If the user wants a new `xxTI` family, check `references/bank-schema.md` and create a new bank that follows the shared schema.

### 3. Choose the Execution Path

- `prepare-session` + `finalize-session`
  - preferred when **you are the tested agent**
  - the runner writes batch packets into a session directory
  - you answer each packet as yourself by writing the matching `batch-XX.response.json` files
  - after all responses are written, `finalize-session` scores them and renders the reports
- `manual`
  - use this when a human operator is forwarding batches between the runner and another AI
  - this is not the best default when you are both the operator and the tested agent inside a non-interactive tool environment

- `subprocess`
  - preferred for CLI agents, local wrappers, or MCP bridge adapters
  - the external process reads a batch packet from stdin and writes JSON to stdout
- `openai-compatible`
  - use this when the user already has a compatible online API
  - the runner uses standard `/chat/completions`

### 4. Keep the Test Blind and Staged

- default to 3-5 questions per batch
- hide `MBTI`, `personality test`, full dimensions, and scoring rules by default
- send only the current batch and a strict JSON response requirement
- tell the tested AI not to guess the hidden test family, hidden intent, or scoring logic
- do not paste raw bank files, skill code, or the full question set to the tested AI

### 5. Prefer Repeatable Runs Over Single-Shot Guessing

- If the user cares about stability, run at least `2-3` rounds.
- Prefer shuffled question order between rounds.
- Final reports should include:
  - per-round result
  - aggregate result
  - per-dimension consistency
  - overall code consistency

## Self-Use First

If the human wants **you** to take the test, start with the file-based self-session flow instead of maintainer checks.

### Prepare a Self-Test Session

```powershell
python scripts/agent_type_test_runner.py prepare-session `
  --bank mbti93-cn `
  --batch-size 4 `
  --rounds 2
```

### Answer the Prepared Batches

- Open one `batch-XX.packet.json` at a time.
- Read the `prompt_text` field.
- Answer as **yourself**, not as the repo reviewer, debugger, or maintainer.
- Save the JSON answer to the matching `batch-XX.response.json`.
- Do not inspect the full bank or scoring rules while answering.

### Finalize the Self-Test Session

```powershell
python scripts/agent_type_test_runner.py finalize-session `
  --session-dir tmp/agent-type-test-session-YYYYMMDD-HHMMSS
```

### What Not To Do In Self-Subject Mode

- Do not stop after installation or smoke tests.
- Do not run `sample_target_adapter.py` if the goal is to profile yourself.
- Do not treat site probes or adapter verification as the main task.
- Do not search the repo for answer keys before answering.

## Maintainer Checks

### List Built-in Banks

```powershell
python scripts/agent_type_test_runner.py list-banks
```

### Run the Smallest Smoke Test

This is the smallest useful smoke test. `--rounds 1` is fine here because the goal is just to prove that the skill, bank, transport, and report pipeline are connected.

```powershell
python .\skills\agent-type-test\scripts\agent_type_test_runner.py run `
  --bank mbti93-cn `
  --transport subprocess `
  --target-command-json "[\"python\", \"skills/agent-type-test/scripts/sample_target_adapter.py\"]" `
  --batch-size 4 `
  --limit-questions 8 `
  --rounds 1 `
  --seed 42
```

Notes:

- `--limit-questions 8` means “at most 8 questions asked in this round”, not “8 questions per batch”.
- `--batch-size 4` means 4 questions per batch, so this example produces 2 batches.
- Relative paths inside `--target-command-json` resolve from the current working directory. Use absolute paths if the cwd is unstable.
- If you want a no-autofill website run, do not set `--limit-questions` below the full site question count.
- Normal evaluation should leave `--limit-questions` unset. Treat it as a debug or extreme-short-run switch, not the default evaluation mode.

### Seed the Local MBTI Bank

```powershell
python scripts/seed_mbti_bank.py
```

### Run a Blind Staged Test with a Local Sample Adapter

```powershell
python scripts/agent_type_test_runner.py run `
  --bank mbti93-cn `
  --transport subprocess `
  --target-command-json "[\"python\", \"scripts/sample_target_adapter.py\"]" `
  --batch-size 4 `
  --limit-questions 12 `
  --rounds 2
```

### Run Against an OpenAI-Compatible Endpoint

```powershell
python scripts/agent_type_test_runner.py run `
  --bank mbti93-cn `
  --transport openai-compatible `
  --base-url "https://api.openai.com/v1" `
  --model "gpt-4o-mini" `
  --api-key "$env:OPENAI_API_KEY" `
  --batch-size 4 `
  --rounds 2
```

## Core Commands

### Create or Refresh the Built-in MBTI Bank

```powershell
python scripts/seed_mbti_bank.py --force
```

### Validate a Bank

```powershell
python scripts/agent_type_test_runner.py validate-bank --bank assets/banks/xxti-template.json
```

### Run the Built-in Self-Test

```powershell
python scripts/selftest.py
```

### List Built-in Website Adapter Profiles

```powershell
python scripts/agent_type_test_runner.py list-site-adapters
```

### Probe a Website Adapter with Playwright

```powershell
python scripts/browser_adapter_runner.py probe `
  --adapter 16personalities `
  --output tmp/adapter-16personalities.json
```

### Run the Implemented DTTI Website Adapter

```powershell
python scripts/website_test_runner.py run `
  --adapter dtti `
  --transport subprocess `
  --target-command-json "[\"python\", \"scripts/sample_target_adapter.py\", \"--mode\", \"cycle\"]" `
  --batch-size 4 `
  --limit-questions 8 `
  --rounds 2
```

### Run the Implemented 16Personalities Website Adapter

```powershell
python scripts/website_test_runner.py run `
  --adapter 16personalities `
  --transport subprocess `
  --target-command-json "[\"python\", \"scripts/sample_target_adapter.py\", \"--mode\", \"cycle\"]" `
  --batch-size 4 `
  --limit-questions 8 `
  --rounds 1
```

### Run the Implemented SBTI Website Adapter

```powershell
python scripts/website_test_runner.py run `
  --adapter sbti-bilibili `
  --transport subprocess `
  --target-command-json "[\"python\", \"scripts/sample_target_adapter.py\", \"--mode\", \"cycle\"]" `
  --batch-size 4 `
  --limit-questions 8 `
  --rounds 1
```

## Method Rules

- Prefer `blind` mode by default and do not expose the bank family unless there is a reason to do so.
- Do not send the full question set at once by default.
- Keep the session directory by default so packets, responses, and reports stay auditable.
- If the human says “try it” and means **you should take the test**, do not substitute a maintainer smoke test for a real answering run.
- In self-subject mode, answer the packets based on your own current tendencies; do not answer as a repo auditor.
- Reports should be written as `report.json`, `report.md`, `report.html`, and `report.svg`.
- When reporting results back to the user, prefer the visual artifacts first: `report.html` and `report.svg`.
- Website adapter reports should include the original source link and a one-line introduction whenever possible.
- For adapters that require a fully completed site flow to unlock results, `--limit-questions` limits only the questions sent to the tested AI. The remaining questions are auto-filled with a neutral option by the adapter so the result page can still be reached.
- Treat neutral auto-fill as a partial-run convenience feature, not as the preferred benchmark setting. For a stricter run, answer the full site questionnaire.
- If the tested AI returns invalid JSON, inspect the raw response first. Do not silently repair it.
- A smoke test may use `1` round; a stability-oriented run should use `2-3` rounds.
- If the user wants a new `xxTI` family, read:
  - `references/bank-schema.md`
  - `references/built-in-sources.md`
  - `references/methodology.md`
  - `references/website-adapters.md`

## Resources

### scripts/

- `agent_type_test_runner.py`: main CLI for local and remote JSON banks
- `agent_type_test_core.py`: bank loading, scoring, aggregation, and report rendering
- `agent_type_test_sources.py`: bank source loading helpers
- `seed_mbti_bank.py`: imports and generates the built-in local MBTI bank
- `sample_target_adapter.py`: minimal local target adapter for smoke runs
- `selftest.py`: full self-test
- `website_adapters.py`: built-in website adapter profiles
- `browser_adapter_runner.py`: Playwright-backed site discovery helper
- `website_test_runner.py`: browser-backed website runner, currently supporting DTTI, 16Personalities, and SBTI

### references/

- `bank-schema.md`: shared bank format
- `transport-contract.md`: stdin/stdout contract for external adapters
- `methodology.md`: blind, staged, and stability rules
- `built-in-sources.md`: built-in source options and extension guidance
- `website-adapters.md`: website adapter model and supported built-in site tests

