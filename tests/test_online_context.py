from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "orqivra-orchestrate" / "SKILL.md"
EXPORT = ROOT / "docs" / "online-llm-context.md"
GENERATOR = ROOT / "tools" / "generate-online-context.mjs"
NODE = shutil.which("node")
START = "<!-- PORTABLE_METHOD_START -->"
END = "<!-- PORTABLE_METHOD_END -->"


class PortableContextTests(unittest.TestCase):
    def test_checked_in_export_matches_canonical_section_and_uses_lf(self):
        source = normalize_line_endings(SKILL.read_text(encoding="utf-8"))
        self.assertEqual(source.count(START), 1)
        self.assertEqual(source.count(END), 1)
        start = source.index(START) + len(START)
        end = source.index(END)
        self.assertGreater(end, start)
        expected = source[start:end].strip() + "\n"
        self.assertEqual(EXPORT.read_text(encoding="utf-8"), expected)
        self.assertNotIn(b"\r", EXPORT.read_bytes(), "The generated portable context must use LF bytes.")

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

    @unittest.skipUnless(NODE, "Node.js is required for generator integration tests")
    def test_generator_is_lf_deterministic_for_lf_and_crlf_fixtures(self):
        expected = "## Fixture method\n\nFirst line.\nSecond line.\n"
        for source_eol in ("\n", "\r\n"):
            for output_eol in ("\n", "\r\n"):
                with self.subTest(source_eol=repr(source_eol), output_eol=repr(output_eol)):
                    with tempfile.TemporaryDirectory(prefix="orqivra portable context fixture ") as temporary:
                        directory = Path(temporary)
                        source_path = directory / "canonical skill.md"
                        output_path = directory / "portable context.md"
                        source = source_eol.join((
                            "front matter",
                            START,
                            "## Fixture method",
                            "",
                            "First line.",
                            "Second line.",
                            END,
                            "trailer",
                        )) + source_eol
                        source_path.write_bytes(source.encode("utf-8"))
                        output_path.write_bytes(expected.replace("\n", output_eol).encode("utf-8"))

                        checked = run_generator(source_path, output_path, check=True)
                        self.assertEqual(checked.returncode, 0, checked.stderr)

                        generated = run_generator(source_path, output_path)
                        self.assertEqual(generated.returncode, 0, generated.stderr)
                        first_bytes = output_path.read_bytes()
                        self.assertEqual(first_bytes, expected.encode("utf-8"))
                        self.assertNotIn(b"\r", first_bytes)

                        repeated = run_generator(source_path, output_path)
                        self.assertEqual(repeated.returncode, 0, repeated.stderr)
                        self.assertEqual(output_path.read_bytes(), first_bytes)

    @unittest.skipUnless(NODE, "Node.js is required for generator integration tests")
    def test_check_rejects_source_and_output_content_drift(self):
        expected = "## Fixture method\n\nOriginal content.\n"
        with tempfile.TemporaryDirectory(prefix="orqivra portable context drift ") as temporary:
            directory = Path(temporary)
            source_path = directory / "canonical.md"
            output_path = directory / "export.md"
            source_path.write_text(f"{START}\n{expected}{END}\n", encoding="utf-8", newline="\n")
            output_path.write_bytes(expected.encode("utf-8"))

            output_path.write_bytes(b"## Fixture method\n\nChanged output.\n")
            output_drift = run_generator(source_path, output_path, check=True)
            self.assertNotEqual(output_drift.returncode, 0)
            self.assertIn("stale", output_drift.stderr.lower())

            output_path.write_bytes(expected.encode("utf-8"))
            source_path.write_text(f"{START}\n## Fixture method\n\nChanged source.\n{END}\n", encoding="utf-8", newline="\n")
            source_drift = run_generator(source_path, output_path, check=True)
            self.assertNotEqual(source_drift.returncode, 0)
            self.assertIn("stale", source_drift.stderr.lower())


def run_generator(source: Path, output: Path, *, check: bool = False) -> subprocess.CompletedProcess[str]:
    assert NODE is not None
    command = [NODE, str(GENERATOR), "--source", str(source), "--output", str(output)]
    if check:
        command.append("--check")
    return subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)


def normalize_line_endings(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n")


if __name__ == "__main__":
    unittest.main()
