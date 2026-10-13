from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "orqivra-orchestrate" / "SKILL.md"
EXPORT = ROOT / "docs" / "online-llm-context.md"
START = "<!-- PORTABLE_METHOD_START -->"
END = "<!-- PORTABLE_METHOD_END -->"


class PortableContextTests(unittest.TestCase):
    def test_export_is_the_canonical_skill_section(self):
        source = SKILL.read_text(encoding="utf-8")
        self.assertEqual(source.count(START), 1)
        self.assertEqual(source.count(END), 1)
        start = source.index(START) + len(START)
        end = source.index(END)
        self.assertGreater(end, start)
        expected = source[start:end].strip() + "\n"
        self.assertEqual(EXPORT.read_text(encoding="utf-8"), expected)

    def test_export_keeps_activation_and_capability_limits(self):
        exported = EXPORT.read_text(encoding="utf-8")
        for required in (
            "### Copyable activation message",
            "A generated assistant prompt must include the relevant method and task-specific approval gate",
            "If CLI, files, workers, or model controls are unavailable",
            "Delegate only with available workers, authorization, independent tasks, and disjoint scopes",
            "Allow at most five attempts per task",
            "Skipped, unavailable, configured, or queued is not a pass",
        ):
            with self.subTest(required=required):
                self.assertIn(required, exported)

    def test_export_is_generic_and_contains_no_local_configuration(self):
        exported = EXPORT.read_text(encoding="utf-8").lower()
        for excluded in (
            "orqivra.config.json",
            "gpt-6-",
            "claude-sonnet-",
            "gemini-3.",
            "c:\\users\\",
            "api_key",
        ):
            with self.subTest(excluded=excluded):
                self.assertNotIn(excluded, exported)


if __name__ == "__main__":
    unittest.main()
