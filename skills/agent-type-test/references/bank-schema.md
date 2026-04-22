# Bank Schema

This schema is the shared format for MBTI, SBTI, DTTI, and other `xxTI`-style questionnaires.

## Top-Level Fields

```json
{
  "family": "mbti",
  "version": "2026-04-22",
  "title": "MBTI 93 (zh-CN)",
  "description": "Built-in local bank",
  "blind_label": "short questionnaire",
  "report_mode": "pair_letters",
  "dimension_order": ["EI", "SN", "TF", "JP"],
  "dimensions": [],
  "questions": []
}
```

## Dimensions

```json
{
  "id": "EI",
  "left": {
    "code": "E",
    "label": "Extraversion"
  },
  "right": {
    "code": "I",
    "label": "Introversion"
  }
}
```

Rules:

- `id` must be unique.
- `left.code` and `right.code` are the two output sides for the dimension.
- `label` is report-facing text and should not be exposed to the tested AI by default.

## Questions

```json
{
  "id": "mbti-001",
  "prompt": "When you are going out for the whole day, you usually",
  "choices": [
    {
      "id": "A",
      "text": "plan what you will do and when you will do it",
      "effects": [
        {
          "dimension": "JP",
          "side": "left",
          "weight": 1
        }
      ]
    },
    {
      "id": "B",
      "text": "just go with the flow",
      "effects": [
        {
          "dimension": "JP",
          "side": "right",
          "weight": 1
        }
      ]
    }
  ]
}
```

Rules:

- `id` must be unique.
- `choices` must contain at least two options.
- each choice should normally carry at least one `effect`
- `side` must be `left` or `right`

## Report Modes

- `pair_letters`
  - fits families such as MBTI where the result is assembled from multiple dimensions
  - the final output is built in `dimension_order`, for example `INTJ`
- `dimension_scores`
  - reports dimension scores only and does not assemble a single code

## Notes

- For entertainment-oriented `xxTI` tests, the bank itself may be informal, but the schema and orchestration should stay stable.
- If a family is not naturally binary, it is still useful to map it into left-vs-right dimensions so the main runner does not need to change.
