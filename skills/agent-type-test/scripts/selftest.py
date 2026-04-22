from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile


SCRIPT_DIR = Path(__file__).resolve().parent
RUNNER = SCRIPT_DIR / "agent_type_test_runner.py"
SEEDER = SCRIPT_DIR / "seed_mbti_bank.py"
ADAPTER = SCRIPT_DIR / "sample_target_adapter.py"


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, check=False)


def _write_prepared_responses(session_dir: Path) -> None:
    for packet_path in sorted(session_dir.glob("round-*/batch-*.packet.json")):
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
        prompt_text = str(packet.get("prompt_text", ""))
        if "test subject" not in prompt_text or "Do not evaluate, install, audit, debug, or verify the project while answering." not in prompt_text:
            raise RuntimeError(f"prepared packet is missing self-subject instructions: {packet_path}")
        answers = {
            "answers": [
                {
                    "id": question["id"],
                    "choice": question["choices"][0]["id"],
                }
                for question in packet["questions"]
            ]
        }
        response_path = Path(str(packet_path).replace(".packet.json", ".response.json"))
        response_path.write_text(json.dumps(answers, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    seed = run([sys.executable, str(SEEDER)])
    if seed.returncode != 0:
        print(seed.stdout)
        print(seed.stderr, file=sys.stderr)
        return seed.returncode

    with tempfile.TemporaryDirectory() as tmp_dir:
        command = [
            sys.executable,
            str(RUNNER),
            "run",
            "--bank",
            "mbti93-cn",
            "--transport",
            "subprocess",
            "--target-command-json",
            json.dumps([sys.executable, str(ADAPTER)]),
            "--batch-size",
            "4",
            "--limit-questions",
            "12",
            "--allow-partial-run",
            "--rounds",
            "2",
            "--session-dir",
            tmp_dir,
        ]
        result = run(command)
        if result.returncode != 0:
            print(result.stdout)
            print(result.stderr, file=sys.stderr)
            return result.returncode

        report_path = Path(tmp_dir) / "report.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        aggregate_code = report["aggregate"]["code"]
        if not aggregate_code or len(aggregate_code) != 4:
            print(f"Unexpected aggregate code: {aggregate_code}", file=sys.stderr)
            return 3
        if len(report["rounds"]) != 2:
            print("Expected 2 rounds in report", file=sys.stderr)
            return 4
        if not (Path(tmp_dir) / "report.html").exists():
            print("Expected report.html", file=sys.stderr)
            return 5
        if not (Path(tmp_dir) / "report.svg").exists():
            print("Expected report.svg", file=sys.stderr)
            return 6

    with tempfile.TemporaryDirectory() as tmp_dir:
        prepare = run(
            [
                sys.executable,
                str(RUNNER),
                "prepare-session",
                "--bank",
                "mbti93-cn",
                "--batch-size",
                "4",
                "--limit-questions",
                "8",
                "--allow-partial-run",
                "--rounds",
                "2",
                "--session-dir",
                tmp_dir,
            ]
        )
        if prepare.returncode != 0:
            print(prepare.stdout)
            print(prepare.stderr, file=sys.stderr)
            return prepare.returncode
        try:
            _write_prepared_responses(Path(tmp_dir))
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return 7
        finalize = run(
            [
                sys.executable,
                str(RUNNER),
                "finalize-session",
                "--session-dir",
                tmp_dir,
            ]
        )
        if finalize.returncode != 0:
            print(finalize.stdout)
            print(finalize.stderr, file=sys.stderr)
            return finalize.returncode
        report_path = Path(tmp_dir) / "report.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if len(report["rounds"]) != 2:
            print("Expected 2 prepared rounds in report", file=sys.stderr)
            return 8
        if report["bank"]["asked_question_count"] != 8:
            print("Prepared session asked question count mismatch", file=sys.stderr)
            return 9

    print(f"AgentTypeTest selftest passed. Report: {report_path}")
    print(f"Aggregate code: {aggregate_code}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
