from __future__ import annotations

import argparse
from pathlib import Path

from agent_type_test_sources import builtin_bank_map, seed_mbti_bank


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Seed the built-in MBTI 93 bank.")
    parser.add_argument("--output", default=None, help="Optional output path")
    parser.add_argument("--force", action="store_true", help="Overwrite existing file")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    default_output = builtin_bank_map()["mbti93-cn"]
    output_path = Path(args.output).resolve() if args.output else default_output
    if output_path.exists() and not args.force:
        print(f"Bank already exists: {output_path}")
        print("Use --force to refresh it.")
        return 0
    final_path = seed_mbti_bank(output_path)
    print(f"Seeded MBTI bank: {final_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
