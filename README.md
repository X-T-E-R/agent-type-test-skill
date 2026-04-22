# AgentTypeTest

![AgentTypeTest Orbit Core logo](./assets/branding/agent-type-test-orbit-core.svg)

[简体中文说明](./README.zh-CN.md)

> Run the test. Reveal the type.

AgentTypeTest is a Codex-style skill for running blind, staged, repeatable personality-style tests on AI agents. It hides the full bank, only sends the current batch, and leaves behind auditable packets, answers, and reports.

This repo is intentionally skill-first. It is not a standalone app or a clinical assessment tool. It is a reusable workflow for fun, comparable, inspectable agent personality runs.

## What It Does

- Runs local banks such as `mbti93-cn` and `mini-ipip-en`
- Runs website-backed adapters such as `16personalities`, `sbti-bilibili`, and `dtti`
- Supports `manual`, `subprocess`, and `openai-compatible` transports
- Produces deterministic `json`, `md`, `html`, and `svg` reports
- Keeps each round blind and staged instead of dumping the whole questionnaire into one prompt

## Real GPT-5.4 Examples

These screenshots and archived runs come from real GPT-5.4 sessions stored in this repository.

<table>
  <tr>
    <td width="50%">
      <a href="./examples/runs/16personalities-sample-cycle/report.html">
        <img src="./assets/screenshots/gpt-5.4-high-16personalities.png" alt="GPT-5.4 on 16Personalities" />
      </a>
      <br />
      <strong>16Personalities</strong><br />
      ENFP-T · Campaigner · full browser flow · 60 / 60 AI-answered
    </td>
    <td width="50%">
      <a href="./examples/runs/sbti-sample-cycle/report.html">
        <img src="./assets/screenshots/gpt-5.4-high-sbti.png" alt="GPT-5.4 on SBTI" />
      </a>
      <br />
      <strong>SBTI Bilibili</strong><br />
      LOVE-R（多情者） · avg match 73.0% · 31 / 31 AI-answered
    </td>
  </tr>
  <tr>
    <td width="50%">
      <a href="./examples/runs/dtti-sample-cycle/report.html">
        <img src="./assets/screenshots/gpt-5.4-medium-dtti.png" alt="GPT-5.4 on DTTI" />
      </a>
      <br />
      <strong>DTTI</strong><br />
      梅什金公爵 · profile consistency 1.00 · local scoring from extracted site data
    </td>
    <td width="50%">
      <a href="./examples/runs/mbti93-cn-sample-cycle/report.html">
        <img src="./assets/screenshots/gpt-5.4-medium-mbti93.png" alt="GPT-5.4 on MBTI93 local bank" />
      </a>
      <br />
      <strong>MBTI 93 (zh-CN)</strong><br />
      INF? · code consistency 1.00 · full local bank run
    </td>
  </tr>
</table>

Additional archived runs live under [`examples/runs/`](./examples/runs/).

## Repository Layout

```text
AgentTypeTest/
├─ assets/
│  ├─ branding/
│  └─ screenshots/
├─ docs/
│  ├─ research/
│  └─ superpowers/
│     ├─ plans/
│     └─ specs/
├─ examples/
│  └─ runs/
├─ skills/
│  └─ agent-type-test/
│     ├─ agents/
│     ├─ assets/
│     ├─ references/
│     ├─ scripts/
│     └─ SKILL.md
└─ tmp/
```

## Quick Start

### 1. Install dependencies

```powershell
pip install -r requirements.txt
python -m playwright install chromium
```

### 2. Run the self-test

```powershell
python skills/agent-type-test/scripts/selftest.py
```

### 3. Run a local bank

```powershell
python skills/agent-type-test/scripts/agent_type_test_runner.py run `
  --bank mbti93-cn `
  --transport subprocess `
  --target-command-json "[\"python\", \"skills/agent-type-test/scripts/sample_target_adapter.py\", \"--mode\", \"cycle\"]" `
  --batch-size 4 `
  --limit-questions 12 `
  --rounds 2 `
  --seed 42
```

### 4. Run a website adapter

```powershell
python skills/agent-type-test/scripts/website_test_runner.py run `
  --adapter 16personalities `
  --transport subprocess `
  --target-command-json "[\"python\", \"skills/agent-type-test/scripts/sample_target_adapter.py\", \"--mode\", \"cycle\"]" `
  --batch-size 4 `
  --limit-questions 8 `
  --rounds 1
```

## Skill Entry

The public skill entry lives at [`skills/agent-type-test/SKILL.md`](./skills/agent-type-test/SKILL.md).

Use it when you want to:

- test an agent with a hidden local bank
- replay the same test across multiple rounds
- compare local banks with live website adapters
- keep browser-backed results and packet-level artifacts for inspection

## Notes

- `tmp/` is intentionally kept as a local scratch directory and is ignored by git.
- Archived development runs now live in `examples/runs/` so the repo keeps working examples without mixing them into the scratch space.
- This project does not try to be a generic “chat to any MCP model” bridge. The stable integration point is still the transport layer.
- Website adapters are practical and fun, but more brittle than local banks because upstream pages can change.

## License

This repository is released under [GPL-3.0](./LICENSE).

Bundled and candidate test sources can have their own provenance or reuse constraints. Check:

- [skills/agent-type-test/references/built-in-sources.md](./skills/agent-type-test/references/built-in-sources.md)
- [docs/research/2026-04-22-bank-candidates.md](./docs/research/2026-04-22-bank-candidates.md)
