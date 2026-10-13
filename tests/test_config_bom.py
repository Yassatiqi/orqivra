"""Configuration JSON accepts one leading UTF-8 BOM consistently."""

from __future__ import annotations

import tempfile
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from orqivra.config import load_project_config
from orqivra.errors import OrqivraError


class ConfigBomTests(unittest.TestCase):
    def test_leading_bom_empty_and_nonempty_files_are_accepted(self) -> None:
        with tempfile.TemporaryDirectory(prefix="orqivra-config-bom-") as temporary:
            root = Path(temporary)
            empty = root / "empty.json"
            empty.write_bytes(b"\xef\xbb\xbf{}")
            empty_config, empty_source = load_project_config(empty)
            self.assertEqual(empty_config["workflow"]["preferred_parallelism"], 2)
            self.assertEqual(empty_source["kind"], "file")

            configured = root / "configured.json"
            configured.write_bytes(b'\xef\xbb\xbf{"workflow":{"preferred_parallelism":3}}')
            config, _ = load_project_config(configured)
            self.assertEqual(config["workflow"]["preferred_parallelism"], 3)

    def test_multiple_or_misplaced_bom_and_invalid_utf8_are_rejected(self) -> None:
        cases = {
            "multiple": b"\xef\xbb\xbf\xef\xbb\xbf{}",
            "misplaced": b'{"workflow":\xef\xbb\xbf{"preferred_parallelism":3}}',
            "invalid-utf8": b"{\xff}",
        }
        with tempfile.TemporaryDirectory(prefix="orqivra-config-bom-invalid-") as temporary:
            root = Path(temporary)
            for label, data in cases.items():
                with self.subTest(case=label):
                    path = root / f"{label}.json"
                    path.write_bytes(data)
                    with self.assertRaises(OrqivraError):
                        load_project_config(path)


if __name__ == "__main__":
    unittest.main()
