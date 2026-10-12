"""Focused regression tests for symlink and junction path protections."""

from __future__ import annotations

import os
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from orqivra.dag import plan_hashes
from orqivra.errors import OrqivraError, UnsafePathError
from orqivra.installer import install
from orqivra.paths import is_linklike, reject_symlink_components, reject_symlink_path, safe_join
from verify_windows_python311_junctions import discovery_error, execution_error, runtime_error
from orqivra.state import (
    _collect_input_hashes,
    _evidence_stale_reason,
    add_evidence,
    begin_attempt,
    initialize_state,
    mutate_state,
    read_state,
    resume,
    transition,
)


ZERO_HASH = "sha256:" + "0" * 64


def _node(node_id: str, inputs: list[str] | None = None) -> dict[str, object]:
    return {
        "id": node_id,
        "objective": "Exercise the path security contract.",
        "inputs": inputs or [],
        "dependencies": [],
        "role": "implementer",
        "profile": "test-profile",
        "file_scope": [f"work/{node_id}.txt"],
        "risk": "low",
        "acceptance_criteria": ["The path security check rejects unsafe roots."],
        "verification": ["Run the focused regression test."],
        "status": "planned",
        "attempts": 0,
        "evidence": [],
        "blocking_reason": None,
    }


def _write_dag(path: Path, node: dict[str, object]) -> None:
    path.write_text(
        json.dumps({
            "schema_version": 1,
            "id": "path-security-test",
            "objective": "Exercise path security.",
            "input_snapshot": ZERO_HASH,
            "nodes": [node],
        }),
        encoding="utf-8",
    )


def _directory_redirect(link: Path, target: Path, base: Path) -> None:
    if os.name == "nt":
        command_file = base / "create-root-redirect.cmd"
        command_file.write_text(
            '@echo off\r\n'
            'mklink /J "%~dp0project" "%~dp0outside"\r\n'
            'exit /b %errorlevel%\r\n',
            encoding="ascii",
        )
        command_interpreter = os.environ.get("COMSPEC", r"C:\Windows\System32\cmd.exe")
        result = subprocess.run(
            [command_interpreter, "/d", "/c", command_file.name],
            cwd=base,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0 or not link.exists():
            raise OSError(result.stderr.strip() or result.stdout.strip() or "mklink /J failed")
    else:
        link.symlink_to(target, target_is_directory=True)


class PathSecurityTests(unittest.TestCase):
    def test_input_directories_are_rejected_even_during_recovery(self) -> None:
        with tempfile.TemporaryDirectory(prefix="orqivra-input-kind-") as temporary:
            root = Path(temporary)
            (root / "existing-directory").mkdir()
            dag = {"id": "input-kind", "nodes": [{"id": "task", "inputs": ["existing-directory"]}]}
            with self.assertRaisesRegex(OrqivraError, "not a regular file"):
                plan_hashes(dag, root)
            with self.assertRaisesRegex(OrqivraError, "not a regular file"):
                plan_hashes(dag, root, allow_missing_inputs=True)

            missing = {"id": "missing-input", "nodes": [{"id": "task", "inputs": ["not-created.txt"]}]}
            self.assertEqual(plan_hashes(missing, root, allow_missing_inputs=True)[2], {})
            with self.assertRaisesRegex(OrqivraError, "does not exist"):
                plan_hashes(missing, root)

    def test_replaced_saved_project_root_is_checked_without_inputs_or_artifacts(self) -> None:
        with tempfile.TemporaryDirectory(prefix="orqivra-root-replacement-") as temporary:
            base = Path(temporary)
            root = base / "project"
            root.mkdir()
            outside = base / "outside"
            outside.mkdir()
            dag_path = base / "dag.json"
            _write_dag(dag_path, _node("task"))
            state_path = base / "state.json"
            initialize_state(dag_path, state_path, root)
            transition(state_path, "task", "ready", "Begin the root-boundary regression.")
            begin_attempt(state_path, "task", "Check the saved root before evidence collection.")

            moved_root = base / "original-project"
            root.rename(moved_root)
            try:
                _directory_redirect(root, outside, base)
            except (OSError, NotImplementedError) as error:
                self.skipTest(f"This system cannot create a directory redirect: {error}")

            state = read_state(state_path)
            with self.assertRaises(UnsafePathError):
                _collect_input_hashes(state)
            with self.assertRaises(UnsafePathError):
                _evidence_stale_reason(state, "task", {"snapshot": "stale", "artifacts": []})
            with self.assertRaises(UnsafePathError):
                add_evidence(state_path, "task", "no-op evidence command", 0, [])
            with self.assertRaises(UnsafePathError):
                resume(dag_path, state_path)

            resumed, _ = resume(dag_path, state_path, project_root=outside)
            self.assertEqual(resumed["project_root"], str(outside.resolve()))

    def test_hypothesis_duplicate_normalization_uses_nfc_lower_and_ascii_whitespace(self) -> None:
        with tempfile.TemporaryDirectory(prefix="orqivra-hypothesis-normalization-") as temporary:
            base = Path(temporary)
            root = base / "project"
            root.mkdir()
            dag_path = base / "dag.json"
            _write_dag(dag_path, _node("task"))
            state_path = base / "state.json"
            initialize_state(dag_path, state_path, root)
            transition(state_path, "task", "ready", "Begin the normalization regression.")
            begin_attempt(state_path, "task", "\tÅ\t  hypothesis\r\n")
            with self.assertRaisesRegex(OrqivraError, "new hypothesis"):
                begin_attempt(state_path, "task", "å hypothesis")

    def test_symlink_is_detected_without_following_it(self) -> None:
        with tempfile.TemporaryDirectory(prefix="orqivra-path-security-") as temporary:
            base = Path(temporary)
            target = base / "target.txt"
            target.write_text("outside the link\n", encoding="utf-8")
            link = base / "link.txt"
            try:
                link.symlink_to(target)
            except (OSError, NotImplementedError) as error:
                self.skipTest(f"This system cannot create a symlink: {error}")

            self.assertTrue(is_linklike(link))
            with self.assertRaises(UnsafePathError):
                reject_symlink_path(link)

    @unittest.skipUnless(os.name == "nt", "Windows junction regression")
    def test_real_junction_is_rejected_at_path_boundaries(self) -> None:
        with tempfile.TemporaryDirectory(prefix="orqivra-junction-security-") as temporary:
            base = Path(temporary)
            selected_root = base / "project"
            selected_root.mkdir()
            outside = base / "outside"
            outside.mkdir()
            sentinel = outside / "source.txt"
            sentinel.write_text("outside project data\n", encoding="utf-8")
            junction = selected_root / "redirected-directory"
            command_file = base / "create-junction.cmd"
            command_file.write_text(
                '@echo off\r\n'
                'mklink /J "%~dp0project\\redirected-directory" "%~dp0outside"\r\n'
                'exit /b %errorlevel%\r\n',
                encoding="ascii",
            )
            command_interpreter = os.environ.get("COMSPEC", r"C:\Windows\System32\cmd.exe")
            result = subprocess.run(
                [command_interpreter, "/d", "/c", command_file.name],
                cwd=base,
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0 or not junction.exists():
                self.skipTest(
                    "Could not create a Windows junction with mklink /J: "
                    + (result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}")
                )

            try:
                self.assertTrue(is_linklike(junction))
                with self.assertRaises(UnsafePathError):
                    reject_symlink_path(junction)
                with self.assertRaises(UnsafePathError):
                    reject_symlink_components(junction / "source.txt")
                with self.assertRaises(UnsafePathError):
                    safe_join(selected_root, "redirected-directory/source.txt")

                safe_file = selected_root / "ordinary.txt"
                self.assertEqual(safe_join(selected_root, "ordinary.txt", allow_missing=True), safe_file)
                with self.assertRaises(UnsafePathError):
                    safe_join(selected_root, "../outside/source.txt", allow_missing=True)

                install_target = junction / "installation"
                with self.assertRaises(UnsafePathError):
                    install("codex", install_target, ["orqivra-orchestrate"], apply=True)
                self.assertFalse((outside / "installation").exists())

                state_path = junction / "state.json"
                with self.assertRaises(UnsafePathError):
                    mutate_state(state_path, "test", None, {}, lambda _state: None)
                self.assertFalse((outside / "state.json").exists())
                self.assertEqual(sorted(path.name for path in outside.iterdir()), ["source.txt"])
            finally:
                if junction.exists() or junction.is_symlink():
                    junction.rmdir()


class JunctionQualificationGateTests(unittest.TestCase):
    def test_release_gate_requires_windows_python_311(self) -> None:
        self.assertIsNone(runtime_error("nt", (3, 11)))
        self.assertIn("Python 3.11", runtime_error("nt", (3, 13)) or "")
        self.assertIn("Windows", runtime_error("posix", (3, 11)) or "")

    def test_release_gate_rejects_missing_or_unloadable_junction_tests(self) -> None:
        self.assertIsNone(discovery_error([], 2, 2))
        self.assertIn("count", discovery_error([], 1, 2) or "")
        self.assertIn("ImportError", discovery_error(["ImportError: test missing"], 2, 2) or "")

    def test_release_gate_rejects_skipped_unexecuted_or_failed_junction_tests(self) -> None:
        self.assertIsNone(execution_error(2, 0, True, 2))
        self.assertIn("skipped", execution_error(2, 1, True, 2) or "")
        self.assertIn("Executed 0", execution_error(0, 0, True, 2) or "")
        self.assertIn("failed", execution_error(2, 0, False, 2) or "")


if __name__ == "__main__":
    unittest.main()
