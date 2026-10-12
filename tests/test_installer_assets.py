"""Canonical skill rendering, offline bundles, and manifest-scoped installation."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from orqivra.errors import OrqivraError
from orqivra.installer import build, install, render_edition_skills, uninstall, validate_skills, verify_install


class InstallerAssetTests(unittest.TestCase):
    def test_all_editions_render_from_canonical_sources_and_validated_adapters(self) -> None:
        expected = {
            "codex": [835, 897, 883, 864],
            "claude-code": [828, 890, 876, 857],
            "gemini-cli": [825, 887, 873, 854],
        }
        for edition, word_counts in expected.items():
            with self.subTest(edition=edition):
                rendered, validation = render_edition_skills(edition)
                self.assertEqual([skill["words"] for skill in validation["skills"]], word_counts)
                self.assertEqual(set(rendered), {"orqivra-orchestrate", "orqivra-architecture", "orqivra-verify", "orqivra-recover"})
                self.assertTrue(all("ORQIVRA_CLIENT_ADAPTER" not in text for text in rendered.values()))

    def test_bundle_contains_native_layout_adapter_schemas_and_license(self) -> None:
        with tempfile.TemporaryDirectory(prefix="orqivra Python bundle ") as temporary:
            output = Path(temporary) / "bundle output"
            editions = build("all", output)
            self.assertEqual(len(editions), 3)
            for edition_root in editions:
                edition = edition_root.name
                native = {"codex": ".agents/skills", "claude-code": ".claude/skills", "gemini-cli": ".gemini/skills"}[edition]
                self.assertEqual(validate_skills(edition_root / native)["count"], 4)
                self.assertTrue((edition_root / "editions" / edition / "adapter.json").is_file())
                self.assertTrue((edition_root / "schemas" / "state.schema.json").is_file())
                self.assertTrue((edition_root / "LICENSE").is_file())
                self.assertTrue((edition_root / "BUILD-MANIFEST.json").is_file())

    def test_explicit_installation_refuses_modified_files_and_preserves_unrelated_data(self) -> None:
        with tempfile.TemporaryDirectory(prefix="orqivra Python install ") as temporary:
            target = Path(temporary) / "explicit client skills target"
            dry_run = install("codex", target, ["orqivra-orchestrate"])
            self.assertTrue(dry_run["dry_run"])
            self.assertFalse(target.exists())

            applied = install("codex", target, ["orqivra-orchestrate"], apply=True)
            self.assertFalse(applied["dry_run"])
            self.assertTrue(verify_install(target)["valid"])
            owned_file = target / "orqivra-orchestrate" / "SKILL.md"
            original = owned_file.read_bytes()
            owned_file.write_bytes(original + b"\nUser change.\n")
            with self.assertRaises(OrqivraError):
                verify_install(target)
            with self.assertRaises(OrqivraError):
                install("codex", target, ["orqivra-orchestrate"], apply=True)
            with self.assertRaises(OrqivraError):
                uninstall(target, apply=True)
            self.assertTrue(owned_file.read_bytes().endswith(b"User change.\n"))

            owned_file.write_bytes(original)
            unrelated = target / "unrelated-user-file.txt"
            unrelated.write_text("Keep this file.\n", encoding="utf-8")
            removed = uninstall(target, apply=True)
            self.assertEqual(removed["removed_files"], ["orqivra-orchestrate/SKILL.md"])
            self.assertEqual(unrelated.read_text(encoding="utf-8"), "Keep this file.\n")


if __name__ == "__main__":
    unittest.main()
