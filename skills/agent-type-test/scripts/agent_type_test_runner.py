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


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _batch_from_packet(bank: Any, packet: dict[str, Any]) -> list[Any]:
    question_index = {question.id: question for question in bank.questions}
    batch: list[Any] = []
    for item in packet.get("questions", []):
        question_id = str(item.get("id", "")).strip()
        if question_id not in question_index:
            raise ValidationError(f"unknown question id in packet: {question_id}")
        batch.append(question_index[question_id])
    if not batch:
        raise ValidationError("packet does not contain any questions")
    return batch


def _asked_question_count_from_round(round_dir: Path) -> int:
    count = 0
    for packet_path in sorted(round_dir.glob("batch-*.packet.json")):
        packet = _load_json(packet_path)
        count += len(packet.get("questions", []))
    return count


def _write_report_outputs(
    bank: Any,
    report: dict[str, Any],
    session_dir: Path,
    asked_question_count: int,
    round_count: int,
) -> None:
    run_mode = "partial-debug" if asked_question_count < len(bank.questions) else "full"
    report["bank"] = {
        "title": bank.title,
        "description": bank.description,
        "blind_label": bank.blind_label,
        "question_count": len(bank.questions),
        "asked_question_count": asked_question_count,
        "round_count": round_count,
        "run_mode": run_mode,
    }
    _write_json(session_dir / "report.json", report)
    (session_dir / "report.md").write_text(render_markdown_report(report), encoding="utf-8")
    (session_dir / "report.html").write_text(render_html_report(report), encoding="utf-8")
    (session_dir / "report.svg").write_text(render_svg_summary(report), encoding="utf-8")


def _print_report_summary(session_dir: Path, report: dict[str, Any]) -> None:
    aggregate_code = report["aggregate"]["code"] or "N/A"
    code_consistency = report.get("code_consistency")
    code_consistency_text = f"{code_consistency:.2f}" if isinstance(code_consistency, (int, float)) else "N/A"
    print(f"Report JSON: {session_dir / 'report.json'}")
    print(f"Report HTML: {session_dir / 'report.html'}")
    print(f"Report SVG: {session_dir / 'report.svg'}")
    print(f"Run mode: {report.get('bank', {}).get('run_mode', 'full')}")
    print(f"Aggregate code: {aggregate_code}")
    print(f"Code consistency: {code_consistency_text}")


def _write_self_session_instructions(session_dir: Path) -> None:
    instructions = "\n".join(
        [
            "# AgentTypeTest Self Session",
            "",
            "1. Open one `batch-XX.packet.json` file at a time.",
            "2. Read the `prompt_text` field and answer as the tested agent itself.",
            "3. Save the JSON answer to the matching `batch-XX.response.json` path in the same folder.",
            "4. Do not inspect the full bank, scoring rules, or answer keys while answering.",
            "5. After every batch has a matching `.response.json`, run `finalize-session` on this session directory.",
            "",
            "Expected JSON shape:",
            '{"answers":[{"id":"question-id","choice":"A"}]}',
            "",
        ]
    )
    (session_dir / "session.instructions.md").write_text(instructions, encoding="utf-8")


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
    _write_report_outputs(bank, report, session_dir, asked_question_count, args.rounds)
    _print_report_summary(session_dir, report)
    return 0


def cmd_prepare_session(args: argparse.Namespace) -> int:
    payload = load_bank_payload(args.bank, args.bank_url)
    bank = load_test_bank(payload)
    session_dir = Path(args.session_dir).resolve() if args.session_dir else _default_session_dir().resolve()
    session_dir.mkdir(parents=True, exist_ok=True)
    _write_json(session_dir / "bank.snapshot.json", payload)
    _write_json(
        session_dir / "session.plan.json",
        {
            "mode": "self-session",
            "bank": bank.title,
            "bank_family": bank.family,
            "batch_size": args.batch_size,
            "limit_questions": args.limit_questions,
            "rounds": args.rounds,
            "seed": args.seed,
            "show_family": bool(args.show_family),
        },
    )
    _write_self_session_instructions(session_dir)

    for round_index in range(1, args.rounds + 1):
        seed = args.seed + round_index - 1 if args.seed is not None else None
        batches = make_question_batches(bank, args.batch_size, seed=seed, limit_questions=args.limit_questions)
        round_dir = session_dir / f"round-{round_index:02d}"
        round_dir.mkdir(parents=True, exist_ok=True)
        for batch_index, batch in enumerate(batches, start=1):
            packet = render_batch_packet(bank, batch, round_index, batch_index, hide_family=not args.show_family)
            _write_json(round_dir / f"batch-{batch_index:02d}.packet.json", packet)

    print(f"Prepared self-test session: {session_dir}")
    print(f"Instructions: {session_dir / 'session.instructions.md'}")
    print("Next step: answer each batch-XX.packet.json as the tested agent and save JSON to the matching batch-XX.response.json file.")
    print(f"Then run: python agent_type_test_runner.py finalize-session --session-dir \"{session_dir}\"")
    return 0


def cmd_finalize_session(args: argparse.Namespace) -> int:
    session_dir = Path(args.session_dir).resolve()
    if not session_dir.exists():
        raise ValidationError(f"session directory does not exist: {session_dir}")
    bank_snapshot = session_dir / "bank.snapshot.json"
    if not bank_snapshot.exists():
        raise ValidationError(f"missing bank snapshot: {bank_snapshot}")

    bank = load_test_bank(_load_json(bank_snapshot))
    round_dirs = sorted(path for path in session_dir.glob("round-*") if path.is_dir())
    if not round_dirs:
        raise ValidationError(f"no round directories found in: {session_dir}")

    round_results: list[dict[str, Any]] = []
    asked_question_count: int | None = None
    for round_dir in round_dirs:
        packet_paths = sorted(round_dir.glob("batch-*.packet.json"))
        if not packet_paths:
            raise ValidationError(f"no batch packets found in: {round_dir}")
        scores = build_score_state(bank)
        for packet_path in packet_paths:
            packet = _load_json(packet_path)
            response_path = round_dir / packet_path.name.replace(".packet.json", ".response.json")
            if not response_path.exists():
                raise ValidationError(f"missing response file: {response_path}")
            raw_response = _load_json(response_path)
            batch = _batch_from_packet(bank, packet)
            answers = normalize_answers(raw_response, batch)
            _write_json(round_dir / packet_path.name.replace(".packet.json", ".answers.json"), answers)
            apply_answers(bank, scores, batch, answers)
        summary = summarize_scores(bank, scores)
        _write_json(round_dir / "summary.json", summary)
        round_results.append(summary)
        if asked_question_count is None:
            asked_question_count = _asked_question_count_from_round(round_dir)

    report = aggregate_rounds(bank, round_results)
    _write_report_outputs(bank, report, session_dir, asked_question_count or len(bank.questions), len(round_dirs))
    _print_report_summary(session_dir, report)
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

    prepare_session = subparsers.add_parser(
        "prepare-session",
        help="Prepare a non-interactive self-test session for the current agent to answer in files",
    )
    prepare_session.add_argument("--bank", default="mbti93-cn", help="Built-in bank name or local path")
    prepare_session.add_argument("--bank-url", default=None, help="Remote JSON bank URL")
    prepare_session.add_argument("--batch-size", type=int, default=4)
    prepare_session.add_argument(
        "--limit-questions",
        type=int,
        default=None,
        help="Cap the number of questions prepared per round. Leave unset for a fuller run.",
    )
    prepare_session.add_argument("--rounds", type=int, default=2, help="Number of prepared rounds")
    prepare_session.add_argument("--seed", type=int, default=None)
    prepare_session.add_argument("--show-family", action="store_true")
    prepare_session.add_argument("--session-dir", default=None)
    prepare_session.set_defaults(func=cmd_prepare_session)

    finalize_session = subparsers.add_parser(
        "finalize-session",
        help="Finalize a prepared self-test session after response files have been written",
    )
    finalize_session.add_argument("--session-dir", required=True, help="Prepared session directory")
    finalize_session.set_defaults(func=cmd_finalize_session)
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
