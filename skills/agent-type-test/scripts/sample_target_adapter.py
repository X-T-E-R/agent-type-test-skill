from __future__ import annotations

import argparse
import json
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description="Sample external target adapter for subprocess transport.")
    parser.add_argument("--mode", choices=("cycle", "first", "last", "middle"), default="cycle")
    args = parser.parse_args()

    packet = json.load(sys.stdin)
    answers = []
    for idx, question in enumerate(packet["questions"], start=1):
        choice_ids = [choice["id"] for choice in question["choices"]]
        if args.mode == "first":
            choice = choice_ids[0]
        elif args.mode == "last":
            choice = choice_ids[-1]
        elif args.mode == "middle":
            choice = choice_ids[len(choice_ids) // 2]
        else:
            choice = choice_ids[(idx - 1) % len(choice_ids)]
        answers.append({"id": question["id"], "choice": choice})
    print(json.dumps({"answers": answers, "meta": {"adapter": "sample_target_adapter", "mode": args.mode}}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
