"""Focused regression tests for symlink and junction path protections."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from orqivra.errors import UnsafePathError
from orqivra.installer import install
from orqivra.paths import is_linklike, reject_symlink_components, reject_symlink_path, safe_join
from orqivra.state import mutate_state


class PathSecurityTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
