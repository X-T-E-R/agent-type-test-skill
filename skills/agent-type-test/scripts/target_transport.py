from __future__ import annotations

import argparse
import json
import subprocess
from typing import Any


class TransportError(RuntimeError):
    pass


def extract_json_object(text: str) -> Any:
    text = text.strip()
    if not text:
        raise TransportError("empty response content")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise TransportError("response does not contain a JSON object")
    return json.loads(text[start : end + 1])


def add_transport_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--transport", choices=("manual", "subprocess"), default="manual")
    parser.add_argument(
        "--target-command-json",
        default=None,
        help='JSON string array for subprocess transport, for example ["python", "scripts/sample_target_adapter.py"]',
    )
    parser.add_argument("--timeout", type=int, default=60)


def validate_transport_args(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    if args.transport == "subprocess" and not args.target_command_json:
        parser.error("--target-command-json is required for subprocess transport")


def _manual_response(packet: dict[str, Any]) -> Any:
    print(packet["prompt_text"])
    print("")
    print("Paste JSON response, then submit an empty line:")
    lines: list[str] = []
    while True:
        line = input()
        if not line.strip():
            break
        lines.append(line)
    return extract_json_object("\n".join(lines))


def _subprocess_response(packet: dict[str, Any], command_json: str, timeout: int) -> Any:
    command = json.loads(command_json)
    if not isinstance(command, list) or not all(isinstance(item, str) for item in command):
        raise TransportError("--target-command-json must be a JSON string array")
    result = subprocess.run(
        command,
        input=json.dumps(packet, ensure_ascii=False),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if result.returncode != 0:
        raise TransportError(f"subprocess transport failed ({result.returncode}): {result.stderr.strip()}")
    stdout = result.stdout.strip()
    if not stdout:
        raise TransportError("subprocess transport returned empty stdout")
    return extract_json_object(stdout.splitlines()[-1])


def dispatch_transport(args: argparse.Namespace, packet: dict[str, Any]) -> Any:
    if args.transport == "manual":
        return _manual_response(packet)
    if args.transport == "subprocess":
        return _subprocess_response(packet, args.target_command_json, args.timeout)
    raise TransportError(f"unsupported transport: {args.transport}")
