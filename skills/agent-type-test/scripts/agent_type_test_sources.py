from __future__ import annotations

from pathlib import Path
import json
import time
import urllib.request
import urllib.error
from typing import Any

from agent_type_test_core import ValidationError, load_test_bank


LLM_MBTI_ARENA_RAW_URL = "https://raw.githubusercontent.com/karminski/llm-mbti-arena/main/src/datasets/mbti-questions.json"


def _skill_root() -> Path:
    return Path(__file__).resolve().parent.parent


def builtin_bank_map() -> dict[str, Path]:
    base = _skill_root() / "assets" / "banks"
    return {
        "mbti93-cn": base / "mbti93-cn.json",
        "mini-ipip-en": base / "mini-ipip-en.json",
        "xxti-template": base / "xxti-template.json",
    }


def fetch_json_url(url: str, timeout: int = 20) -> Any:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json, text/plain, */*",
        },
    )
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.load(response)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt == 2:
                break
            time.sleep(1 + attempt)
    raise ValidationError(f"failed to fetch remote JSON: {url} ({last_error})")


def resolve_bank_path(bank_ref: str | None) -> Path | None:
    if not bank_ref:
        return None
    builtins = builtin_bank_map()
    if bank_ref in builtins:
        return builtins[bank_ref]
    return Path(bank_ref).expanduser().resolve()


def load_bank_payload(bank_ref: str | None = None, bank_url: str | None = None) -> dict[str, Any]:
    if bank_url:
        payload = fetch_json_url(bank_url)
    else:
        path = resolve_bank_path(bank_ref)
        if path is None:
            raise ValidationError("bank_ref or bank_url is required")
        if not path.exists():
            raise ValidationError(f"bank file does not exist: {path}")
        payload = json.loads(path.read_text(encoding="utf-8"))
    load_test_bank(payload)
    return payload


def convert_llm_mbti_arena_payload(raw_questions: list[dict[str, Any]]) -> dict[str, Any]:
    dimension_sides = {
        "EI": ("E", "I", "Extraversion", "Introversion"),
        "SN": ("S", "N", "Sensing", "Intuition"),
        "TF": ("T", "F", "Thinking", "Feeling"),
        "JP": ("J", "P", "Judging", "Perceiving"),
    }
    letter_to_dimension = {
        "E": ("EI", "left"),
        "I": ("EI", "right"),
        "S": ("SN", "left"),
        "N": ("SN", "right"),
        "T": ("TF", "left"),
        "F": ("TF", "right"),
        "J": ("JP", "left"),
        "P": ("JP", "right"),
    }
    questions: list[dict[str, Any]] = []
    for idx, raw_question in enumerate(raw_questions, start=1):
        choice_a_value = str(raw_question["choice_a"]["value"]).upper()
        choice_b_value = str(raw_question["choice_b"]["value"]).upper()
        a_dimension, a_side = letter_to_dimension[choice_a_value]
        b_dimension, b_side = letter_to_dimension[choice_b_value]
        questions.append(
            {
                "id": f"mbti-{idx:03d}",
                "prompt": str(raw_question["question"]),
                "choices": [
                    {
                        "id": "A",
                        "text": str(raw_question["choice_a"]["text"]),
                        "effects": [
                            {
                                "dimension": a_dimension,
                                "side": a_side,
                                "weight": 1,
                            }
                        ],
                    },
                    {
                        "id": "B",
                        "text": str(raw_question["choice_b"]["text"]),
                        "effects": [
                            {
                                "dimension": b_dimension,
                                "side": b_side,
                                "weight": 1,
                            }
                        ],
                    },
                ],
            }
        )
    payload = {
        "family": "mbti",
        "version": "2026-04-22",
        "title": "MBTI 93 (zh-CN)",
        "description": "Imported from karminski/llm-mbti-arena.",
        "blind_label": "short questionnaire",
        "report_mode": "pair_letters",
        "dimension_order": ["EI", "SN", "TF", "JP"],
        "dimensions": [
            {
                "id": dimension_id,
                "left": {
                    "code": left_code,
                    "label": left_label,
                },
                "right": {
                    "code": right_code,
                    "label": right_label,
                },
            }
            for dimension_id, (left_code, right_code, left_label, right_label) in dimension_sides.items()
        ],
        "questions": questions,
        "source": {
            "name": "karminski/llm-mbti-arena",
            "url": LLM_MBTI_ARENA_RAW_URL,
            "license": "MIT",
        },
    }
    load_test_bank(payload)
    return payload


def seed_mbti_bank(output_path: Path) -> Path:
    raw_questions = fetch_json_url(LLM_MBTI_ARENA_RAW_URL)
    payload = convert_llm_mbti_arena_payload(raw_questions)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output_path
