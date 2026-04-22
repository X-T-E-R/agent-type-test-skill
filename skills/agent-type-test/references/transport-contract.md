# Transport Contract

The `subprocess` transport uses a small stdin/stdout JSON contract for external adapters.

## Input Packet

The runner writes a JSON object to the external process over stdin.

```json
{
  "family": "hidden",
  "title": "hidden",
  "round_index": 1,
  "batch_index": 1,
  "questions": [
    {
      "id": "mbti-001",
      "prompt": "When you are going out for the whole day, you usually",
      "choices": [
        { "id": "A", "text": "plan what you will do and when you will do it" },
        { "id": "B", "text": "just go with the flow" }
      ]
    }
  ],
  "instructions": {
    "response_format": {
      "type": "json",
      "schema": {
        "answers": [
          { "id": "mbti-001", "choice": "A" }
        ]
      }
    }
  },
  "prompt_text": "..."
}
```

## Expected Output

The external process should return a JSON object on stdout:

```json
{
  "answers": [
    { "id": "mbti-001", "choice": "A" }
  ],
  "meta": {
    "adapter": "your-adapter-name"
  }
}
```

## Validation Rules

- `answers[].id` must match question ids from the current batch
- `choice` must map to one of the current question choices
- avoid extra stdout text when possible; if you must log, make the last line a JSON object

## Recommended Bridge Pattern

If you need to bridge MCP or another agent runtime, use a thin wrapper:

1. read the packet from stdin
2. forward `prompt_text` to the target runtime
3. receive JSON answers from that runtime
4. write the normalized JSON response back to stdout

This keeps the main runner independent from the target runtime internals.
