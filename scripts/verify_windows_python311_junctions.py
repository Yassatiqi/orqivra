"""Require the Windows Python 3.11 path-security junction regressions."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path


REQUIRED_TESTS = (
    "test_path_security.PathSecurityTests.test_replaced_saved_project_root_is_checked_without_inputs_or_artifacts",
    "test_path_security.PathSecurityTests.test_real_junction_is_rejected_at_path_boundaries",
)


def runtime_error(platform_name: str, version: tuple[int, int]) -> str | None:
    if platform_name != "nt":
        return "Windows Python 3.11 is required for junction qualification."
    if version != (3, 11):
        return f"Python 3.11 is required; found {version[0]}.{version[1]}."
    return None


def discovery_error(
    loader_errors: list[str], discovered_count: int, expected_count: int
) -> str | None:
    if not loader_errors and discovered_count == expected_count:
        return None
    details = "\n".join(loader_errors) or "required test count did not match"
    return f"Could not load all required junction tests: {details}"


def execution_error(
    tests_run: int, skipped_count: int, successful: bool, expected_count: int
) -> str | None:
    if tests_run != expected_count:
        return f"Executed {tests_run} of {expected_count} required junction tests."
    if skipped_count:
        return f"{skipped_count} required junction test(s) were skipped."
    if not successful:
        return "Required Windows Python 3.11 junction qualification failed."
    return None


def main() -> int:
    error = runtime_error(os.name, tuple(sys.version_info[:2]))
    if error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2

    repository_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repository_root / "tests"))
    loader = unittest.defaultTestLoader
    suites = [loader.loadTestsFromName(name) for name in REQUIRED_TESTS]
    expected_count = len(REQUIRED_TESTS)
    discovered_count = sum(suite.countTestCases() for suite in suites)
    error = discovery_error(loader.errors, discovered_count, expected_count)
    if error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2

    required_suite = unittest.TestSuite(suites)
    result = unittest.TextTestRunner(verbosity=2).run(required_suite)
    error = execution_error(
        result.testsRun,
        len(result.skipped),
        result.wasSuccessful(),
        expected_count,
    )
    if error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print(f"Python 3.11 Windows junction qualification passed: {expected_count} required tests, 0 skips.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
