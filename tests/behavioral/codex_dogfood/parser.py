"""Small JSON Lines parser used by the Codex dogfood fixture."""

from __future__ import annotations

import json
from typing import Any


def parse_jsonl(text: str) -> list[dict[str, Any]]:
    """Parse JSON object records, skipping blank or whitespace-only lines."""
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if line.strip() == "":
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"Malformed JSON on line {line_number}") from error
        if not isinstance(value, dict):
            raise ValueError(f"Expected a JSON object on line {line_number}")
        records.append(value)
    return records
