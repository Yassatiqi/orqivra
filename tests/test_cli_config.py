"""Public command-line contract tests for configuration commands."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ConfigCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="orqivra-config-cli-")
        self.addCleanup(self.temporary.cleanup)
        self.temp = Path(self.temporary.name)

    def cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        source_path = str(ROOT / "src")
        existing = environment.get("PYTHONPATH")
        environment["PYTHONPATH"] = source_path if not existing else source_path + os.pathsep + existing
        return subprocess.run(
            [sys.executable, "-m", "orqivra.cli", *args],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_config_show_emits_stable_parity_shape_and_is_advisory(self) -> None:
        result = self.cli("config", "show", "--edition", "claude-code")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(
            set(payload),
            {
                "schema_version",
                "edition",
                "profile_id",
                "catalog_version",
                "config_source",
                "workflow",
                "fallback",
                "roles",
            },
        )
        self.assertEqual(payload["config_source"], {"kind": "defaults", "path": None})
        self.assertEqual(payload["workflow"], {
            "preferred_route": "recommend",
            "preferred_parallelism": 2,
            "preferred_parallelism_advisory": True,
        })
        self.assertEqual(payload["fallback"], {"policy": "none"})
        self.assertEqual(set(payload["roles"]), {"orchestrator", "implementer", "complex_implementer", "reviewer"})
        role = payload["roles"]["complex_implementer"]
        self.assertEqual(role["model"], "claude-opus-5-5")
        self.assertIsNone(role["reasoning"])
        self.assertEqual(role["reasoning_resolution"], "client-default")
        self.assertFalse(role["activatable"])

    def test_explicit_missing_config_is_exit_four_and_explains_recovery(self) -> None:
        missing = self.temp / "does-not-exist.json"
        result = self.cli("config", "show", "--edition", "codex", "--config", str(missing))
        self.assertEqual(result.returncode, 4)
        self.assertIn("Explicit configuration file was not found", result.stderr)
        self.assertIn("omit --config to use defaults", result.stderr)

    def test_validate_accepts_empty_config_and_rejects_invalid_settings(self) -> None:
        config_path = self.temp / "empty.json"
        config_path.write_text("\n \t", encoding="utf-8")
        valid = self.cli("config", "validate", "--config", str(config_path))
        self.assertEqual(valid.returncode, 0, valid.stderr)
        payload = json.loads(valid.stdout)
        self.assertEqual(
            set(payload),
            {"valid", "config_source", "schema_version", "workflow", "fallback"},
        )
        self.assertTrue(payload["valid"])
        self.assertEqual(payload["config_source"], {"kind": "file", "path": str(config_path)})
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["workflow"]["preferred_parallelism_advisory"], True)
        self.assertEqual(payload["fallback"], {"policy": "none"})

        config_path.write_text('{"workflow":{"preferred_parallelism":0}}', encoding="utf-8")
        invalid = self.cli("config", "validate", "--config", str(config_path))
        self.assertEqual(invalid.returncode, 2)
        self.assertIn("preferred_parallelism", invalid.stderr)

    def test_markdown_show_names_advisory_and_client_native_behavior(self) -> None:
        config_path = self.temp / "partial.json"
        config_path.write_text("{}", encoding="utf-8")
        result = self.cli("config", "show", "--edition", "gemini-cli", "--config", str(config_path), "--format", "markdown")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("advisory maximum", result.stdout)
        self.assertIn("client-native routing may still apply", result.stdout)
        self.assertIn("Gemini CLI owns dynamic routing", result.stdout)

    def test_profile_validate_accepts_v2_catalog_linked_assets(self) -> None:
        profile = ROOT / "profiles" / "codex.json"
        result = self.cli("validate", "profile", str(profile))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["edition"], "codex")

    def test_profile_validate_rejects_non_object_json_without_traceback(self) -> None:
        profile = self.temp / "not-an-object.json"
        for contents in ("[]", '"scalar"', "7", "null"):
            with self.subTest(contents=contents):
                profile.write_text(contents, encoding="utf-8")
                result = self.cli("validate", "profile", str(profile))
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("Profile data must be a JSON object.", result.stderr)
                self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
