from __future__ import annotations

import argparse
import json
import subprocess
from typing import Any
import urllib.request


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
    parser.add_argument("--transport", choices=("manual", "subprocess", "openai-compatible"), default="manual")
    parser.add_argument(
        "--target-command-json",
        default=None,
        help='JSON string array for subprocess transport, for example ["python", "scripts/sample_target_adapter.py"]',
    )
    parser.add_argument("--base-url", default=None, help="Base URL for OpenAI-compatible API")
    parser.add_argument("--model", default=None, help="Model name for OpenAI-compatible transport")
    parser.add_argument("--api-key", default=None, help="API key for OpenAI-compatible transport")
    parser.add_argument("--timeout", type=int, default=60)


def validate_transport_args(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    if args.transport == "subprocess" and not args.target_command_json:
        parser.error("--target-command-json is required for subprocess transport")
    if args.transport == "openai-compatible":
        if not args.base_url or not args.model or not args.api_key:
            parser.error("--base-url, --model, and --api-key are required for openai-compatible transport")


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


def _openai_response(packet: dict[str, Any], base_url: str, model: str, api_key: str, timeout: int) -> Any:
    body = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": packet["prompt_text"],
            }
        ],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }
    request = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "Mozilla/5.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.load(response)
    content = payload["choices"][0]["message"]["content"]
    return extract_json_object(content)


def dispatch_transport(args: argparse.Namespace, packet: dict[str, Any]) -> Any:
    if args.transport == "manual":
        return _manual_response(packet)
    if args.transport == "subprocess":
        return _subprocess_response(packet, args.target_command_json, args.timeout)
    if args.transport == "openai-compatible":
        return _openai_response(packet, args.base_url, args.model, args.api_key, args.timeout)
    raise TransportError(f"unsupported transport: {args.transport}")
