"""Python configuration loading and catalog-aware resolution regressions."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from orqivra.config import _profile_and_catalog, load_project_config, resolve_edition
from orqivra.errors import InputOutputError, OrqivraError
from orqivra.installer import build
from orqivra.schema import load_json


class ConfigLoadingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="orqivra-config-")
        self.addCleanup(self.temporary.cleanup)
        self.cwd = Path(self.temporary.name)

    def test_auto_discovery_absence_and_empty_forms_inherit_defaults(self) -> None:
        config, source = load_project_config(None, cwd=self.cwd)
        self.assertEqual(config["workflow"], {"preferred_route": "recommend", "preferred_parallelism": 2})
        self.assertEqual(config["fallback"], {"policy": "none"})
        self.assertEqual(source, {"kind": "defaults", "path": None})

        for index, content in enumerate(("", " \r\n\t", "{}", '{"schema_version": 1}')):
            with self.subTest(content=content):
                path = self.cwd / "orqivra.config.json"
                path.write_text(content, encoding="utf-8")
                config, source = load_project_config(None, cwd=self.cwd)
                self.assertEqual(config["workflow"]["preferred_parallelism"], 2)
                self.assertEqual(config["fallback"]["policy"], "none")
                self.assertEqual(source, {"kind": "file", "path": "orqivra.config.json"})
                path.unlink()

    def test_explicit_missing_file_is_actionable_io_error(self) -> None:
        missing = self.cwd / "selected.json"
        with self.assertRaisesRegex(InputOutputError, r"selected.json.*Create the file or omit --config"):
            load_project_config(missing)

    def test_inaccessible_auto_discovered_config_is_not_treated_as_absent(self) -> None:
        discovered = self.cwd / "orqivra.config.json"
        real_lstat = Path.lstat

        def deny_discovery(path: Path):
            if path == discovered:
                raise PermissionError("access denied by test")
            return real_lstat(path)

        with patch.object(Path, "lstat", deny_discovery):
            with self.assertRaisesRegex(InputOutputError, "Could not inspect configuration file.*access denied"):
                load_project_config(None, cwd=self.cwd)

    def test_recursive_merge_preserves_defaults_for_omitted_fields(self) -> None:
        selected = self.cwd / "selected.json"
        selected.write_text('{"workflow":{"preferred_route":"audit"}}', encoding="utf-8")
        config, source = load_project_config(selected)
        self.assertEqual(config["workflow"], {"preferred_route": "audit", "preferred_parallelism": 2})
        self.assertEqual(config["fallback"], {"policy": "none"})
        self.assertEqual(source, {"kind": "file", "path": str(selected)})

    def test_invalid_json_and_invalid_schema_are_not_silently_defaulted(self) -> None:
        selected = self.cwd / "selected.json"
        for contents in ('{"workflow":{},"workflow":{}}', "{", '{"unexpected":true}'):
            with self.subTest(contents=contents):
                selected.write_text(contents, encoding="utf-8")
                with self.assertRaises(OrqivraError):
                    load_project_config(selected)


class ModelResolutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.profiles = {edition: load_json(ROOT / "profiles" / f"{edition}.json") for edition in ("codex", "claude-code", "gemini-cli")}
        cls.catalog = load_json(ROOT / "models" / "catalog.json")

    def _resolve(self, edition: str, config: dict, *, profile: dict | None = None) -> dict:
        selected = profile or self.profiles[edition]
        with patch("orqivra.config._profile_and_catalog", return_value=(selected, self.catalog)):
            return resolve_edition(config, edition)

    def test_changed_model_inherits_only_a_catalog_proven_reasoning_value(self) -> None:
        profile = json.loads(json.dumps(self.profiles["claude-code"]))
        profile["roles"]["implementer"]["reasoning"] = {
            "control": "claude-code.effort",
            "value": "medium",
        }
        result = self._resolve(
            "claude-code",
            {"editions": {"claude-code": {"roles": {"implementer": {"model": "claude-opus-5-5"}}}}},
            profile=profile,
        )
        role = result["roles"]["implementer"]
        self.assertEqual(role["reasoning"], {"control": "claude-code.effort", "value": "medium"})
        self.assertEqual(role["reasoning_resolution"], "profile")

    def test_changed_model_rejects_known_incompatible_inherited_reasoning(self) -> None:
        profile = json.loads(json.dumps(self.profiles["claude-code"]))
        profile["roles"]["implementer"]["reasoning"] = {
            "control": "claude-code.effort",
            "value": "extreme",
        }
        with self.assertRaisesRegex(OrqivraError, r"editions.claude-code.roles.implementer.reasoning.*set reasoning to null"):
            self._resolve(
                "claude-code",
                {"editions": {"claude-code": {"roles": {"implementer": {"model": "claude-opus-5-5"}}}}},
                profile=profile,
            )

    def test_changed_model_rejects_inherited_value_when_catalog_compatibility_is_unknown(self) -> None:
        config = {"editions": {"codex": {"roles": {"implementer": {"model": "gpt-6-sol"}}}}}
        with self.assertRaisesRegex(OrqivraError, r"editions.codex.roles.implementer.reasoning.*compatibility is unknown"):
            self._resolve("codex", config)

    def test_reasoning_null_clears_profile_preference_and_uses_client_default(self) -> None:
        result = self._resolve(
            "codex",
            {"editions": {"codex": {"roles": {"implementer": {"model": "gpt-6-sol", "reasoning": None}}}}},
        )
        role = result["roles"]["implementer"]
        self.assertIsNone(role["reasoning"])
        self.assertEqual(role["reasoning_resolution"], "client-default")

    def test_catalog_reasoning_uncertainty_does_not_claim_runtime_unverified(self) -> None:
        role = self._resolve("codex", {})["roles"]["implementer"]
        self.assertEqual(role["runtime_qualification"], "NOT_RUN")
        self.assertIn("UNVERIFIED; catalog does not enumerate compatible values", role["client_instructions"])

    def test_explicit_incompatible_value_has_path_and_recovery_action(self) -> None:
        config = {
            "editions": {
                "claude-code": {
                    "roles": {"implementer": {"reasoning": {"control": "claude-code.effort", "value": "extreme"}}}
                }
            }
        }
        with self.assertRaisesRegex(OrqivraError, r"editions.claude-code.roles.implementer.reasoning.value.*set reasoning to null"):
            self._resolve("claude-code", config)

    def test_unknown_model_requires_custom_source_and_is_unverified(self) -> None:
        base = {"editions": {"claude-code": {"roles": {"implementer": {"model": "local-experiment"}}}}}
        with self.assertRaisesRegex(OrqivraError, r"model_source: 'user-supplied'"):
            self._resolve("claude-code", base)
        base["editions"]["claude-code"]["roles"]["implementer"]["model_source"] = "user-supplied"
        role = self._resolve("claude-code", base)["roles"]["implementer"]
        self.assertEqual(role["model_source"], "user-supplied")
        self.assertEqual(role["runtime_qualification"], "UNVERIFIED")
        self.assertEqual(role["reasoning_resolution"], "client-default")
        self.assertIn(
            "Configure this custom model in the client; ORQIVRA cannot verify its compatibility or availability. "
            "Custom model compatibility is UNVERIFIED.",
            role["client_instructions"],
        )

    def test_empty_model_and_provider_values_inherit_the_profile(self) -> None:
        with tempfile.TemporaryDirectory(prefix="orqivra-empty-inheritance-") as temporary:
            selected = Path(temporary) / "orqivra.config.json"
            selected.write_text(
                '{"editions":{"codex":{"roles":{"implementer":{"provider":"","model":""}}}}}',
                encoding="utf-8",
            )
            config, _ = load_project_config(selected)
        role = self._resolve("codex", config)["roles"]["implementer"]
        self.assertEqual(role["provider"], self.profiles["codex"]["roles"]["implementer"]["provider"])
        self.assertEqual(role["model"], self.profiles["codex"]["roles"]["implementer"]["model"])

    def test_v2_profile_must_reference_the_loaded_catalog_version(self) -> None:
        with tempfile.TemporaryDirectory(prefix="orqivra-catalog-version-") as temporary:
            root = Path(temporary)
            (root / "profiles").mkdir()
            (root / "models").mkdir()
            profile = json.loads(json.dumps(self.profiles["codex"]))
            profile["catalog_version"] = "mismatched-catalog-version"
            (root / "profiles" / "codex.json").write_text(json.dumps(profile), encoding="utf-8")
            (root / "models" / "catalog.json").write_text(json.dumps(self.catalog), encoding="utf-8")
            with patch("orqivra.config.source_root", return_value=root):
                with self.assertRaisesRegex(OrqivraError, r"references model catalog version.*loaded catalog is version"):
                    _profile_and_catalog("codex")

    def test_custom_model_requires_provider_control_for_explicit_reasoning(self) -> None:
        config = {
            "editions": {
                "claude-code": {
                    "roles": {
                        "implementer": {
                            "model": "local-experiment",
                            "model_source": "user-supplied",
                            "reasoning": {"control": "codex.model_reasoning_effort", "value": "high"},
                        }
                    }
                }
            }
        }
        with self.assertRaisesRegex(OrqivraError, r"editions.claude-code.roles.implementer.reasoning.control"):
            self._resolve("claude-code", config)

    def test_catalog_model_cannot_be_mislabeled_custom_and_api_only_model_is_rejected(self) -> None:
        config = {"editions": {"gemini-cli": {"roles": {"implementer": {"model": "auto", "model_source": "user-supplied"}}}}}
        with self.assertRaisesRegex(OrqivraError, "cannot be 'user-supplied'"):
            self._resolve("gemini-cli", config)
        config["editions"]["gemini-cli"]["roles"]["implementer"] = {"model": "gemini-3.8-flash"}
        with self.assertRaisesRegex(OrqivraError, "no supported client edition"):
            self._resolve("gemini-cli", config)

    def test_gemini_reasoning_is_rejected_instead_of_ignored(self) -> None:
        config = {
            "editions": {
                "gemini-cli": {
                    "roles": {"implementer": {"reasoning": {"control": "claude-code.effort", "value": "high"}}}
                }
            }
        }
        with self.assertRaisesRegex(OrqivraError, r"editions.gemini-cli.roles.implementer.reasoning.control"):
            self._resolve("gemini-cli", config)

    def test_bundle_contains_config_defaults_and_model_catalog(self) -> None:
        with tempfile.TemporaryDirectory(prefix="orqivra-config-bundle-") as temporary:
            built = build("codex", Path(temporary) / "bundle")
            root = built[0]
            self.assertTrue((root / "defaults" / "config.json").is_file())
            self.assertTrue((root / "models" / "catalog.json").is_file())
            manifest = load_json(root / "BUILD-MANIFEST.json")
            self.assertIn("defaults/config.json", manifest["files"])
            self.assertIn("models/catalog.json", manifest["files"])


if __name__ == "__main__":
    unittest.main()
