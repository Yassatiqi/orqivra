"""Canonical skill rendering, offline bundles, and manifest-scoped installation."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from orqivra.errors import OrqivraError
import orqivra.installer as installer
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

    def test_install_rechecks_owned_destination_immediately_before_replacement(self) -> None:
        with tempfile.TemporaryDirectory(prefix="orqivra install race ") as temporary:
            target = Path(temporary) / "skills"
            install("codex", target, ["orqivra-orchestrate"], apply=True)
            owned_file = target / "orqivra-orchestrate" / "SKILL.md"
            concurrent_change = b"Concurrent user edit.\n"
            real_fsync = os.fsync

            def mutate_before_destination_recheck(descriptor: int) -> None:
                owned_file.write_bytes(concurrent_change)
                real_fsync(descriptor)

            with patch.object(installer.os, "fsync", side_effect=mutate_before_destination_recheck):
                with self.assertRaisesRegex(OrqivraError, "modified during installation"):
                    install("codex", target, ["orqivra-orchestrate"], apply=True)
            self.assertEqual(owned_file.read_bytes(), concurrent_change)

    def test_install_rechecks_manifest_immediately_before_replacement(self) -> None:
        with tempfile.TemporaryDirectory(prefix="orqivra manifest race ") as temporary:
            target = Path(temporary) / "skills"
            install("codex", target, ["orqivra-orchestrate"], apply=True)
            manifest_path = target / ".orqivra-manifest.json"
            concurrent_change = manifest_path.read_bytes() + b"\nConcurrent manifest edit.\n"
            real_fsync = os.fsync
            calls = 0

            def mutate_before_manifest_recheck(descriptor: int) -> None:
                nonlocal calls
                calls += 1
                if calls == 2:
                    manifest_path.write_bytes(concurrent_change)
                real_fsync(descriptor)

            with patch.object(installer.os, "fsync", side_effect=mutate_before_manifest_recheck):
                with self.assertRaisesRegex(OrqivraError, "manifest changed"):
                    install("codex", target, ["orqivra-orchestrate"], apply=True)
            self.assertEqual(manifest_path.read_bytes(), concurrent_change)

    def test_uninstall_rechecks_each_owned_file_immediately_before_unlink(self) -> None:
        with tempfile.TemporaryDirectory(prefix="orqivra uninstall race ") as temporary:
            target = Path(temporary) / "skills"
            install("codex", target, ["orqivra-orchestrate"], apply=True)
            owned_file = target / "orqivra-orchestrate" / "SKILL.md"
            concurrent_change = b"Concurrent user edit.\n"
            real_safe_join = installer.safe_join
            calls = 0

            def mutate_after_initial_verification(root: Path, relative: str, *, allow_missing: bool = False) -> Path:
                nonlocal calls
                result = real_safe_join(root, relative, allow_missing=allow_missing)
                calls += 1
                if calls == 2:
                    result.write_bytes(concurrent_change)
                return result

            with patch.object(installer, "safe_join", side_effect=mutate_after_initial_verification):
                with self.assertRaisesRegex(OrqivraError, "modified; refusing to remove"):
                    uninstall(target, apply=True)
            self.assertEqual(owned_file.read_bytes(), concurrent_change)
            self.assertTrue((target / ".orqivra-manifest.json").is_file())

    def test_manifest_hashes_must_be_lowercase_sha256(self) -> None:
        with tempfile.TemporaryDirectory(prefix="orqivra manifest digest ") as temporary:
            target = Path(temporary) / "skills"
            install("codex", target, ["orqivra-orchestrate"], apply=True)
            manifest_path = target / ".orqivra-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"]["orqivra-orchestrate/SKILL.md"] = "A" * 64
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(OrqivraError, "invalid file digest"):
                verify_install(target)

    def test_malformed_manifest_shapes_are_reported_as_orqivra_errors(self) -> None:
        with tempfile.TemporaryDirectory(prefix="orqivra malformed manifest ") as temporary:
            target = Path(temporary) / "skills"
            install("codex", target, ["orqivra-orchestrate"], apply=True)
            manifest_path = target / ".orqivra-manifest.json"
            original = json.loads(manifest_path.read_text(encoding="utf-8"))
            malformed_manifests = [
                [],
                {**original, "format_version": True},
                {**original, "edition": []},
                {**original, "files": []},
            ]
            for manifest in malformed_manifests:
                with self.subTest(manifest=manifest):
                    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
                    with self.assertRaises(OrqivraError):
                        verify_install(target)


if __name__ == "__main__":
    unittest.main()
