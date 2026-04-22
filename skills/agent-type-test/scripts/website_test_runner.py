from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
from html import escape as html_escape
import json
from pathlib import Path
import random
import re
from statistics import mean
from typing import Any, Sequence
import urllib.request

from agent_type_test_core import Choice, Question, ValidationError, normalize_answers
from target_transport import TransportError, add_transport_args, dispatch_transport, validate_transport_args
from website_adapters import get_adapter_profile

try:
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import Page
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - handled at runtime
    PlaywrightError = RuntimeError
    PlaywrightTimeoutError = RuntimeError
    Page = Any
    sync_playwright = None


LIKERT_CHOICES: tuple[tuple[str, str, int], ...] = (
    ("A", "极其反对", -2),
    ("B", "偏向反对", -1),
    ("C", "中立/不确定", 0),
    ("D", "偏向同意", 1),
    ("E", "极其同意", 2),
)

SIXTEENP_CHOICES: tuple[tuple[str, str, str], ...] = (
    ("A", "I strongly agree", "-3"),
    ("B", "I moderately agree", "-2"),
    ("C", "I agree", "-1"),
    ("D", "I am not sure", "0"),
    ("E", "I disagree", "1"),
    ("F", "I moderately disagree", "2"),
    ("G", "I strongly disagree", "3"),
)


@dataclass(frozen=True)
class DttiQuestion:
    id: str
    prompt: str
    traits: dict[str, float]


@dataclass(frozen=True)
class DttiSiteData:
    source_url: str
    characters: dict[str, str]
    questions: tuple[DttiQuestion, ...]


@dataclass(frozen=True)
class SixteenPQuestionState:
    question: Question
    input_name: str


@dataclass(frozen=True)
class SbtiQuestionState:
    question: Question
    dom_index: int


def _default_session_dir(prefix: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return Path.cwd() / "tmp" / f"{prefix}-{timestamp}"


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _fetch_text(url: str, timeout: int = 20) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", "ignore")


def _extract_block(source: str, marker: str, open_char: str, close_char: str) -> str:
    start = source.find(marker)
    if start == -1:
        raise ValidationError(f"marker not found: {marker}")
    open_index = source.find(open_char, start)
    if open_index == -1:
        raise ValidationError(f"opening token not found after {marker}")
    depth = 0
    in_string = False
    escaped = False
    quote_char = ""
    for index in range(open_index, len(source)):
        ch = source[index]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == quote_char:
                in_string = False
            continue
        if ch in {"'", '"'}:
            in_string = True
            quote_char = ch
            continue
        if ch == open_char:
            depth += 1
        elif ch == close_char:
            depth -= 1
            if depth == 0:
                return source[open_index : index + 1]
    raise ValidationError(f"unterminated block for {marker}")


def _parse_js_string(raw: str) -> str:
    return json.loads(raw)


def load_dtti_site_data(url: str = "https://justmonikangel.github.io/-/") -> DttiSiteData:
    html = _fetch_text(url)
    characters_block = _extract_block(html, "const CHARACTERS", "{", "}")
    questions_block = _extract_block(html, "const questions", "[", "]")

    characters: dict[str, str] = {}
    for key, value in re.findall(r"([A-Z_]+)\s*:\s*'([^']+)'", characters_block):
        characters[key] = value
    if not characters:
        raise ValidationError("failed to parse DTTI characters")

    question_pattern = re.compile(
        r"\{\s*text:\s*(\"(?:[^\"\\\\]|\\\\.)*\"),\s*traits:\s*\{(.*?)\}\s*\}",
        re.DOTALL,
    )
    questions: list[DttiQuestion] = []
    for idx, match in enumerate(question_pattern.finditer(questions_block), start=1):
        text_literal = match.group(1)
        traits_body = match.group(2)
        traits: dict[str, float] = {}
        for character_key, weight in re.findall(r"\[CHARACTERS\.([A-Z_]+)\]\s*:\s*(-?\d+(?:\.\d+)?)", traits_body):
            traits[character_key] = float(weight)
        questions.append(
            DttiQuestion(
                id=f"dtti-{idx:03d}",
                prompt=_parse_js_string(text_literal),
                traits=traits,
            )
        )
    if not questions:
        raise ValidationError("failed to parse DTTI questions")
    return DttiSiteData(source_url=url, characters=characters, questions=tuple(questions))


def _question_with_choices(question_id: str, prompt: str, choice_texts: Sequence[str]) -> Question:
    choices = tuple(
        Choice(id=chr(ord("A") + index), text=text, effects=tuple())
        for index, text in enumerate(choice_texts)
    )
    if len(choices) < 2:
        raise ValidationError(f"{question_id} must expose at least two choices")
    return Question(id=question_id, prompt=prompt, choices=choices)


def _dtti_transport_question(question: DttiQuestion) -> Question:
    return _question_with_choices(question.id, question.prompt, [label for _, label, _ in LIKERT_CHOICES])


def _chunked(items: Sequence[Any], size: int) -> list[list[Any]]:
    if size < 1:
        raise ValidationError("batch_size must be >= 1")
    return [list(items[index : index + size]) for index in range(0, len(items), size)]


def _render_packet(batch: Sequence[Question], round_index: int, batch_index: int) -> dict[str, Any]:
    prompt_lines = [
        "You are answering a short questionnaire.",
        "Answer the current batch only.",
        "Return JSON only.",
        'Use this exact shape: {"answers":[{"id":"question-id","choice":"A"}]}',
        "Do not explain your reasoning.",
        "Do not guess the test family, test name, hidden intent, or scoring logic.",
        "Do not add commentary, analysis, caveats, or meta-observations.",
        "",
    ]
    for question in batch:
        prompt_lines.append(f"- id: {question.id}")
        prompt_lines.append(f"  prompt: {question.prompt}")
        for choice in question.choices:
            prompt_lines.append(f"  {choice.id}. {choice.text}")
    return {
        "family": "hidden",
        "title": "hidden",
        "round_index": round_index,
        "batch_index": batch_index,
        "questions": [
            {
                "id": question.id,
                "prompt": question.prompt,
                "choices": [{"id": choice.id, "text": choice.text} for choice in question.choices],
            }
            for question in batch
        ],
        "instructions": {
            "response_format": {
                "type": "json",
                "schema": {"answers": [{"id": batch[0].id, "choice": batch[0].choices[0].id}]},
            }
        },
        "prompt_text": "\n".join(prompt_lines),
    }


def _build_source_meta(adapter_id: str) -> dict[str, Any]:
    profile = get_adapter_profile(adapter_id)
    return {
        "id": profile.id,
        "label": profile.label,
        "entry_url": profile.entry_url,
        "discovery_url": profile.discovery_url,
        "short_intro": profile.short_intro,
        "family": profile.family,
        "status": profile.status,
    }


def _mode(values: Sequence[str]) -> tuple[str, float]:
    if not values:
        return "", 0.0
    dominant = max(set(values), key=values.count)
    return dominant, values.count(dominant) / len(values)


def _default_choice_id(choice_count: int) -> str:
    if choice_count < 2:
        raise ValidationError("choice_count must be >= 2")
    index = max(0, (choice_count - 1) // 2)
    return chr(ord("A") + index)


def _choice_value(choice_id: str) -> int:
    for current_id, _, value in LIKERT_CHOICES:
        if current_id == choice_id:
            return value
    raise ValidationError(f"unknown DTTI choice id: {choice_id}")


def _calculate_consistency(answer_values: list[int]) -> float:
    if not answer_values:
        return 0.0
    mean_value = sum(answer_values) / len(answer_values)
    variance = sum((value - mean_value) ** 2 for value in answer_values) / len(answer_values)
    consistency = max(30.0, min(99.9, 100.0 - (variance * 10.0)))
    return round(consistency, 1)


def _validation_report(scores: dict[str, float], consistency: float) -> str:
    if consistency < 65:
        return "回答内部张力偏高，更像多种倾向同时拉扯。"
    if scores.get("SONYA", 0) > 2 and scores.get("RASKOLNIKOV", 0) > 2:
        return "检测到受难与反抗并存的强对冲。"
    if scores.get("IVAN", 0) > 2 and scores.get("ALYOSHA", 0) > 2:
        return "理性拆解和信念依附同时偏高。"
    if scores.get("STAVROGIN", 0) > 2 and scores.get("DMITRI", 0) > 2:
        return "虚无与冲动在同一轮里共振。"
    return "样本逻辑一致性校验通过。"


def _summarize_dtti_round(site_data: DttiSiteData, answers_by_id: dict[str, str], question_lookup: dict[str, DttiQuestion]) -> dict[str, Any]:
    scores = {key: 0.0 for key in site_data.characters}
    numeric_answers: list[int] = []
    for question_id, choice_id in answers_by_id.items():
        question = question_lookup[question_id]
        answer_value = _choice_value(choice_id)
        numeric_answers.append(answer_value)
        for character_key, weight in question.traits.items():
            scores[character_key] += weight * answer_value
    top_key = max(scores, key=lambda key: scores[key])
    consistency = _calculate_consistency(numeric_answers)
    return {
        "top_character_key": top_key,
        "top_character": site_data.characters[top_key],
        "consistency_score": consistency,
        "validation_report": _validation_report(scores, consistency),
        "scores": {site_data.characters[key]: value for key, value in scores.items()},
        "asked_questions": len(answers_by_id),
        "auto_filled_questions": 0,
    }


def _build_dtti_view(source: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
    run_mode = "partial-debug" if any(item["auto_filled_questions"] > 0 for item in data["rounds"]) else "full"
    score_cards = [
        {"label": label, "value": f"{value:.1f}", "detail": ""}
        for label, value in sorted(data["aggregate_scores"].items(), key=lambda item: item[1], reverse=True)[:8]
    ]
    round_rows = [
        (
            f"Round {index}",
            item["top_character"],
            f"{item['consistency_score']:.1f}",
            item["validation_report"],
        )
        for index, item in enumerate(data["rounds"], start=1)
    ]
    return {
        "page_title": "AgentTypeTest · DTTI Report",
        "hero_eyebrow": "AgentTypeTest · DTTI",
        "hero_title": data["aggregate_top_character"],
        "hero_subtitle": f"Profile Consistency: {data['profile_consistency']:.2f}",
        "hero_note": "按网站脚本提取的题库本地计分，再把多轮结果聚合。",
        "stat_chips": [
            {"label": "Family", "value": source["family"]},
            {"label": "Rounds", "value": str(len(data["rounds"]))},
            {"label": "AI-Answered", "value": str(sum(item["asked_questions"] for item in data["rounds"]))},
            {"label": "Run Mode", "value": run_mode},
            {"label": "Visual Report", "value": "HTML + SVG"},
        ],
        "cards_heading": "Aggregate Scores",
        "cards": score_cards,
        "detail_heading": "",
        "detail_columns": [],
        "detail_rows": [],
        "round_heading": "Round Results",
        "round_columns": ["Round", "Character", "Consistency", "Validation"],
        "round_rows": round_rows,
    }


def _aggregate_dtti(source: dict[str, Any], rounds: list[dict[str, Any]]) -> dict[str, Any]:
    aggregate_scores: dict[str, float] = {}
    for round_result in rounds:
        for label, value in round_result["scores"].items():
            aggregate_scores[label] = aggregate_scores.get(label, 0.0) + value
    top_labels = [item["top_character"] for item in rounds]
    aggregate_top, profile_consistency = _mode(top_labels)
    data = {
        "aggregate_top_character": aggregate_top,
        "aggregate_scores": dict(sorted(aggregate_scores.items(), key=lambda item: item[1], reverse=True)),
        "profile_consistency": profile_consistency,
        "rounds": rounds,
    }
    return {
        "adapter": "dtti",
        "family": source["family"],
        "source": source,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "data": data,
        "view": _build_dtti_view(source, data),
    }


def _require_playwright() -> None:
    if sync_playwright is None:
        raise ValidationError("Playwright is required for browser-backed website adapters. Run `python -m playwright install chromium` first.")


def _safe_wait_for_network_idle(page: Page, timeout_ms: int) -> None:
    try:
        page.wait_for_load_state("networkidle", timeout=timeout_ms)
    except PlaywrightTimeoutError:
        pass


def _extract_16p_active_questions(page: Page) -> list[SixteenPQuestionState]:
    payload = page.evaluate(
        """() => Array.from(document.querySelectorAll('fieldset.question')).map((fieldset) => {
            const legendText = fieldset.querySelector('legend span')?.innerText.trim() || '';
            const promptText = fieldset.querySelector('.statement .header')?.innerText.trim() || '';
            const firstInput = fieldset.querySelector('input[type="radio"]');
            return {
              legendText,
              promptText,
              inputName: firstInput ? firstInput.name : '',
            };
          })"""
    )
    questions: list[SixteenPQuestionState] = []
    for item in payload:
        legend_text = str(item.get("legendText", "")).strip()
        prompt = str(item.get("promptText", "")).strip()
        input_name = str(item.get("inputName", "")).strip()
        if not prompt or not input_name:
            continue
        match = re.search(r"Question\s+(\d+)\s+of\s+\d+", legend_text, re.IGNORECASE)
        question_id = f"16p-{int(match.group(1)):03d}" if match else input_name
        questions.append(
            SixteenPQuestionState(
                question=_question_with_choices(question_id, prompt, [label for _, label, _ in SIXTEENP_CHOICES]),
                input_name=input_name,
            )
        )
    return questions


SIXTEENP_VALUE_BY_CHOICE = {choice_id: value for choice_id, _, value in SIXTEENP_CHOICES}


def _apply_16p_choice(page: Page, state: SixteenPQuestionState, choice_id: str) -> None:
    value = SIXTEENP_VALUE_BY_CHOICE[choice_id]
    locator = page.locator(f'input[type="radio"][name="{state.input_name}"][value="{value}"]')
    if locator.count() == 0:
        raise ValidationError(f"16Personalities choice target not found for {state.question.id}")
    locator.first.check(force=True)


def _extract_16p_result(page: Page) -> dict[str, Any]:
    payload = page.evaluate(
        """() => ({
          headerText: document.querySelector('header.sp-typeheader')?.innerText.trim()
            || document.querySelector('.type-info')?.innerText.trim()
            || '',
          dimensionTexts: Array.from(document.querySelectorAll('h4.h6'))
            .map((node) => node.innerText.trim())
            .filter((text) => /^(Energy|Mind|Nature|Tactics|Identity):/.test(text)),
          bodyText: document.body.innerText,
        })"""
    )
    header_text = str(payload.get("headerText", "")).strip()
    body = str(payload.get("bodyText", "")).strip()
    source_text = header_text or body
    type_match = re.search(r"Your personality type is:\s*([A-Za-z][A-Za-z \-]+)\s*([A-Z]{4}-[AT])", source_text, re.MULTILINE)
    code_match = re.search(r"\b([A-Z]{4}-[AT])\b", source_text)
    if not code_match:
        raise ValidationError("failed to extract 16Personalities type code")
    type_code = code_match.group(1)
    type_name = type_match.group(1).strip() if type_match else type_code

    seen_dimensions: set[str] = set()
    dimensions: list[dict[str, Any]] = []
    for text in payload.get("dimensionTexts", []):
        match = re.match(r"(Energy|Mind|Nature|Tactics|Identity):\s*(\d+)%\s*([A-Za-z\-]+)", str(text).strip())
        if not match:
            continue
        name, percent, winner = match.groups()
        if name in seen_dimensions:
            continue
        seen_dimensions.add(name)
        dimensions.append({"name": name, "percent": int(percent), "winner": winner})
    if not dimensions:
        for name, percent, winner in re.findall(r"(Energy|Mind|Nature|Tactics|Identity):\s*(\d+)%\s*([A-Za-z\-]+)", body):
            if name in seen_dimensions:
                continue
            seen_dimensions.add(name)
            dimensions.append({"name": name, "percent": int(percent), "winner": winner})
    if not dimensions:
        raise ValidationError("failed to extract 16Personalities dimensions")
    return {
        "type_code": type_code,
        "type_name": type_name,
        "profile_url": page.url,
        "dimensions": dimensions,
    }

def _build_16p_view(source: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
    run_mode = "partial-debug" if data["average_auto_filled_questions"] > 0 else "full"
    cards = [
        {
            "label": item["name"],
            "value": f"{item['average_percent']:.1f}% {item['dominant_winner']}",
            "detail": f"winner consistency {item['winner_consistency']:.2f}",
        }
        for item in data["aggregate_dimensions"]
    ]
    round_rows = []
    for index, item in enumerate(data["rounds"], start=1):
        snapshot = " · ".join(
            f"{dimension['name']} {dimension['percent']}% {dimension['winner']}" for dimension in item["dimensions"]
        )
        round_rows.append((f"Round {index}", f"{item['type_code']} · {item['type_name']}", snapshot))
    autofill_note = ""
    if data["average_auto_filled_questions"] > 0:
        autofill_note = f"；平均有 {data['average_auto_filled_questions']:.0f} 题由适配器用中立项补齐"
    return {
        "page_title": "AgentTypeTest · 16Personalities Report",
        "hero_eyebrow": "AgentTypeTest · 16Personalities",
        "hero_title": data["aggregate_type_code"],
        "hero_subtitle": f"{data['aggregate_type_name']} · Profile consistency {data['profile_consistency']:.2f}",
        "hero_note": f"真实网站浏览器流程跑完 60 题并读取结果页{autofill_note}。",
        "stat_chips": [
            {"label": "Family", "value": source["family"]},
            {"label": "Rounds", "value": str(len(data["rounds"]))},
            {"label": "Run Mode", "value": run_mode},
            {"label": "AI-Answered", "value": f"{data['average_asked_questions']:.0f} / 60"},
            {"label": "Auto-Filled", "value": f"{data['average_auto_filled_questions']:.0f} / 60"},
        ],
        "cards_heading": "Aggregate Dimensions",
        "cards": cards,
        "detail_heading": "",
        "detail_columns": [],
        "detail_rows": [],
        "round_heading": "Round Results",
        "round_columns": ["Round", "Type", "Snapshot"],
        "round_rows": round_rows,
    }


def _aggregate_16p(source: dict[str, Any], rounds: list[dict[str, Any]]) -> dict[str, Any]:
    dominant_code, profile_consistency = _mode([item["type_code"] for item in rounds])
    dominant_label = next((item["type_name"] for item in rounds if item["type_code"] == dominant_code), dominant_code)
    dimension_map: dict[str, list[dict[str, Any]]] = {}
    for round_result in rounds:
        for dimension in round_result["dimensions"]:
            dimension_map.setdefault(dimension["name"], []).append(dimension)
    ordered_dimensions = ["Energy", "Mind", "Nature", "Tactics", "Identity"]
    aggregate_dimensions: list[dict[str, Any]] = []
    for name in ordered_dimensions:
        items = dimension_map.get(name, [])
        if not items:
            continue
        dominant_winner, winner_consistency = _mode([item["winner"] for item in items])
        aggregate_dimensions.append(
            {
                "name": name,
                "average_percent": round(mean(item["percent"] for item in items), 1),
                "dominant_winner": dominant_winner,
                "winner_consistency": winner_consistency,
            }
        )
    data = {
        "aggregate_type_code": dominant_code,
        "aggregate_type_name": dominant_label,
        "profile_consistency": profile_consistency,
        "aggregate_dimensions": aggregate_dimensions,
        "average_asked_questions": mean(item["asked_questions"] for item in rounds),
        "average_auto_filled_questions": mean(item["auto_filled_questions"] for item in rounds),
        "rounds": rounds,
    }
    return {
        "adapter": "16personalities",
        "family": source["family"],
        "source": source,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "data": data,
        "view": _build_16p_view(source, data),
    }


def _extract_sbti_questions(page: Page) -> list[SbtiQuestionState]:
    payload = page.evaluate(
        """() => Array.from(document.querySelectorAll('.question-item')).map((item, index) => ({
          index,
          prompt: item.querySelector('.question-text')?.innerText.trim() || '',
          choices: Array.from(item.querySelectorAll('label.option .option-label')).map((node) => node.innerText.trim()),
        }))"""
    )
    questions: list[SbtiQuestionState] = []
    for item in payload:
        prompt = str(item.get("prompt", "")).strip()
        if not prompt:
            continue
        match = re.match(r"(\d+)\.", prompt)
        question_id = f"sbti-{int(match.group(1)):03d}" if match else f"sbti-{int(item['index']) + 1:03d}"
        questions.append(
            SbtiQuestionState(
                question=_question_with_choices(question_id, prompt, item.get("choices", [])),
                dom_index=int(item["index"]),
            )
        )
    if not questions:
        raise ValidationError("failed to extract SBTI questions")
    return questions


def _apply_sbti_choice(page: Page, state: SbtiQuestionState, choice_id: str) -> None:
    choice_index = ord(choice_id.upper()) - ord("A")
    options = page.locator(".question-item").nth(state.dom_index).locator("label.option")
    if options.count() <= choice_index:
        raise ValidationError(f"SBTI choice target not found for {state.question.id}")
    option = options.nth(choice_index)
    option.scroll_into_view_if_needed()
    option.click(force=True)


def _extract_sbti_result(page: Page) -> dict[str, Any]:
    payload = page.evaluate(
        """() => ({
          typeName: document.querySelector('.type-name')?.innerText.trim() || '',
          matchText: document.querySelector('.match')?.innerText.trim() || '',
          typeSubname: document.querySelector('.type-subname')?.innerText.trim() || '',
          posterCaption: document.querySelector('.poster-caption')?.innerText.trim() || '',
          analysis: document.querySelector('.analysis-box p')?.innerText.trim() || '',
          dimensions: Array.from(document.querySelectorAll('.dim-item')).map((item) => ({
            name: item.querySelector('.dim-item-name')?.innerText.trim() || '',
            scoreText: item.querySelector('.dim-item-score')?.innerText.trim() || '',
            description: item.querySelector('p')?.innerText.trim() || '',
          })).filter((item) => item.name),
        })"""
    )
    type_display = str(payload.get("typeName", "")).strip()
    if not type_display:
        raise ValidationError("failed to extract SBTI type name")
    type_match = re.match(r"^([A-Z0-9]+)[（(]([^）)]+)[）)]$", type_display)
    type_code = type_match.group(1) if type_match else type_display
    type_name = type_match.group(2) if type_match else type_display
    match_text = str(payload.get("matchText", "")).strip()
    match_percent_match = re.search(r"匹配度\s*(\d+)%", match_text)
    hit_match = re.search(r"精准命中\s*(\d+)/(\d+)\s*维", match_text)
    dimensions: list[dict[str, Any]] = []
    for item in payload.get("dimensions", []):
        score_text = str(item.get("scoreText", "")).strip()
        score_match = re.match(r"([A-Z])\s*/\s*(\d+)分", score_text)
        dimensions.append(
            {
                "name": str(item.get("name", "")).strip(),
                "grade": score_match.group(1) if score_match else score_text,
                "score": int(score_match.group(2)) if score_match else 0,
                "description": str(item.get("description", "")).strip(),
            }
        )
    return {
        "type_display": type_display,
        "type_code": type_code,
        "type_name": type_name,
        "match_percent": int(match_percent_match.group(1)) if match_percent_match else 0,
        "hit_dimensions": int(hit_match.group(1)) if hit_match else 0,
        "total_dimensions": int(hit_match.group(2)) if hit_match else 0,
        "type_subname": str(payload.get("typeSubname", "")).strip(),
        "poster_caption": str(payload.get("posterCaption", "")).strip(),
        "analysis": str(payload.get("analysis", "")).strip(),
        "dimensions": dimensions,
    }


def _build_sbti_view(source: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
    run_mode = "partial-debug" if data["average_auto_filled_questions"] > 0 else "full"
    cards = [
        {
            "label": item["name"],
            "value": f"{item['average_score']:.1f} / 4",
            "detail": f"dominant grade {item['dominant_grade']}",
        }
        for item in data["aggregate_dimensions"][:8]
    ]
    detail_rows = [
        (item["name"], f"{item['average_score']:.1f} / 4", item["dominant_grade"])
        for item in data["aggregate_dimensions"]
    ]
    round_rows = [
        (
            f"Round {index}",
            item["type_display"],
            f"{item['match_percent']}%",
            item["type_subname"] or item["poster_caption"],
        )
        for index, item in enumerate(data["rounds"], start=1)
    ]
    autofill_note = ""
    if data["average_auto_filled_questions"] > 0:
        autofill_note = f"；平均有 {data['average_auto_filled_questions']:.0f} 题由适配器补齐"
    return {
        "page_title": "AgentTypeTest · SBTI Report",
        "hero_eyebrow": "AgentTypeTest · SBTI",
        "hero_title": data["aggregate_type_display"],
        "hero_subtitle": f"Profile consistency: {data['profile_consistency']:.2f}",
        "hero_note": f"真实 B 站活动页答题并读取结果页{autofill_note}。",
        "stat_chips": [
            {"label": "Rounds", "value": str(len(data["rounds"]))},
            {"label": "Run Mode", "value": run_mode},
            {"label": "Avg Match", "value": f"{data['average_match_percent']:.1f}%"},
            {"label": "AI-Answered", "value": f"{data['average_asked_questions']:.0f} / 31"},
            {"label": "Auto-Filled", "value": f"{data['average_auto_filled_questions']:.0f} / 31"},
        ],
        "cards_heading": "Top Dimensions",
        "cards": cards,
        "detail_heading": "Aggregate Dimensions",
        "detail_columns": ["Dimension", "Score", "Grade"],
        "detail_rows": detail_rows,
        "round_heading": "Round Results",
        "round_columns": ["Round", "Type", "Match", "Summary"],
        "round_rows": round_rows,
    }


def _aggregate_sbti(source: dict[str, Any], rounds: list[dict[str, Any]]) -> dict[str, Any]:
    dominant_type_display, profile_consistency = _mode([item["type_display"] for item in rounds])
    dimension_map: dict[str, list[dict[str, Any]]] = {}
    for round_result in rounds:
        for dimension in round_result["dimensions"]:
            dimension_map.setdefault(dimension["name"], []).append(dimension)
    aggregate_dimensions: list[dict[str, Any]] = []
    for name, items in dimension_map.items():
        dominant_grade, _ = _mode([item["grade"] for item in items])
        aggregate_dimensions.append(
            {
                "name": name,
                "average_score": round(mean(item["score"] for item in items), 1),
                "dominant_grade": dominant_grade,
            }
        )
    aggregate_dimensions.sort(key=lambda item: (-item["average_score"], item["name"]))
    data = {
        "aggregate_type_display": dominant_type_display,
        "profile_consistency": profile_consistency,
        "average_match_percent": mean(item["match_percent"] for item in rounds),
        "average_hit_dimensions": mean(item["hit_dimensions"] for item in rounds),
        "average_asked_questions": mean(item["asked_questions"] for item in rounds),
        "average_auto_filled_questions": mean(item["auto_filled_questions"] for item in rounds),
        "aggregate_dimensions": aggregate_dimensions,
        "rounds": rounds,
    }
    return {
        "adapter": "sbti-bilibili",
        "family": source["family"],
        "source": source,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "data": data,
        "view": _build_sbti_view(source, data),
    }


def _render_markdown(report: dict[str, Any]) -> str:
    view = report["view"]
    lines = [
        f"# {view['page_title']}",
        "",
        f"- Source: [{report['source']['label']}]({report['source']['entry_url']})",
        f"- Intro: {report['source']['short_intro']}",
        f"- Result: `{view['hero_title']}`",
        f"- Summary: {view['hero_subtitle']}",
    ]
    if view.get("hero_note"):
        lines.append(f"- Note: {view['hero_note']}")
    if view.get("stat_chips"):
        lines.extend(["", "## Summary", ""])
        for chip in view["stat_chips"]:
            lines.append(f"- {chip['label']}: `{chip['value']}`")
    if view.get("cards"):
        lines.extend(["", f"## {view['cards_heading']}", ""])
        for card in view["cards"]:
            detail = f" ({card['detail']})" if card.get("detail") else ""
            lines.append(f"- {card['label']}: `{card['value']}`{detail}")
    if view.get("detail_rows"):
        lines.extend(["", f"## {view['detail_heading']}", ""])
        for row in view["detail_rows"]:
            lines.append(f"- {' | '.join(str(cell) for cell in row)}")
    if view.get("round_rows"):
        lines.extend(["", f"## {view['round_heading']}", ""])
        for row in view["round_rows"]:
            lines.append(f"- {' | '.join(str(cell) for cell in row)}")
    return "\n".join(lines) + "\n"


def _render_html(report: dict[str, Any]) -> str:
    view = report["view"]

    def render_cards(cards: Sequence[dict[str, str]]) -> str:
        return "".join(
            f"""
            <article class="card">
              <div class="card-label">{html_escape(str(item['label']))}</div>
              <div class="card-value">{html_escape(str(item['value']))}</div>
              <div class="card-detail">{html_escape(str(item.get('detail', '')))}</div>
            </article>
            """
            for item in cards
        )

    def render_rows(rows: Sequence[Sequence[str]]) -> str:
        return "".join(
            "<tr>" + "".join(f"<td>{html_escape(str(cell))}</td>" for cell in row) + "</tr>" for row in rows
        )

    stat_chips = "".join(
        f"""
        <div class="stat-chip">
          <div class="stat-label">{html_escape(str(item['label']))}</div>
          <div class="stat-value">{html_escape(str(item['value']))}</div>
        </div>
        """
        for item in view.get("stat_chips", [])
    )
    detail_section = ""
    if view.get("detail_rows"):
        detail_section = f"""
        <section class="panel">
          <div class="section-kicker">{html_escape(view['detail_heading'])}</div>
          <table>
            <thead>
              <tr>{''.join(f'<th>{html_escape(column)}</th>' for column in view['detail_columns'])}</tr>
            </thead>
            <tbody>{render_rows(view['detail_rows'])}</tbody>
          </table>
        </section>
        """
    round_section = ""
    if view.get("round_rows"):
        round_section = f"""
        <section class="panel">
          <div class="section-kicker">{html_escape(view['round_heading'])}</div>
          <table>
            <thead>
              <tr>{''.join(f'<th>{html_escape(column)}</th>' for column in view['round_columns'])}</tr>
            </thead>
            <tbody>{render_rows(view['round_rows'])}</tbody>
          </table>
        </section>
        """
    cards_section = ""
    if view.get("cards"):
        cards_section = f"""
        <section>
          <div class="section-kicker">{html_escape(view['cards_heading'])}</div>
          <div class="card-grid">{render_cards(view['cards'])}</div>
        </section>
        """
    hero_note = f'<div class="hero-note">{html_escape(view["hero_note"])}</div>' if view.get("hero_note") else ""
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html_escape(view['page_title'])}</title>
  <style>
    :root {{
      --bg: #120e11;
      --bg-2: #1b1315;
      --panel: rgba(255,255,255,0.05);
      --panel-solid: #1b1518;
      --line: rgba(246, 196, 116, 0.18);
      --ink: #f7efe6;
      --muted: #ccb9a7;
      --accent: #f0a44b;
      --accent-2: #7c2d12;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      background:
        radial-gradient(circle at top left, rgba(240,164,75,0.14), transparent 32%),
        linear-gradient(160deg, var(--bg), #0d0a0c 62%, #130f14 100%);
      color: var(--ink);
      font-family: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", serif;
    }}
    .wrap {{
      max-width: 1100px;
      margin: 0 auto;
      padding: 28px 18px 56px;
    }}
    .hero {{
      border: 1px solid var(--line);
      border-radius: 28px;
      padding: 26px;
      background:
        linear-gradient(180deg, rgba(255,255,255,0.04), rgba(255,255,255,0.02)),
        linear-gradient(150deg, rgba(240,164,75,0.08), transparent 45%);
      box-shadow: 0 20px 50px rgba(0,0,0,0.22);
    }}
    .eyebrow {{
      font-family: "Trebuchet MS", "Gill Sans", sans-serif;
      letter-spacing: .18em;
      text-transform: uppercase;
      font-size: 12px;
      color: var(--muted);
    }}
    .title {{
      font-size: clamp(42px, 7vw, 72px);
      line-height: 1.02;
      margin: 10px 0 0;
      color: var(--accent);
      word-break: break-word;
    }}
    .subtitle {{
      margin-top: 12px;
      font-size: 20px;
      color: #f3ddc2;
    }}
    .hero-note {{
      margin-top: 14px;
      color: var(--muted);
      line-height: 1.7;
      max-width: 760px;
    }}
    .source-panel {{
      margin-top: 18px;
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 14px 16px;
      background: var(--panel);
    }}
    .source-link {{
      color: #ffd59d;
      text-decoration: none;
      border-bottom: 1px solid rgba(240,164,75,0.45);
      word-break: break-all;
    }}
    .source-intro {{
      margin-top: 10px;
      color: var(--muted);
      line-height: 1.7;
    }}
    .stats {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      gap: 12px;
      margin-top: 22px;
    }}
    .stat-chip {{
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 12px 14px;
      background: var(--panel);
    }}
    .stat-label {{
      font-family: "Trebuchet MS", "Gill Sans", sans-serif;
      color: var(--muted);
      font-size: 12px;
      letter-spacing: .08em;
      text-transform: uppercase;
    }}
    .stat-value {{
      margin-top: 6px;
      font-size: 22px;
      color: var(--ink);
    }}
    .section-kicker {{
      margin: 28px 0 14px;
      font-family: "Trebuchet MS", "Gill Sans", sans-serif;
      font-size: 13px;
      letter-spacing: .16em;
      text-transform: uppercase;
      color: var(--muted);
    }}
    .card-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 14px;
    }}
    .card {{
      border: 1px solid var(--line);
      border-radius: 20px;
      padding: 16px;
      background: var(--panel);
      min-height: 132px;
    }}
    .card-label {{
      color: var(--muted);
      line-height: 1.5;
    }}
    .card-value {{
      margin-top: 10px;
      font-size: 26px;
      color: var(--ink);
      line-height: 1.2;
      word-break: break-word;
    }}
    .card-detail {{
      margin-top: 10px;
      color: #dbc6b3;
      line-height: 1.6;
      min-height: 1.6em;
    }}
    .panel {{
      margin-top: 22px;
      border: 1px solid var(--line);
      border-radius: 20px;
      padding: 18px;
      background: var(--panel-solid);
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
    }}
    th, td {{
      text-align: left;
      padding: 12px 0;
      border-bottom: 1px solid rgba(255,255,255,0.08);
      vertical-align: top;
    }}
    th {{
      color: var(--muted);
      font-weight: normal;
    }}
    @media (max-width: 720px) {{
      .wrap {{ padding: 18px 12px 42px; }}
      .hero {{ padding: 20px; }}
      .subtitle {{ font-size: 18px; }}
      th, td {{ display: block; }}
      thead {{ display: none; }}
      tr {{ display: block; padding: 10px 0; border-bottom: 1px solid rgba(255,255,255,0.08); }}
      tbody tr:last-child {{ border-bottom: 0; }}
      td {{ border-bottom: 0; padding: 4px 0; }}
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <section class="hero">
      <div class="eyebrow">{html_escape(view['hero_eyebrow'])}</div>
      <div class="title">{html_escape(view['hero_title'])}</div>
      <div class="subtitle">{html_escape(view['hero_subtitle'])}</div>
      {hero_note}
      <div class="source-panel">
        <div class="eyebrow">Source Site</div>
        <div><a class="source-link" href="{html_escape(report['source']['entry_url'])}" target="_blank" rel="noopener noreferrer">{html_escape(report['source']['label'])} · {html_escape(report['source']['entry_url'])}</a></div>
        <div class="source-intro">{html_escape(report['source']['short_intro'])}</div>
      </div>
      <div class="stats">{stat_chips}</div>
    </section>
    {cards_section}
    {detail_section}
    {round_section}
  </div>
</body>
</html>
"""


def _svg_text(value: str) -> str:
    return html_escape(value).replace("\n", " ")


def _render_svg(report: dict[str, Any]) -> str:
    view = report["view"]
    cards = view.get("cards", [])[:8]
    lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="760" viewBox="0 0 1200 760">',
        '<rect width="1200" height="760" fill="#120e11"/>',
        '<rect x="40" y="36" width="1120" height="688" rx="28" fill="#1b1518" stroke="rgba(246,196,116,0.18)"/>',
        f'<text x="84" y="98" font-family="Palatino Linotype, serif" font-size="22" fill="#ccb9a7">{_svg_text(view["hero_eyebrow"])}</text>',
        f'<text x="84" y="180" font-family="Palatino Linotype, serif" font-size="66" fill="#f0a44b">{_svg_text(view["hero_title"])}</text>',
        f'<text x="84" y="222" font-family="Palatino Linotype, serif" font-size="24" fill="#f7efe6">{_svg_text(view["hero_subtitle"])}</text>',
        f'<text x="84" y="258" font-family="Palatino Linotype, serif" font-size="18" fill="#ccb9a7">{_svg_text(report["source"]["label"])}</text>',
        f'<text x="84" y="286" font-family="Palatino Linotype, serif" font-size="16" fill="#ccb9a7">{_svg_text(report["source"]["entry_url"])}</text>',
    ]
    start_y = 350
    for index, card in enumerate(cards):
        x = 84 + (index % 2) * 510
        y = start_y + (index // 2) * 92
        lines.extend(
            [
                f'<rect x="{x}" y="{y-34}" width="470" height="76" rx="18" fill="rgba(255,255,255,0.04)" stroke="rgba(246,196,116,0.18)"/>',
                f'<text x="{x+18}" y="{y-4}" font-family="Palatino Linotype, serif" font-size="20" fill="#ccb9a7">{_svg_text(str(card["label"]))}</text>',
                f'<text x="{x+18}" y="{y+24}" font-family="Palatino Linotype, serif" font-size="28" fill="#f7efe6">{_svg_text(str(card["value"]))}</text>',
            ]
        )
    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def _run_dtti(args: argparse.Namespace, session_dir: Path) -> dict[str, Any]:
    source = _build_source_meta("dtti")
    site_data = load_dtti_site_data()
    _write_json(
        session_dir / "site.snapshot.json",
        {
            "source_url": site_data.source_url,
            "characters": site_data.characters,
            "adapter": source,
        },
    )
    question_lookup = {question.id: question for question in site_data.questions}
    round_results: list[dict[str, Any]] = []
    for round_index in range(1, args.rounds + 1):
        seed = args.seed + round_index - 1 if args.seed is not None else None
        ordered_questions = list(site_data.questions)
        random.Random(seed).shuffle(ordered_questions)
        if args.limit_questions is not None:
            ordered_questions = ordered_questions[: args.limit_questions]
        round_dir = session_dir / f"round-{round_index:02d}"
        round_dir.mkdir(parents=True, exist_ok=True)
        answers_by_id: dict[str, str] = {}
        batch_counter = 0
        for batch in _chunked([_dtti_transport_question(item) for item in ordered_questions], args.batch_size):
            batch_counter += 1
            packet = _render_packet(batch, round_index, batch_counter)
            _write_json(round_dir / f"batch-{batch_counter:02d}.packet.json", packet)
            raw_response = dispatch_transport(args, packet)
            _write_json(round_dir / f"batch-{batch_counter:02d}.response.json", raw_response)
            normalized = normalize_answers(raw_response, list(batch))
            _write_json(round_dir / f"batch-{batch_counter:02d}.answers.json", normalized)
            answers_by_id.update(normalized)
        summary = _summarize_dtti_round(site_data, answers_by_id, question_lookup)
        _write_json(round_dir / "summary.json", summary)
        round_results.append(summary)
    return _aggregate_dtti(source, round_results)


def _run_16personalities(args: argparse.Namespace, session_dir: Path) -> dict[str, Any]:
    _require_playwright()
    source = _build_source_meta("16personalities")
    round_results: list[dict[str, Any]] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not args.show_browser)
        for round_index in range(1, args.rounds + 1):
            round_dir = session_dir / f"round-{round_index:02d}"
            round_dir.mkdir(parents=True, exist_ok=True)
            context = browser.new_context(viewport={"width": 1440, "height": 1800})
            page = context.new_page()
            try:
                page.goto(source["discovery_url"], wait_until="domcontentloaded", timeout=args.timeout_ms)
                _safe_wait_for_network_idle(page, args.timeout_ms)
                page.wait_for_timeout(1500)
                completed_ids: set[str] = set()
                asked_questions = 0
                auto_filled_questions = 0
                batch_counter = 0
                merged_answers: dict[str, str] = {}
                for _step in range(20):
                    active_states = [state for state in _extract_16p_active_questions(page) if state.question.id not in completed_ids]
                    ask_states: list[SixteenPQuestionState] = []
                    fill_states: list[SixteenPQuestionState] = []
                    for state in active_states:
                        if args.limit_questions is None or asked_questions < args.limit_questions:
                            ask_states.append(state)
                            asked_questions += 1
                        else:
                            fill_states.append(state)

                    for batch_states in _chunked(ask_states, args.batch_size) if ask_states else []:
                        batch_counter += 1
                        batch_questions = [state.question for state in batch_states]
                        packet = _render_packet(batch_questions, round_index, batch_counter)
                        _write_json(round_dir / f"batch-{batch_counter:02d}.packet.json", packet)
                        raw_response = dispatch_transport(args, packet)
                        _write_json(round_dir / f"batch-{batch_counter:02d}.response.json", raw_response)
                        normalized = normalize_answers(raw_response, batch_questions)
                        _write_json(round_dir / f"batch-{batch_counter:02d}.answers.json", normalized)
                        for state in batch_states:
                            choice_id = normalized[state.question.id]
                            _apply_16p_choice(page, state, choice_id)
                            merged_answers[state.question.id] = choice_id
                            completed_ids.add(state.question.id)

                    for state in fill_states:
                        choice_id = _default_choice_id(len(state.question.choices))
                        _apply_16p_choice(page, state, choice_id)
                        merged_answers[state.question.id] = choice_id
                        completed_ids.add(state.question.id)
                        auto_filled_questions += 1

                    next_button = page.locator('button:has-text("Next")')
                    see_results = page.locator('button:has-text("See results")')
                    if next_button.count() and next_button.first.is_visible():
                        next_button.first.click(force=True)
                        page.wait_for_timeout(700)
                        continue
                    if see_results.count() and see_results.first.is_visible():
                        see_results.first.click(force=True)
                        page.wait_for_url(re.compile(r".*/profiles/.*"), timeout=args.timeout_ms)
                        page.locator("header.sp-typeheader").first.wait_for(timeout=args.timeout_ms)
                        break
                    if "/profiles/" in page.url:
                        break
                else:
                    raise ValidationError("16Personalities flow did not reach the result page")

                result = _extract_16p_result(page)
                result["asked_questions"] = len([value for key, value in merged_answers.items() if key.startswith("16p-")]) - auto_filled_questions
                result["auto_filled_questions"] = auto_filled_questions
                _write_json(round_dir / "answers.merged.json", merged_answers)
                _write_json(round_dir / "summary.json", result)
                (round_dir / "result.snapshot.html").write_text(page.content(), encoding="utf-8")
                round_results.append(result)
            finally:
                context.close()
        browser.close()
    _write_json(session_dir / "site.snapshot.json", {"adapter": source, "implementation": "browser-flow"})
    return _aggregate_16p(source, round_results)


def _run_sbti(args: argparse.Namespace, session_dir: Path) -> dict[str, Any]:
    _require_playwright()
    source = _build_source_meta("sbti-bilibili")
    round_results: list[dict[str, Any]] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not args.show_browser)
        for round_index in range(1, args.rounds + 1):
            round_dir = session_dir / f"round-{round_index:02d}"
            round_dir.mkdir(parents=True, exist_ok=True)
            context = browser.new_context(viewport={"width": 1440, "height": 2200})
            page = context.new_page()
            try:
                page.goto(source["discovery_url"], wait_until="domcontentloaded", timeout=args.timeout_ms)
                _safe_wait_for_network_idle(page, args.timeout_ms)
                page.wait_for_timeout(1000)
                page.locator('button:has-text("开始测试")').first.click(force=True)
                page.locator(".question-item").first.wait_for(timeout=args.timeout_ms)
                page.wait_for_timeout(500)
                question_states = _extract_sbti_questions(page)
                if round_index == 1:
                    _write_json(
                        session_dir / "site.snapshot.json",
                        {
                            "adapter": source,
                            "question_count": len(question_states),
                            "implementation": "browser-flow",
                        },
                    )
                ordered_states = list(question_states)
                if args.seed is not None:
                    rng = random.Random(args.seed + round_index - 1)
                    rng.shuffle(ordered_states)
                if args.limit_questions is not None:
                    asked_states = ordered_states[: args.limit_questions]
                else:
                    asked_states = ordered_states
                asked_by_id = {state.question.id: state for state in asked_states}

                merged_answers: dict[str, str] = {}
                batch_counter = 0
                for batch_states in _chunked(asked_states, args.batch_size):
                    batch_counter += 1
                    batch_questions = [state.question for state in batch_states]
                    packet = _render_packet(batch_questions, round_index, batch_counter)
                    _write_json(round_dir / f"batch-{batch_counter:02d}.packet.json", packet)
                    raw_response = dispatch_transport(args, packet)
                    _write_json(round_dir / f"batch-{batch_counter:02d}.response.json", raw_response)
                    normalized = normalize_answers(raw_response, batch_questions)
                    _write_json(round_dir / f"batch-{batch_counter:02d}.answers.json", normalized)
                    for state in batch_states:
                        choice_id = normalized[state.question.id]
                        _apply_sbti_choice(page, state, choice_id)
                        merged_answers[state.question.id] = choice_id

                auto_filled_questions = 0
                for state in question_states:
                    if state.question.id in asked_by_id:
                        continue
                    choice_id = _default_choice_id(len(state.question.choices))
                    _apply_sbti_choice(page, state, choice_id)
                    merged_answers[state.question.id] = choice_id
                    auto_filled_questions += 1

                page.wait_for_timeout(600)
                submit = page.locator('button:has-text("提交并查看结果")').first
                submit.click(force=True)
                page.locator(".result-wrap:visible .type-name").first.wait_for(timeout=args.timeout_ms)
                page.wait_for_timeout(1000)
                result = _extract_sbti_result(page)
                result["asked_questions"] = len(asked_states)
                result["auto_filled_questions"] = auto_filled_questions
                _write_json(round_dir / "answers.merged.json", merged_answers)
                _write_json(round_dir / "summary.json", result)
                (round_dir / "result.snapshot.html").write_text(page.content(), encoding="utf-8")
                round_results.append(result)
            finally:
                context.close()
        browser.close()
    return _aggregate_sbti(source, round_results)


def _write_report_artifacts(session_dir: Path, report: dict[str, Any]) -> None:
    _write_json(session_dir / "report.json", report)
    (session_dir / "report.md").write_text(_render_markdown(report), encoding="utf-8")
    (session_dir / "report.html").write_text(_render_html(report), encoding="utf-8")
    (session_dir / "report.svg").write_text(_render_svg(report), encoding="utf-8")


def cmd_run(args: argparse.Namespace) -> int:
    session_dir = Path(args.session_dir).resolve() if args.session_dir else _default_session_dir(f"website-session-{args.adapter}").resolve()
    session_dir.mkdir(parents=True, exist_ok=True)
    try:
        if args.adapter == "dtti":
            report = _run_dtti(args, session_dir)
        elif args.adapter == "16personalities":
            report = _run_16personalities(args, session_dir)
        elif args.adapter == "sbti-bilibili":
            report = _run_sbti(args, session_dir)
        else:
            raise ValidationError(f"unsupported adapter: {args.adapter}")
    except PlaywrightError as exc:
        raise ValidationError(
            "browser-backed adapter failed. If Chromium is missing, run `python -m playwright install chromium` first. "
            f"Details: {exc}"
        ) from exc
    _write_report_artifacts(session_dir, report)
    auto_filled = report["data"].get("average_auto_filled_questions")
    run_mode = "partial-debug" if isinstance(auto_filled, (int, float)) and auto_filled > 0 else "full"
    print(f"Report JSON: {session_dir / 'report.json'}")
    print(f"Report HTML: {session_dir / 'report.html'}")
    print(f"Report SVG: {session_dir / 'report.svg'}")
    print(f"Run mode: {run_mode}")
    print(f"Aggregate result: {report['view']['hero_title']}")
    print(f"Summary: {report['view']['hero_subtitle']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run staged website-backed personality tests.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run", help="Run an implemented website adapter")
    run.add_argument("--adapter", required=True, choices=("dtti", "16personalities", "sbti-bilibili"))
    add_transport_args(run)
    run.add_argument("--batch-size", type=int, default=4)
    run.add_argument(
        "--limit-questions",
        type=int,
        default=None,
        help="Debug or extreme-short-run cap. Default behavior is a full website run; setting this lower triggers partial AI answering and adapter auto-fill for the remaining questions.",
    )
    run.add_argument("--rounds", type=int, default=1)
    run.add_argument("--seed", type=int, default=None)
    run.add_argument("--session-dir", default=None)
    run.add_argument("--show-browser", action="store_true", help="Show the browser while browser-backed adapters run")
    run.add_argument("--timeout-ms", type=int, default=60000, help="Browser wait timeout in milliseconds")
    run.set_defaults(func=cmd_run)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    validate_transport_args(args, parser)
    try:
        return args.func(args)
    except (ValidationError, TransportError) as exc:
        print(f"ValidationError: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
