from __future__ import annotations

from dataclasses import dataclass
from html import escape as html_escape
import json
import random
from typing import Any


class ValidationError(ValueError):
    pass


@dataclass(frozen=True)
class SideDefinition:
    code: str
    label: str


@dataclass(frozen=True)
class Dimension:
    id: str
    left: SideDefinition
    right: SideDefinition


@dataclass(frozen=True)
class Effect:
    dimension: str
    side: str
    weight: float


@dataclass(frozen=True)
class Choice:
    id: str
    text: str
    effects: tuple[Effect, ...]


@dataclass(frozen=True)
class Question:
    id: str
    prompt: str
    choices: tuple[Choice, ...]


@dataclass(frozen=True)
class TestBank:
    family: str
    version: str
    title: str
    description: str
    blind_label: str
    report_mode: str
    dimension_order: tuple[str, ...]
    dimensions: tuple[Dimension, ...]
    questions: tuple[Question, ...]


def _require_keys(obj: dict[str, Any], keys: tuple[str, ...], scope: str) -> None:
    missing = [key for key in keys if key not in obj]
    if missing:
        raise ValidationError(f"{scope} missing keys: {', '.join(missing)}")


def load_test_bank(data: dict[str, Any]) -> TestBank:
    _require_keys(
        data,
        (
            "family",
            "version",
            "title",
            "description",
            "blind_label",
            "report_mode",
            "dimension_order",
            "dimensions",
            "questions",
        ),
        "bank",
    )
    dimensions: list[Dimension] = []
    seen_dimension_ids: set[str] = set()
    for raw_dimension in data["dimensions"]:
        _require_keys(raw_dimension, ("id", "left", "right"), "dimension")
        dimension_id = str(raw_dimension["id"])
        if dimension_id in seen_dimension_ids:
            raise ValidationError(f"duplicate dimension id: {dimension_id}")
        seen_dimension_ids.add(dimension_id)
        left = raw_dimension["left"]
        right = raw_dimension["right"]
        _require_keys(left, ("code", "label"), f"dimension {dimension_id}.left")
        _require_keys(right, ("code", "label"), f"dimension {dimension_id}.right")
        dimensions.append(
            Dimension(
                id=dimension_id,
                left=SideDefinition(code=str(left["code"]), label=str(left["label"])),
                right=SideDefinition(code=str(right["code"]), label=str(right["label"])),
            )
        )

    dimension_index = {dimension.id: dimension for dimension in dimensions}
    questions: list[Question] = []
    seen_question_ids: set[str] = set()
    for raw_question in data["questions"]:
        _require_keys(raw_question, ("id", "prompt", "choices"), "question")
        question_id = str(raw_question["id"])
        if question_id in seen_question_ids:
            raise ValidationError(f"duplicate question id: {question_id}")
        seen_question_ids.add(question_id)
        choices: list[Choice] = []
        seen_choice_ids: set[str] = set()
        for raw_choice in raw_question["choices"]:
            _require_keys(raw_choice, ("id", "text", "effects"), f"question {question_id}.choice")
            choice_id = str(raw_choice["id"]).upper()
            if choice_id in seen_choice_ids:
                raise ValidationError(f"duplicate choice id in {question_id}: {choice_id}")
            seen_choice_ids.add(choice_id)
            effects: list[Effect] = []
            for raw_effect in raw_choice["effects"]:
                _require_keys(raw_effect, ("dimension", "side", "weight"), f"question {question_id}.effect")
                dimension = str(raw_effect["dimension"])
                if dimension not in dimension_index:
                    raise ValidationError(f"unknown dimension in {question_id}: {dimension}")
                side = str(raw_effect["side"])
                if side not in {"left", "right"}:
                    raise ValidationError(f"invalid side in {question_id}: {side}")
                effects.append(
                    Effect(
                        dimension=dimension,
                        side=side,
                        weight=float(raw_effect["weight"]),
                    )
                )
            choices.append(
                Choice(
                    id=choice_id,
                    text=str(raw_choice["text"]),
                    effects=tuple(effects),
                )
            )
        if len(choices) < 2:
            raise ValidationError(f"question {question_id} must have at least two choices")
        questions.append(
            Question(
                id=question_id,
                prompt=str(raw_question["prompt"]),
                choices=tuple(choices),
            )
        )

    dimension_order = tuple(str(item) for item in data["dimension_order"])
    for item in dimension_order:
        if item not in dimension_index:
            raise ValidationError(f"dimension_order references unknown dimension: {item}")

    return TestBank(
        family=str(data["family"]),
        version=str(data["version"]),
        title=str(data["title"]),
        description=str(data["description"]),
        blind_label=str(data["blind_label"]),
        report_mode=str(data["report_mode"]),
        dimension_order=dimension_order,
        dimensions=tuple(dimensions),
        questions=tuple(questions),
    )


def validate_bank_payload(data: dict[str, Any]) -> None:
    load_test_bank(data)


def build_score_state(bank: TestBank) -> dict[str, dict[str, float]]:
    return {
        dimension.id: {
            "left": 0.0,
            "right": 0.0,
        }
        for dimension in bank.dimensions
    }


def make_question_batches(
    bank: TestBank,
    batch_size: int,
    seed: int | None = None,
    limit_questions: int | None = None,
) -> list[list[Question]]:
    if batch_size < 1:
        raise ValidationError("batch_size must be >= 1")
    ordered = list(bank.questions)
    rng = random.Random(seed)
    rng.shuffle(ordered)
    if limit_questions is not None:
        ordered = ordered[:limit_questions]
    return [ordered[index : index + batch_size] for index in range(0, len(ordered), batch_size)]


def _choice_aliases(question: Question) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for idx, choice in enumerate(question.choices, start=1):
        aliases[choice.id.upper()] = choice.id
        aliases[choice.id.casefold()] = choice.id
        aliases[str(idx)] = choice.id
        aliases[choice.text.strip().casefold()] = choice.id
    return aliases


def normalize_answers(raw: Any, batch: list[Question]) -> dict[str, str]:
    if isinstance(raw, str):
        raw = json.loads(raw)
    if isinstance(raw, dict):
        items = raw.get("answers", raw)
    else:
        items = raw
    if not isinstance(items, list):
        raise ValidationError("answers payload must be a list or an object containing 'answers'")

    question_index = {question.id: question for question in batch}
    normalized: dict[str, str] = {}
    for item in items:
        if not isinstance(item, dict):
            raise ValidationError("each answer item must be an object")
        question_id = str(item.get("id", "")).strip()
        if question_id not in question_index:
            raise ValidationError(f"unknown answer id in batch: {question_id}")
        raw_choice = item.get("choice", item.get("value"))
        if raw_choice is None:
            raise ValidationError(f"answer for {question_id} is missing 'choice'")
        aliases = _choice_aliases(question_index[question_id])
        normalized_choice = aliases.get(str(raw_choice).strip().casefold())
        if normalized_choice is None:
            raise ValidationError(f"invalid choice for {question_id}: {raw_choice}")
        normalized[question_id] = normalized_choice

    missing = [question.id for question in batch if question.id not in normalized]
    if missing:
        raise ValidationError(f"missing answers for: {', '.join(missing)}")
    return normalized


def apply_answers(bank: TestBank, scores: dict[str, dict[str, float]], batch: list[Question], answers: dict[str, str]) -> None:
    question_index = {question.id: question for question in batch}
    for question_id, choice_id in answers.items():
        question = question_index[question_id]
        choice = next(choice for choice in question.choices if choice.id == choice_id)
        for effect in choice.effects:
            scores[effect.dimension][effect.side] += effect.weight


def summarize_scores(bank: TestBank, scores: dict[str, dict[str, float]]) -> dict[str, Any]:
    dimensions: list[dict[str, Any]] = []
    letters: list[str] = []
    for dimension_id in bank.dimension_order:
        dimension = next(item for item in bank.dimensions if item.id == dimension_id)
        left_score = scores[dimension_id]["left"]
        right_score = scores[dimension_id]["right"]
        if left_score > right_score:
            winner_side = "left"
            winner_code = dimension.left.code
            winner_label = dimension.left.label
        elif right_score > left_score:
            winner_side = "right"
            winner_code = dimension.right.code
            winner_label = dimension.right.label
        else:
            winner_side = "tie"
            winner_code = "?"
            winner_label = "Tie"
        letters.append(winner_code)
        dimensions.append(
            {
                "id": dimension.id,
                "left": {
                    "code": dimension.left.code,
                    "label": dimension.left.label,
                    "score": left_score,
                },
                "right": {
                    "code": dimension.right.code,
                    "label": dimension.right.label,
                    "score": right_score,
                },
                "winner": {
                    "side": winner_side,
                    "code": winner_code,
                    "label": winner_label,
                },
                "margin": abs(left_score - right_score),
            }
        )
    return {
        "family": bank.family,
        "report_mode": bank.report_mode,
        "code": "".join(letters) if bank.report_mode == "pair_letters" else None,
        "dimensions": dimensions,
    }


def aggregate_rounds(bank: TestBank, rounds: list[dict[str, Any]]) -> dict[str, Any]:
    if not rounds:
        raise ValidationError("cannot aggregate empty round list")
    aggregate_scores = build_score_state(bank)
    for round_result in rounds:
        for dimension in round_result["dimensions"]:
            aggregate_scores[dimension["id"]]["left"] += float(dimension["left"]["score"])
            aggregate_scores[dimension["id"]]["right"] += float(dimension["right"]["score"])
    aggregate_summary = summarize_scores(bank, aggregate_scores)
    round_codes = [item["code"] for item in rounds if item["code"]]
    code_consistency: float | None = None
    if round_codes:
        dominant_code = max(set(round_codes), key=round_codes.count)
        code_consistency = round_codes.count(dominant_code) / len(round_codes)

    dimension_consistency: list[dict[str, Any]] = []
    for dimension_id in bank.dimension_order:
        winners = [
            next(item for item in round_result["dimensions"] if item["id"] == dimension_id)["winner"]["code"]
            for round_result in rounds
        ]
        dominant = max(set(winners), key=winners.count)
        dimension_consistency.append(
            {
                "id": dimension_id,
                "dominant_code": dominant,
                "consistency": winners.count(dominant) / len(winners),
            }
        )

    return {
        "aggregate": aggregate_summary,
        "code_consistency": code_consistency,
        "dimension_consistency": dimension_consistency,
        "rounds": rounds,
    }


def render_batch_packet(
    bank: TestBank,
    batch: list[Question],
    round_index: int,
    batch_index: int,
    hide_family: bool = True,
) -> dict[str, Any]:
    title = "hidden" if hide_family else bank.title
    family = "hidden" if hide_family else bank.family
    prompt_lines = [
        f"You are the test subject for this {bank.blind_label}.",
        "Answer as yourself, based on your own current preferences, instincts, and habits.",
        "Pick the option that best matches how you would actually respond right now.",
        "Answer the current batch only.",
        "Return JSON only.",
        "Use this exact shape:",
        '{"answers":[{"id":"question-id","choice":"A"}]}',
        "Do not explain your reasoning.",
        "Do not evaluate, install, audit, debug, or verify the project while answering.",
        "Do not search for answer keys, scoring rules, or the full questionnaire.",
        "Do not guess the test family, test name, hidden intent, or scoring logic.",
        "Do not copy the questions back or rewrite the options as commentary.",
        "Do not add commentary, analysis, caveats, or meta-observations.",
        "",
    ]
    if not hide_family:
        prompt_lines.append(f"Test family: {bank.family}")
        prompt_lines.append(f"Title: {bank.title}")
        prompt_lines.append("")
    for question in batch:
        prompt_lines.append(f"- id: {question.id}")
        prompt_lines.append(f"  prompt: {question.prompt}")
        for choice in question.choices:
            prompt_lines.append(f"  {choice.id}. {choice.text}")
    prompt_text = "\n".join(prompt_lines)
    return {
        "family": family,
        "title": title,
        "round_index": round_index,
        "batch_index": batch_index,
        "questions": [
            {
                "id": question.id,
                "prompt": question.prompt,
                "choices": [
                    {
                        "id": choice.id,
                        "text": choice.text,
                    }
                    for choice in question.choices
                ],
            }
            for question in batch
        ],
        "instructions": {
            "response_format": {
                "type": "json",
                "schema": {
                    "answers": [
                        {
                            "id": question.id,
                            "choice": question.choices[0].id,
                        }
                        for question in batch[:1]
                    ]
                },
            }
        },
        "prompt_text": prompt_text,
    }


def render_markdown_report(report: dict[str, Any]) -> str:
    bank_meta = report.get("bank", {})
    code_consistency = report.get("code_consistency")
    code_consistency_text = f"{code_consistency:.2f}" if isinstance(code_consistency, (int, float)) else "N/A"
    lines = [
        "# AgentTypeTest Report",
        "",
    ]
    if bank_meta:
        lines.extend(
            [
                f"- Title: `{bank_meta.get('title', '')}`",
                f"- Description: {bank_meta.get('description', '')}",
                f"- Question Count: `{bank_meta.get('question_count', 0)}`",
                f"- Asked Question Count: `{bank_meta.get('asked_question_count', bank_meta.get('question_count', 0))}`",
                f"- Rounds: `{bank_meta.get('round_count', len(report['rounds']))}`",
                f"- Run Mode: `{bank_meta.get('run_mode', 'full')}`",
            ]
        )
    lines.extend(
        [
        f"- Family: `{report['aggregate']['family']}`",
        f"- Aggregate Code: `{report['aggregate']['code']}`",
        f"- Code Consistency: `{code_consistency_text}`",
        "",
        "## Aggregate Dimensions",
        "",
        ]
    )
    for dimension in report["aggregate"]["dimensions"]:
        lines.append(
            f"- `{dimension['id']}`: {dimension['winner']['code']} "
            f"({dimension['left']['code']}={dimension['left']['score']:.1f}, "
            f"{dimension['right']['code']}={dimension['right']['score']:.1f})"
        )
    lines.extend(["", "## Round Results", ""])
    for idx, round_result in enumerate(report["rounds"], start=1):
        lines.append(f"- Round {idx}: `{round_result['code']}`")
    lines.extend(["", "## Dimension Consistency", ""])
    for item in report["dimension_consistency"]:
        lines.append(f"- `{item['id']}`: {item['dominant_code']} @ {item['consistency']:.2f}")
    return "\n".join(lines) + "\n"


def render_html_report(report: dict[str, Any]) -> str:
    bank_meta = report.get("bank", {})
    code_consistency = report.get("code_consistency")
    code_consistency_text = f"{code_consistency:.2f}" if isinstance(code_consistency, (int, float)) else "N/A"

    def pct(value: float, total: float) -> float:
        if total <= 0:
            return 50.0
        return (value / total) * 100.0

    def winner_copy(dimension: dict[str, Any]) -> str:
        if dimension["winner"]["code"] == "?":
            return "Balanced"
        return f"{dimension['winner']['code']} · {dimension['winner']['label']}"

    dimension_cards: list[str] = []
    for dimension in report["aggregate"]["dimensions"]:
        left_score = float(dimension["left"]["score"])
        right_score = float(dimension["right"]["score"])
        total = left_score + right_score
        left_pct = pct(left_score, total)
        right_pct = pct(right_score, total)
        dimension_cards.append(
            f"""
            <section class="dimension-card">
              <div class="dimension-top">
                <div>
                  <div class="dimension-id">{html_escape(dimension['id'])}</div>
                  <div class="dimension-labels">{html_escape(dimension['left']['label'])} · {html_escape(dimension['right']['label'])}</div>
                </div>
                <span class="winner-pill">{html_escape(winner_copy(dimension))}</span>
              </div>
              <div class="meter">
                <div class="meter-side meter-left" style="width:{left_pct:.2f}%"></div>
                <div class="meter-side meter-right" style="width:{right_pct:.2f}%"></div>
              </div>
              <div class="meter-legend">
                <span>{html_escape(dimension['left']['code'])} = {left_score:.1f}</span>
                <span>Margin {dimension['margin']:.1f}</span>
                <span>{html_escape(dimension['right']['code'])} = {right_score:.1f}</span>
              </div>
            </section>
            """
        )

    round_rows = "".join(
        f"<tr><td>Round {idx}</td><td><span class=\"round-code\">{html_escape(item['code'] or 'N/A')}</span></td></tr>"
        for idx, item in enumerate(report["rounds"], start=1)
    )
    consistency_cards = "".join(
        f"""
        <article class="consistency-card">
          <div class="dimension-id">{html_escape(item['id'])}</div>
          <div class="consistency-dominant">{html_escape(item['dominant_code'])}</div>
          <div class="consistency-value">{item['consistency']:.2f}</div>
        </article>
        """
        for item in report["dimension_consistency"]
    )
    aggregate_code = report["aggregate"]["code"] or "N/A"
    title_text = bank_meta.get("title", "AgentTypeTest Report")
    description_text = bank_meta.get("description", "Staged aggregate report.")
    question_count = bank_meta.get("question_count", "")
    asked_question_count = bank_meta.get("asked_question_count", question_count)
    round_count = bank_meta.get("round_count", len(report["rounds"]))
    run_mode = bank_meta.get("run_mode", "full")
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AgentTypeTest Report</title>
  <style>
    :root {{
      --bg: #f4eee3;
      --panel: rgba(255,255,255,0.82);
      --panel-strong: #fffaf1;
      --ink: #1a1613;
      --muted: #6c645c;
      --line: rgba(96,75,42,0.16);
      --left: #1d6a6f;
      --right: #cf7a31;
      --accent: #8a4b2d;
      --accent-soft: #f3dfc7;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(207,122,49,0.12), transparent 28%),
        radial-gradient(circle at bottom right, rgba(29,106,111,0.10), transparent 30%),
        linear-gradient(180deg, #faf5ed 0%, var(--bg) 54%, #efe7da 100%);
    }}
    .wrap {{
      max-width: 1080px;
      margin: 0 auto;
      padding: 30px 18px 56px;
    }}
    .hero {{
      background:
        linear-gradient(140deg, rgba(255,255,255,0.78), rgba(255,250,241,0.92)),
        linear-gradient(135deg, rgba(207,122,49,0.08), transparent 44%);
      border: 1px solid var(--line);
      border-radius: 28px;
      padding: 28px;
      box-shadow: 0 18px 48px rgba(46, 34, 20, 0.08);
    }}
    .hero-grid {{
      display: grid;
      grid-template-columns: minmax(260px, 1.35fr) minmax(220px, 1fr);
      gap: 18px;
      align-items: start;
    }}
    .eyebrow {{
      font-family: "Trebuchet MS", "Gill Sans", sans-serif;
      letter-spacing: 0.14em;
      text-transform: uppercase;
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 10px;
    }}
    .code {{
      font-size: clamp(54px, 9vw, 92px);
      line-height: 0.95;
      margin: 0 0 10px;
      color: var(--accent);
    }}
    .hero-copy h2 {{
      margin: 0;
      font-size: 28px;
      line-height: 1.2;
    }}
    .hero-copy p {{
      margin: 12px 0 0;
      color: var(--muted);
      line-height: 1.75;
      max-width: 620px;
    }}
    .metrics {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
      gap: 12px;
    }}
    .metric {{
      background: rgba(255,255,255,0.68);
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 14px 16px 16px;
    }}
    .metric strong {{
      display: block;
      font-size: 26px;
      margin-top: 6px;
    }}
    .section-title {{
      margin: 30px 0 14px;
      font-family: "Trebuchet MS", "Gill Sans", sans-serif;
      color: var(--muted);
      letter-spacing: 0.14em;
      text-transform: uppercase;
      font-size: 12px;
    }}
    .dimension-grid {{
      margin-top: 24px;
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 16px;
    }}
    .dimension-card, .panel, .consistency-card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 22px;
      padding: 18px;
    }}
    .panel {{
      margin-top: 24px;
      background: var(--panel-strong);
    }}
    .dimension-top, .row {{
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 12px;
    }}
    .dimension-id {{
      font-size: 18px;
      letter-spacing: 0.04em;
    }}
    .dimension-labels {{
      margin-top: 6px;
      color: var(--muted);
      line-height: 1.6;
      font-size: 14px;
    }}
    .winner-pill {{
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      padding: 6px 10px;
      background: var(--accent-soft);
      color: var(--accent);
      font-size: 13px;
      white-space: nowrap;
    }}
    .meter {{
      height: 14px;
      border-radius: 999px;
      overflow: hidden;
      background: #ede4d7;
      display: flex;
      margin: 14px 0 10px;
    }}
    .meter-side {{ height: 100%; }}
    .meter-left {{ background: var(--left); }}
    .meter-right {{ background: var(--right); }}
    .meter-legend {{
      display: flex;
      justify-content: space-between;
      color: var(--muted);
      font-size: 14px;
      gap: 8px;
    }}
    .panel h3 {{
      margin: 0;
      font-size: 22px;
    }}
    .round-code {{
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      padding: 4px 10px;
      background: rgba(29,106,111,0.10);
      color: var(--left);
    }}
    .consistency-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
      gap: 14px;
      margin-top: 14px;
    }}
    .consistency-card {{
      background: rgba(255,255,255,0.74);
      text-align: center;
    }}
    .consistency-dominant {{
      font-size: 28px;
      margin-top: 8px;
      color: var(--accent);
    }}
    .consistency-value {{
      margin-top: 6px;
      color: var(--muted);
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 10px;
    }}
    th, td {{
      text-align: left;
      padding: 10px 0;
      border-bottom: 1px solid var(--line);
    }}
    th {{
      color: var(--muted);
      font-weight: normal;
    }}
    @media (max-width: 840px) {{
      .hero-grid {{ grid-template-columns: 1fr; }}
    }}
    @media (max-width: 640px) {{
      .wrap {{ padding: 18px 12px 42px; }}
      .hero {{ padding: 20px; }}
      }}
  </style>
</head>
<body>
  <div class="wrap">
    <section class="hero">
      <div class="hero-grid">
        <div class="hero-copy">
          <div class="eyebrow">AgentTypeTest · Aggregate Code</div>
          <h1 class="code">{html_escape(aggregate_code)}</h1>
          <h2>{html_escape(title_text)}</h2>
          <p>{html_escape(description_text)}</p>
        </div>
        <div class="metrics">
          <div class="metric">
            <div class="eyebrow">Family</div>
            <strong>{html_escape(report['aggregate']['family'])}</strong>
          </div>
          <div class="metric">
            <div class="eyebrow">Code Consistency</div>
            <strong>{code_consistency_text}</strong>
          </div>
          <div class="metric">
            <div class="eyebrow">Questions</div>
            <strong>{question_count}</strong>
          </div>
          <div class="metric">
            <div class="eyebrow">Asked</div>
            <strong>{asked_question_count}</strong>
          </div>
          <div class="metric">
            <div class="eyebrow">Rounds</div>
            <strong>{round_count}</strong>
          </div>
          <div class="metric">
            <div class="eyebrow">Run Mode</div>
            <strong>{html_escape(str(run_mode))}</strong>
          </div>
        </div>
      </div>
    </section>

    <div class="section-title">Aggregate Dimensions</div>
    <section class="dimension-grid">
      {''.join(dimension_cards)}
    </section>

    <section class="panel">
      <div class="row"><h3>Round Results</h3></div>
      <table>
        <thead><tr><th>Round</th><th>Code</th></tr></thead>
        <tbody>{round_rows}</tbody>
      </table>
    </section>

    <section class="panel">
      <div class="row"><h3>Dimension Consistency</h3></div>
      <div class="consistency-grid">{consistency_cards}</div>
    </section>
  </div>
</body>
</html>
"""


def render_svg_summary(report: dict[str, Any]) -> str:
    bank_meta = report.get("bank", {})
    aggregate_code = report["aggregate"]["code"] or "N/A"
    code_consistency = report.get("code_consistency")
    code_consistency_text = f"{code_consistency:.2f}" if isinstance(code_consistency, (int, float)) else "N/A"
    dimensions = report["aggregate"]["dimensions"]
    title_text = bank_meta.get("title", "AgentTypeTest Report")
    lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="760" viewBox="0 0 1280 760">',
        '<rect width="1280" height="760" fill="#f4eee3"/>',
        '<rect x="44" y="38" width="1192" height="684" rx="30" fill="#fffaf1" stroke="rgba(96,75,42,0.16)"/>',
        '<text x="84" y="110" font-family="Palatino Linotype, serif" font-size="22" fill="#6c645c">AgentTypeTest · Aggregate Code</text>',
        f'<text x="84" y="206" font-family="Palatino Linotype, serif" font-size="108" fill="#8a4b2d">{html_escape(aggregate_code)}</text>',
        f'<text x="84" y="252" font-family="Palatino Linotype, serif" font-size="30" fill="#1a1613">{html_escape(title_text)}</text>',
        f'<text x="84" y="300" font-family="Palatino Linotype, serif" font-size="24" fill="#6c645c">Code Consistency: {code_consistency_text}</text>',
    ]
    base_y = 388
    for idx, dimension in enumerate(dimensions):
        y = base_y + idx * 80
        left_score = float(dimension["left"]["score"])
        right_score = float(dimension["right"]["score"])
        total = max(left_score + right_score, 1.0)
        left_width = 420 * (left_score / total)
        right_width = 420 * (right_score / total)
        winner_copy = "Balanced" if dimension["winner"]["code"] == "?" else f"{dimension['winner']['code']} · {dimension['winner']['label']}"
        lines.extend(
            [
                f'<text x="84" y="{y}" font-family="Palatino Linotype, serif" font-size="28" fill="#1a1613">{html_escape(dimension["id"])}</text>',
                f'<text x="150" y="{y}" font-family="Palatino Linotype, serif" font-size="18" fill="#6c645c">{html_escape(dimension["left"]["label"])} · {html_escape(dimension["right"]["label"])}</text>',
                f'<rect x="84" y="{y+16}" width="480" height="18" rx="9" fill="#ede4d7"/>',
                f'<rect x="84" y="{y+16}" width="{left_width:.2f}" height="18" rx="9" fill="#1d6a6f"/>',
                f'<rect x="{564-right_width:.2f}" y="{y+16}" width="{right_width:.2f}" height="18" rx="9" fill="#cf7a31"/>',
                f'<text x="596" y="{y+6}" font-family="Palatino Linotype, serif" font-size="22" fill="#8a4b2d">{html_escape(winner_copy)}</text>',
                f'<text x="596" y="{y+34}" font-family="Palatino Linotype, serif" font-size="18" fill="#6c645c">{html_escape(dimension["left"]["code"])}={left_score:.1f} · {html_escape(dimension["right"]["code"])}={right_score:.1f} · margin {dimension["margin"]:.1f}</text>',
            ]
        )
    lines.append("</svg>")
    return "\n".join(lines) + "\n"
