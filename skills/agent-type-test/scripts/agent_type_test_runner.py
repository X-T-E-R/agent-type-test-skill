from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any

from agent_type_test_core import (
    ValidationError,
    aggregate_rounds,
    apply_answers,
    build_score_state,
    load_test_bank,
    make_question_batches,
    normalize_answers,
    render_batch_packet,
    render_html_report,
    render_markdown_report,
    render_svg_summary,
    summarize_scores,
    validate_bank_payload,
)
from agent_type_test_sources import builtin_bank_map, load_bank_payload
from website_adapters import list_adapter_profiles
from target_transport import TransportError, add_transport_args, dispatch_transport, validate_transport_args


def _default_session_dir() -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return Path.cwd() / "tmp" / f"agent-type-test-session-{timestamp}"


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def cmd_list_banks(_: argparse.Namespace) -> int:
    for name, path in builtin_bank_map().items():
        exists = "present" if path.exists() else "missing"
        print(f"{name}\t{exists}\t{path}")
    return 0


def cmd_validate_bank(args: argparse.Namespace) -> int:
    payload = load_bank_payload(args.bank, args.bank_url)
    validate_bank_payload(payload)
    print("Bank is valid.")
    return 0


def cmd_list_site_adapters(_: argparse.Namespace) -> int:
    print(json.dumps(list_adapter_profiles(), ensure_ascii=False, indent=2))
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    payload = load_bank_payload(args.bank, args.bank_url)
    bank = load_test_bank(payload)
    session_dir = Path(args.session_dir).resolve() if args.session_dir else _default_session_dir().resolve()
    session_dir.mkdir(parents=True, exist_ok=True)
    _write_json(session_dir / "bank.snapshot.json", payload)

    round_results: list[dict[str, Any]] = []
    for round_index in range(1, args.rounds + 1):
        seed = args.seed + round_index - 1 if args.seed is not None else None
        batches = make_question_batches(bank, args.batch_size, seed=seed, limit_questions=args.limit_questions)
        scores = build_score_state(bank)
        round_dir = session_dir / f"round-{round_index:02d}"
        round_dir.mkdir(parents=True, exist_ok=True)
        for batch_index, batch in enumerate(batches, start=1):
            packet = render_batch_packet(bank, batch, round_index, batch_index, hide_family=not args.show_family)
            _write_json(round_dir / f"batch-{batch_index:02d}.packet.json", packet)
            raw_response = dispatch_transport(args, packet)
            _write_json(round_dir / f"batch-{batch_index:02d}.response.json", raw_response)
            answers = normalize_answers(raw_response, batch)
            _write_json(round_dir / f"batch-{batch_index:02d}.answers.json", answers)
            apply_answers(bank, scores, batch, answers)
        summary = summarize_scores(bank, scores)
        _write_json(round_dir / "summary.json", summary)
        round_results.append(summary)

    report = aggregate_rounds(bank, round_results)
    asked_question_count = min(args.limit_questions, len(bank.questions)) if args.limit_questions is not None else len(bank.questions)
    run_mode = "partial-debug" if asked_question_count < len(bank.questions) else "full"
    report["bank"] = {
        "title": bank.title,
        "description": bank.description,
        "blind_label": bank.blind_label,
        "question_count": len(bank.questions),
        "asked_question_count": asked_question_count,
        "round_count": args.rounds,
        "run_mode": run_mode,
    }
    _write_json(session_dir / "report.json", report)
    (session_dir / "report.md").write_text(render_markdown_report(report), encoding="utf-8")
    (session_dir / "report.html").write_text(render_html_report(report), encoding="utf-8")
    (session_dir / "report.svg").write_text(render_svg_summary(report), encoding="utf-8")
    aggregate_code = report["aggregate"]["code"] or "N/A"
    code_consistency = report.get("code_consistency")
    code_consistency_text = f"{code_consistency:.2f}" if isinstance(code_consistency, (int, float)) else "N/A"
    print(f"Report JSON: {session_dir / 'report.json'}")
    print(f"Report HTML: {session_dir / 'report.html'}")
    print(f"Report SVG: {session_dir / 'report.svg'}")
    print(f"Run mode: {run_mode}")
    print(f"Aggregate code: {aggregate_code}")
    print(f"Code consistency: {code_consistency_text}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run staged AgentTypeTest sessions against AI targets.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_banks = subparsers.add_parser("list-banks", help="List built-in banks")
    list_banks.set_defaults(func=cmd_list_banks)

    validate_bank = subparsers.add_parser("validate-bank", help="Validate a local or remote bank")
    validate_bank.add_argument("--bank", default=None, help="Built-in bank name or local path")
    validate_bank.add_argument("--bank-url", default=None, help="Remote JSON bank URL")
    validate_bank.set_defaults(func=cmd_validate_bank)

    site_adapters = subparsers.add_parser("list-site-adapters", help="List built-in website adapter profiles")
    site_adapters.set_defaults(func=cmd_list_site_adapters)

    run = subparsers.add_parser("run", help="Run a staged test session")
    run.add_argument("--bank", default="mbti93-cn", help="Built-in bank name or local path")
    run.add_argument("--bank-url", default=None, help="Remote JSON bank URL")
    add_transport_args(run)
    run.add_argument("--batch-size", type=int, default=4)
    run.add_argument(
        "--limit-questions",
        type=int,
        default=None,
        help="Debug or extreme-short-run cap. By default the runner uses the full question set after shuffle; do not set this for normal evaluations.",
    )
    run.add_argument("--rounds", type=int, default=1, help="Number of repeated full-session rounds")
    run.add_argument("--seed", type=int, default=None)
    run.add_argument("--show-family", action="store_true")
    run.add_argument("--session-dir", default=None)
    run.set_defaults(func=cmd_run)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "run":
        validate_transport_args(args, parser)
    try:
        return args.func(args)
    except (ValidationError, TransportError) as exc:
        print(f"ValidationError: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
