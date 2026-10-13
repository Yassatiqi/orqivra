"""Configuration diagnostics must never repeat attacker-controlled values."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ConfigDiagnosticSafetyTests(unittest.TestCase):
    def test_cli_diagnostics_redact_values_keys_and_semantic_overrides(self) -> None:
        cases = [
            ("object", {"workflow": {"preferred_parallelism": {"api_key": "AUDIT_SECRET_SENTINEL_OBJECT"}}}, ["config", "validate"]),
            ("scalar", {"workflow": {"preferred_parallelism": "AUDIT_SECRET_SENTINEL_SCALAR"}}, ["config", "validate"]),
            ("array", {"workflow": {"preferred_parallelism": ["AUDIT_SECRET_SENTINEL_ARRAY"]}}, ["config", "validate"]),
            ("unknown", {"AUDIT_SECRET_SENTINEL_KEY": {"api_key": "AUDIT_SECRET_SENTINEL_UNKNOWN"}}, ["config", "validate"]),
            ("nested-unknown", {"workflow": {"AUDIT_SECRET_SENTINEL_NESTED_KEY": "AUDIT_SECRET_SENTINEL_NESTED_VALUE"}}, ["config", "validate"]),
            ("provider", {"editions": {"codex": {"roles": {"implementer": {"provider": "AUDIT_SECRET_SENTINEL_PROVIDER"}}}}}, ["config", "show", "--edition", "codex"]),
            ("model", {"editions": {"codex": {"roles": {"implementer": {"model": "AUDIT_SECRET_SENTINEL_MODEL"}}}}}, ["config", "show", "--edition", "codex"]),
            (
                "reasoning-value",
                {"editions": {"claude-code": {"roles": {"implementer": {"reasoning": {
                    "control": "claude-code.effort", "value": "AUDIT_SECRET_SENTINEL_REASONING"
                }}}}}},
                ["config", "show", "--edition", "claude-code"],
            ),
            (
                "reasoning-control",
                {"editions": {"claude-code": {"roles": {"implementer": {"reasoning": {
                    "control": "AUDIT_SECRET_SENTINEL_CONTROL", "value": "high"
                }}}}}},
                ["config", "validate"],
            ),
        ]
        with tempfile.TemporaryDirectory(prefix="orqivra-config-safe-") as temporary:
            root = Path(temporary)
            env = os.environ.copy()
            env["PYTHONPATH"] = str(ROOT / "src")
            for label, data, command in cases:
                with self.subTest(case=label):
                    config_path = root / f"{label}.json"
                    config_path.write_text(json.dumps(data), encoding="utf-8")
                    result = subprocess.run(
                        [sys.executable, "-m", "orqivra.cli", *command, "--config", str(config_path)],
                        cwd=ROOT,
                        env=env,
                        text=True,
                        capture_output=True,
                        check=False,
                    )
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertNotIn("AUDIT_SECRET_SENTINEL", result.stdout + result.stderr)
                    self.assertNotIn("Traceback", result.stderr)
                    self.assertTrue(result.stderr.startswith("orqivra:"), result.stderr)

    def test_duplicate_key_diagnostic_does_not_repeat_the_key(self) -> None:
        with tempfile.TemporaryDirectory(prefix="orqivra-config-duplicate-") as temporary:
            config_path = Path(temporary) / "duplicate.json"
            config_path.write_text(
                '{"AUDIT_SECRET_SENTINEL_DUPLICATE":1,"AUDIT_SECRET_SENTINEL_DUPLICATE":2}',
                encoding="utf-8",
            )
            result = subprocess.run(
                [sys.executable, "-m", "orqivra.cli", "config", "validate", "--config", str(config_path)],
                cwd=ROOT,
                env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertNotIn("AUDIT_SECRET_SENTINEL", result.stdout + result.stderr)
            self.assertIn("Duplicate JSON object key", result.stderr)

    def test_schema_constraints_show_trusted_values_and_corrective_actions(self) -> None:
        cases = [
            ("schema-version", {"schema_version": "AUDIT_SECRET_SENTINEL_SCHEMA"}, ["config", "validate"], "schema_version: must use the schema-defined value 1. Restore this documented value."),
            ("fallback-policy", {"fallback": {"policy": "AUDIT_SECRET_SENTINEL_FALLBACK"}}, ["config", "validate"], 'fallback.policy: must use the schema-defined value "none". Restore this documented value.'),
            ("preferred-route", {"workflow": {"preferred_route": "AUDIT_SECRET_SENTINEL_ROUTE"}}, ["config", "validate"], 'workflow.preferred_route: must be one of the documented values: "recommend", "solo", "delegate", "audit", "full". Choose one of these values.'),
            ("parallelism-type", {"workflow": {"preferred_parallelism": {"api_key": "AUDIT_SECRET_SENTINEL_PARALLELISM"}}}, ["config", "validate"], "workflow.preferred_parallelism: expected integer. Set this field to a whole number."),
            ("parallelism-minimum", {"workflow": {"preferred_parallelism": 0}}, ["config", "validate"], "workflow.preferred_parallelism: must be at least 1. Increase this value to at least 1."),
            ("parallelism-maximum", {"workflow": {"preferred_parallelism": 9}}, ["config", "validate"], "workflow.preferred_parallelism: must be at most 8. Reduce this value to no more than 8."),
            (
                "reasoning-control",
                {"editions": {"codex": {"roles": {"implementer": {
                    "reasoning": {"control": "AUDIT_SECRET_SENTINEL_CONTROL", "value": "high"}
                }}}}},
                ["config", "validate"],
                'reasoning.control: must be one of the documented values: "codex.model_reasoning_effort", "claude-code.effort". Choose one of these values.',
            ),
            (
                "provider",
                {"editions": {"codex": {"roles": {"implementer": {
                    "provider": "AUDIT_SECRET_SENTINEL_PROVIDER"
                }}}}},
                ["config", "show", "--edition", "codex"],
                'provider must be "openai" for this edition. Set provider to "openai" or omit it to inherit the edition provider.',
            ),
        ]
        with tempfile.TemporaryDirectory(prefix="orqivra-config-constraints-") as temporary:
            root = Path(temporary)
            env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
            for label, data, command, expected in cases:
                with self.subTest(case=label):
                    config_path = root / f"{label}.json"
                    config_path.write_text(json.dumps(data), encoding="utf-8")
                    result = subprocess.run(
                        [sys.executable, "-m", "orqivra.cli", *command, "--config", str(config_path)],
                        cwd=ROOT,
                        env=env,
                        text=True,
                        capture_output=True,
                        check=False,
                    )
                    diagnostic = result.stdout + result.stderr
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertIn(expected, diagnostic)
                    self.assertNotIn("AUDIT_SECRET_SENTINEL", diagnostic)
                    self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
