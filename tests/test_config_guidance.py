"""Edition-specific client application guidance remains advisory and safe."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from orqivra.config import resolve_edition


class ConfigGuidanceTests(unittest.TestCase):
    def test_codex_instructions_include_main_session_and_supported_effort(self) -> None:
        role = resolve_edition({}, "codex")["roles"]["implementer"]
        instructions = role["client_instructions"]
        self.assertIn("codex --model gpt-6-luna", instructions)
        self.assertIn("model_reasoning_effort=\"max\"", instructions)
        self.assertIn("main session", instructions)
        self.assertIn("separate `[agents]` settings", instructions)
        self.assertIn("Multiple ORQIVRA role preferences are advisory", instructions)

    def test_claude_instructions_include_model_and_explicit_effort(self) -> None:
        config = {
            "editions": {
                "claude-code": {
                    "roles": {
                        "implementer": {
                            "reasoning": {"control": "claude-code.effort", "value": "high"}
                        }
                    }
                }
            }
        }
        role = resolve_edition(config, "claude-code")["roles"]["implementer"]
        instructions = role["client_instructions"]
        self.assertIn("claude --model claude-sonnet-5-5 --effort high", instructions)
        self.assertIn("Subagents need their own model and effort settings", instructions)
        self.assertIn("Multiple ORQIVRA role preferences are advisory", instructions)

    def test_gemini_instructions_cover_auto_preview_subagents_and_routing(self) -> None:
        roles = resolve_edition({}, "gemini-cli")["roles"]
        routine = roles["implementer"]["client_instructions"]
        complex_role = roles["complex_implementer"]["client_instructions"]
        self.assertIn("gemini --model auto", routine)
        self.assertIn("choose Auto", routine)
        self.assertIn("does not set subagent models", routine)
        self.assertIn("advisory", routine)
        self.assertIn("gemini --model gemini-3.1-pro-preview", complex_role)
        self.assertIn("Preview model availability depends on account rollout and access", complex_role)
        self.assertIn("model-routing.md", complex_role)
        self.assertIn("no ORQIVRA reasoning-effort override", complex_role)

    def test_custom_identifier_is_not_inserted_into_an_executable_command(self) -> None:
        identifier = "custom-model;$(echo AUDIT_SENTINEL)"
        config = {
            "editions": {
                "claude-code": {
                    "roles": {
                        "implementer": {"model": identifier, "model_source": "user-supplied"}
                    }
                }
            }
        }
        role = resolve_edition(config, "claude-code")["roles"]["implementer"]
        instructions = role["client_instructions"]
        self.assertEqual(role["runtime_qualification"], "UNVERIFIED")
        self.assertIn("compatibility and availability are UNVERIFIED", instructions)
        self.assertNotIn(identifier, instructions)
        self.assertNotIn("claude --model", instructions)


if __name__ == "__main__":
    unittest.main()
