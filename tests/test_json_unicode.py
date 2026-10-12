"""Regression coverage for cross-runtime-safe JSON Unicode inputs."""

from __future__ import annotations

import sys
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from orqivra.errors import OrqivraError
from orqivra.cli import _emit
from orqivra.schema import load_json


class JsonUnicodeTests(unittest.TestCase):
    def test_lone_surrogates_are_rejected_in_nested_values_and_object_keys(self) -> None:
        cases = (
            '{"value":"\\ud800"}',
            '{"nested":[{"value":"\\udfff"}]}',
            '{"\\ud800":"value"}',
        )
        with tempfile.TemporaryDirectory(prefix="orqivra-json-unicode-") as temporary:
            for index, content in enumerate(cases):
                with self.subTest(content=content):
                    path = Path(temporary) / f"case-{index}.json"
                    path.write_text(content, encoding="utf-8")
                    with self.assertRaisesRegex(OrqivraError, "Lone surrogate"):
                        load_json(path)

    def test_valid_unicode_json_remains_supported(self) -> None:
        with tempfile.TemporaryDirectory(prefix="orqivra-json-unicode-") as temporary:
            path = Path(temporary) / "valid.json"
            path.write_text('{"value":"Å"}', encoding="utf-8")
            self.assertEqual(load_json(path), {"value": "Å"})

    def test_json_output_is_safe_for_ascii_only_consoles(self) -> None:
        buffer = io.BytesIO()
        stream = io.TextIOWrapper(buffer, encoding="ascii")
        try:
            with patch("sys.stdout", stream):
                _emit({"value": "Å"})
            stream.flush()
            self.assertEqual(json.loads(buffer.getvalue()), {"value": "Å"})
        finally:
            stream.detach()


if __name__ == "__main__":
    unittest.main()
