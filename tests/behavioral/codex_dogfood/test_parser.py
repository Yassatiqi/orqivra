"""Focused behavior checks for the Codex dogfood parser fixture."""

from __future__ import annotations

import unittest
from pathlib import Path

from parser import parse_jsonl


FIXTURE = Path(__file__).with_name("input.jsonl")


class ParseJsonlTests(unittest.TestCase):
    def test_fixture_skips_blank_and_whitespace_only_lines(self) -> None:
        self.assertEqual(
            parse_jsonl(FIXTURE.read_text(encoding="utf-8")),
            [
                {"id": "first", "enabled": True},
                {"id": "second", "count": 2},
            ],
        )

    def test_empty_input_returns_no_records(self) -> None:
        self.assertEqual(parse_jsonl(""), [])

    def test_malformed_json_is_rejected_with_line_number(self) -> None:
        with self.assertRaisesRegex(ValueError, "Malformed JSON on line 2"):
            parse_jsonl('{"id":"first"}\n{"id":')

    def test_non_object_json_is_rejected_with_line_number(self) -> None:
        with self.assertRaisesRegex(ValueError, "Expected a JSON object on line 2"):
            parse_jsonl('{"id":"first"}\n[1, 2]')


if __name__ == "__main__":
    unittest.main()
