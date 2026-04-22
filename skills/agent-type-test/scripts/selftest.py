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
        print(f"AgentTypeTest selftest passed. Report: {report_path}")
        print(f"Aggregate code: {aggregate_code}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
