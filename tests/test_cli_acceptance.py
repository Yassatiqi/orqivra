"""Public behavior acceptance tests for the documented ORQIVRA CLI."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"
ZERO_HASH = "sha256:" + "0" * 64
sys.path.insert(0, str(ROOT / "src"))
from orqivra.errors import InputOutputError, OrqivraError
from orqivra.paths import digest_json
from orqivra.schema import load_json

EDITIONS = ("codex", "claude-code", "gemini-cli")
CAPABILITIES = (
    "orqivra-orchestrate",
    "orqivra-architecture",
    "orqivra-verify",
    "orqivra-recover",
)


def node(
    node_id: str,
    *,
    dependencies: list[str] | None = None,
    inputs: list[str] | None = None,
    file_scope: list[str] | None = None,
    status: str = "planned",
    attempts: int = 0,
    obligations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a public-contract DAG node with every required field."""
    result: dict[str, Any] = {
        "id": node_id,
        "objective": f"Complete the {node_id} work item.",
        "inputs": inputs or [],
        "dependencies": dependencies or [],
        "role": "implementer",
        "profile": "acceptance-profile",
        "file_scope": file_scope or [f"work/{node_id}.txt"],
        "risk": "low",
        "acceptance_criteria": [f"The {node_id} work item meets its stated objective."],
        "verification": ["Review the public result against its acceptance criterion."],
        "status": status,
        "attempts": attempts,
        "evidence": [],
        "blocking_reason": None,
    }
    if obligations is not None:
        result["obligations"] = obligations
    return result


class CliAcceptanceTests(unittest.TestCase):
    """Exercise behavior only through the documented public CLI surface."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="orqivra-acceptance-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.project = self.base / "project"
        self.project.mkdir()

    def cli(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "orqivra.cli", *arguments],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

    def require_success(self, result: subprocess.CompletedProcess[str]) -> None:
        self.assertEqual(
            result.returncode,
            0,
            f"Expected CLI success; stdout={result.stdout!r}, stderr={result.stderr!r}",
        )

    def test_json_contract_rejects_duplicates_fractions_and_unsafe_integers(self) -> None:
        cases = (
            '{"value": 1, "value": 2}',
            '{"value": 1.5}',
            '{"value": 9007199254740992}',
            '{"value": NaN}',
        )
        for index, content in enumerate(cases):
            with self.subTest(content=content):
                path = self.base / f"invalid-json-{index}.json"
                path.write_text(content, encoding="utf-8")
                with self.assertRaises(OrqivraError):
                    load_json(path)

        with self.assertRaises(InputOutputError):
            load_json(self.base / "missing.json")

    def test_canonical_json_hash_matches_the_node_golden_value(self) -> None:
        self.assertEqual(
            digest_json({"z": 1, "a": "é"}),
            "fb64e573f7cde5b7efeda52ffc4bdd57572055b0b7e64a70172606c82c6c7eac",
        )

    def write_dag(
        self,
        name: str,
        nodes: list[dict[str, Any]],
        *,
        obligations: list[dict[str, Any]] | None = None,
    ) -> Path:
        dag: dict[str, Any] = {
            "schema_version": 1,
            "id": name,
            "objective": f"Acceptance scenario for {name}.",
            "input_snapshot": ZERO_HASH,
            "nodes": nodes,
        }
        if obligations is not None:
            dag["obligations"] = obligations
        path = self.base / f"{name}.json"
        path.write_text(json.dumps(dag, indent=2) + "\n", encoding="utf-8")
        return path

    def init_state(self, dag: Path, name: str = "state.json") -> Path:
        state = self.base / name
        self.require_success(
            self.cli(
                "state",
                "init",
                str(dag),
                "--state",
                str(state),
                "--project-root",
                str(self.project),
            )
        )
        return state

    def read_state(self, state: Path) -> dict[str, Any]:
        return json.loads(state.read_text(encoding="utf-8"))

    def transition(
        self,
        state: Path,
        node_id: str,
        status: str,
        reason: str,
        *,
        expected: int = 0,
    ) -> subprocess.CompletedProcess[str]:
        result = self.cli(
            "state",
            "transition",
            "--state",
            str(state),
            node_id,
            "--to",
            status,
            "--reason",
            reason,
        )
        self.assertEqual(
            result.returncode,
            expected,
            f"Unexpected transition result; stdout={result.stdout!r}, stderr={result.stderr!r}",
        )
        return result

    def accept_node(
        self,
        state: Path,
        node_id: str,
        *,
        hypothesis: str | None = None,
        artifact: str | None = None,
    ) -> None:
        """Complete a positive workflow using only documented transitions."""
        self.prepare_node_for_acceptance(state, node_id, hypothesis=hypothesis, artifact=artifact)
        self.transition(state, node_id, "accepted", "Verification and evidence are current")

    def prepare_node_for_acceptance(
        self,
        state: Path,
        node_id: str,
        *,
        hypothesis: str | None = None,
        artifact: str | None = None,
    ) -> None:
        """Record a passing attempt and evidence without accepting the node."""
        self.transition(state, node_id, "ready", "All prerequisites are accepted")
        self.transition(state, node_id, "running", "Begin implementation")
        self.require_success(
            self.cli(
                "attempt",
                "begin",
                "--state",
                str(state),
                node_id,
                "--hypothesis",
                hypothesis or f"The stated objective can be met for {node_id}.",
            )
        )
        self.transition(state, node_id, "verifying", "Implementation is ready for verification")
        self.require_success(
            self.cli(
                "attempt",
                "verify",
                "--state",
                str(state),
                node_id,
                "--attempt",
                "1",
                "--result",
                "pass",
                "--summary",
                "The public acceptance criterion passed.",
            )
        )
        evidence_args = [
            "evidence",
            "add",
            "--state",
            str(state),
            node_id,
            "--command",
            "recorded verification observation",
            "--exit-code",
            "0",
        ]
        if artifact is not None:
            artifact_path = self.project / artifact
            artifact_path.parent.mkdir(parents=True, exist_ok=True)
            if not artifact_path.exists():
                artifact_path.write_text("verified artifact\n", encoding="utf-8")
            evidence_args.extend(["--artifact", artifact])
        self.require_success(self.cli(*evidence_args))

    def test_help_and_example_dags_are_publicly_usable(self) -> None:
        help_result = self.cli("--help")
        self.require_success(help_result)
        self.assertIn("validate", help_result.stdout.lower())
        self.assertIn("resume", help_result.stdout.lower())

        for example in sorted(EXAMPLES.glob("*.json")):
            with self.subTest(example=example.name):
                result = self.cli("validate", "dag", str(example))
                self.require_success(result)

    def test_plan_frontier_is_lexical_and_deterministic(self) -> None:
        dag = self.write_dag(
            "frontier",
            [
                node("zeta", file_scope=["zeta.txt"]),
                node("alpha", file_scope=["alpha.txt"]),
                node("middle", file_scope=["middle.txt"]),
                node("later", dependencies=["alpha"], file_scope=["later.txt"]),
            ],
        )
        first = self.cli("plan", str(dag))
        second = self.cli("plan", str(dag))
        self.require_success(first)
        self.require_success(second)
        self.assertEqual(first.stdout, second.stdout, "The same plan should produce the same frontier")
        frontier = first.stdout
        self.assertLess(frontier.index("alpha"), frontier.index("middle"))
        self.assertLess(frontier.index("middle"), frontier.index("zeta"))
        self.assertNotIn("later", frontier, "A node with an unaccepted dependency is not READY")

    def test_plan_rejects_cycles_missing_dependencies_and_scope_conflicts(self) -> None:
        scenarios = {
            "cycle": [
                node("first", dependencies=["second"], file_scope=["first.txt"]),
                node("second", dependencies=["first"], file_scope=["second.txt"]),
            ],
            "missing-dependency": [node("first", dependencies=["unknown"], file_scope=["first.txt"])],
            "duplicate-scope": [
                node("first", file_scope=["shared/file.txt"]),
                node("second", file_scope=["shared/file.txt"]),
            ],
            "ancestor-scope": [
                node("first", file_scope=["shared/**"]),
                node("second", file_scope=["shared/file.txt"]),
            ],
        }
        for name, nodes in scenarios.items():
            with self.subTest(scenario=name):
                dag = self.write_dag(name, nodes)
                result = self.cli("plan", str(dag))
                self.assertEqual(
                    result.returncode,
                    2,
                    f"Expected invalid DAG rejection; stdout={result.stdout!r}, stderr={result.stderr!r}",
                )

    def test_plan_rejects_absolute_and_parent_traversal_scopes(self) -> None:
        unsafe_scopes = [str((self.base / "outside.txt").resolve()), "../outside.txt"]
        for index, scope in enumerate(unsafe_scopes):
            with self.subTest(scope=scope):
                dag = self.write_dag(f"unsafe-path-{index}", [node("work", file_scope=[scope])])
                result = self.cli("plan", str(dag))
                self.assertEqual(
                    result.returncode,
                    4,
                    f"Expected unsafe project path rejection; stdout={result.stdout!r}, stderr={result.stderr!r}",
                )

    def test_state_transition_rejects_illegal_edges_without_mutating_state(self) -> None:
        dag = self.write_dag("illegal-edge", [node("task")])
        state = self.init_state(dag)
        before = self.read_state(state)
        self.transition(state, "task", "accepted", "Skip required work", expected=2)
        after = self.read_state(state)
        self.assertEqual(after["nodes"]["task"]["status"], "planned")
        self.assertEqual(after["version"], before["version"], "A rejected transition must not write state")

    def test_successful_verification_and_current_evidence_allow_acceptance(self) -> None:
        dag = self.write_dag("positive-workflow", [node("task")])
        state = self.init_state(dag)
        initialized = self.read_state(state)
        self.assertRegex(initialized["plan_hash"], r"^[0-9a-f]{64}$")
        self.assertRegex(initialized["plan_header_hash"], r"^[0-9a-f]{64}$")
        self.assertRegex(initialized["nodes"]["task"]["definition_hash"], r"^[0-9a-f]{64}$")
        self.accept_node(state, "task", artifact="result.txt")
        result = self.cli("evidence", "check", "--state", str(state))
        self.require_success(result)
        saved = self.read_state(state)
        self.assertEqual(saved["nodes"]["task"]["status"], "accepted")
        self.assertEqual(len(saved["nodes"]["task"]["attempts"]), 1)
        self.assertEqual(saved["nodes"]["task"]["attempts"][0]["verification_result"], "pass")

    def test_missing_evidence_and_failed_verification_cannot_be_accepted(self) -> None:
        dag = self.write_dag("missing-evidence", [node("task")])
        state = self.init_state(dag)
        self.transition(state, "task", "ready", "No dependencies")
        self.transition(state, "task", "running", "Begin work")
        self.require_success(
            self.cli("attempt", "begin", "--state", str(state), "task", "--hypothesis", "Test the requirement")
        )
        self.transition(state, "task", "verifying", "Check the result")
        self.require_success(
            self.cli(
                "attempt",
                "verify",
                "--state",
                str(state),
                "task",
                "--attempt",
                "1",
                "--result",
                "pass",
                "--summary",
                "The check passed but evidence was not recorded.",
            )
        )
        self.transition(state, "task", "accepted", "Acceptance without evidence is invalid", expected=2)
        self.assertEqual(self.read_state(state)["nodes"]["task"]["status"], "verifying")

        failed_dag = self.write_dag("failed-verification", [node("task")])
        failed_state = self.init_state(failed_dag, "failed-state.json")
        self.transition(failed_state, "task", "ready", "No dependencies")
        self.transition(failed_state, "task", "running", "Begin work")
        self.require_success(
            self.cli(
                "attempt",
                "begin",
                "--state",
                str(failed_state),
                "task",
                "--hypothesis",
                "The expected result is reachable.",
            )
        )
        self.transition(failed_state, "task", "verifying", "Check the result")
        self.require_success(
            self.cli(
                "attempt",
                "verify",
                "--state",
                str(failed_state),
                "task",
                "--attempt",
                "1",
                "--result",
                "fail",
                "--summary",
                "The check failed.",
            )
        )
        self.require_success(self.cli("evidence", "add", "--state", str(failed_state), "task", "--command", "recorded failing check", "--exit-code", "1"))
        self.transition(failed_state, "task", "accepted", "A failed check is not acceptable", expected=2)
        self.assertEqual(self.read_state(failed_state)["nodes"]["task"]["status"], "verifying")

    def test_correction_requires_a_new_hypothesis_and_sixth_attempt_is_rejected(self) -> None:
        dag = self.write_dag("attempt-limit", [node("task")])
        state = self.init_state(dag)
        for attempt_number in range(1, 6):
            self.transition(state, "task", "ready", f"Prepare attempt {attempt_number}")
            self.transition(state, "task", "running", f"Start attempt {attempt_number}")
            self.require_success(
                self.cli(
                    "attempt",
                    "begin",
                    "--state",
                    str(state),
                    "task",
                    "--hypothesis",
                    f"Hypothesis {attempt_number} explains the current failure.",
                )
            )
            self.transition(state, "task", "verifying", f"Verify attempt {attempt_number}")
            self.require_success(
                self.cli(
                    "attempt",
                    "verify",
                    "--state",
                    str(state),
                    "task",
                    "--attempt",
                    str(attempt_number),
                    "--result",
                    "fail",
                    "--summary",
                    f"Attempt {attempt_number} did not satisfy the criterion.",
                )
            )
            self.transition(state, "task", "fix_required", f"Attempt {attempt_number} needs correction")
            self.require_success(
                self.cli(
                    "attempt",
                    "diagnose",
                    "--state",
                    str(state),
                    "task",
                    "--attempt",
                    str(attempt_number),
                    "--diagnosis",
                    f"Diagnosis {attempt_number} identifies a distinct cause.",
                )
            )
            if attempt_number < 5:
                self.require_success(
                    self.cli(
                        "attempt",
                        "record-change",
                        "--state",
                        str(state),
                        "task",
                        "--attempt",
                        str(attempt_number),
                        "--summary",
                        f"Correction {attempt_number} addresses its diagnosis.",
                    )
                )
        self.transition(state, "task", "ready", "Attempt ceiling boundary")
        self.transition(state, "task", "running", "Attempt ceiling boundary")
        rejected = self.cli(
            "attempt",
            "begin",
            "--state",
            str(state),
            "task",
            "--hypothesis",
            "This sixth hypothesis must be rejected.",
        )
        self.assertEqual(rejected.returncode, 2, f"Expected five-attempt limit; stderr={rejected.stderr!r}")
        attempts = self.read_state(state)["nodes"]["task"]["attempts"]
        self.assertEqual(len(attempts), 5, "A rejected sixth attempt must not increment the counter")
        self.assertEqual([entry["number"] for entry in attempts], [1, 2, 3, 4, 5])

    def test_resume_preserves_attempt_counter_after_interruption(self) -> None:
        dag = self.write_dag("interrupted", [node("task")])
        state = self.init_state(dag)
        self.transition(state, "task", "ready", "No dependencies")
        self.transition(state, "task", "running", "Work began before interruption")
        self.require_success(
            self.cli(
                "attempt",
                "begin",
                "--state",
                str(state),
                "task",
                "--hypothesis",
                "The observed failure comes from a missing delimiter.",
            )
        )
        self.require_success(
            self.cli(
                "resume",
                "--dag",
                str(dag),
                "--state",
                str(state),
                "--project-root",
                str(self.project),
            )
        )
        saved = self.read_state(state)
        self.assertEqual(len(saved["nodes"]["task"]["attempts"]), 1)
        self.assertEqual(saved["nodes"]["task"]["attempts"][0]["number"], 1)

    def test_manual_obsoletion_invalidates_descendants_and_resume_reopens_them(self) -> None:
        dag = self.write_dag(
            "manual-obsoletion",
            [node("base"), node("dependent", dependencies=["base"])],
        )
        state = self.init_state(dag)
        self.accept_node(state, "base")
        self.accept_node(state, "dependent")

        self.transition(state, "base", "obsolete", "A fresh implementation is required")

        invalidated = self.read_state(state)
        self.assertEqual(invalidated["nodes"]["base"]["status"], "obsolete")
        self.assertEqual(invalidated["nodes"]["dependent"]["status"], "obsolete")
        self.assertEqual(invalidated["pending_resume"], ["base", "dependent"])
        resumed = self.cli(
            "resume",
            "--dag",
            str(dag),
            "--state",
            str(state),
            "--project-root",
            str(self.project),
        )

        self.require_success(resumed)
        reopened = self.read_state(state)
        self.assertEqual(reopened["nodes"]["base"]["status"], "ready")
        self.assertEqual(reopened["nodes"]["dependent"]["status"], "planned")
        self.assertEqual(reopened["pending_resume"], [])

    def test_manual_obsoletion_interrupts_active_attempt_and_requires_diagnosis(self) -> None:
        dag = self.write_dag("manual-obsolete-active", [node("task")])
        state = self.init_state(dag)
        self.transition(state, "task", "ready", "No dependencies")
        self.transition(state, "task", "running", "Work began")
        self.require_success(
            self.cli(
                "attempt",
                "begin",
                "--state",
                str(state),
                "task",
                "--hypothesis",
                "The current attempt needs a controlled restart.",
            )
        )
        self.transition(state, "task", "verifying", "Verification was about to begin")

        self.transition(state, "task", "obsolete", "The active attempt must be stopped")

        interrupted = self.read_state(state)
        self.assertEqual(interrupted["nodes"]["task"]["status"], "obsolete")
        self.assertEqual(interrupted["nodes"]["task"]["attempts"][0]["verification_result"], "interrupted")
        self.assertEqual(interrupted["pending_resume"], ["task"])
        resumed = self.cli(
            "resume",
            "--dag",
            str(dag),
            "--state",
            str(state),
            "--project-root",
            str(self.project),
        )

        self.require_success(resumed)
        reopened = self.read_state(state)
        self.assertEqual(reopened["nodes"]["task"]["status"], "fix_required")
        self.assertEqual(reopened["nodes"]["task"]["attempts"][0]["verification_result"], "interrupted")
        self.require_success(
            self.cli(
                "attempt",
                "diagnose",
                "--state",
                str(state),
                "task",
                "--attempt",
                "1",
                "--diagnosis",
                "The interrupted verification must be replaced with a new evidence pass.",
            )
        )
        self.transition(state, "task", "ready", "Resume after diagnosing the interrupted attempt")

    def test_acceptance_rejects_artifact_changed_after_evidence_recording(self) -> None:
        dag = self.write_dag("artifact-before-acceptance", [node("task")])
        state = self.init_state(dag)
        self.prepare_node_for_acceptance(state, "task", artifact="result.txt")
        (self.project / "result.txt").write_text("changed after evidence\n", encoding="utf-8")
        before = self.read_state(state)

        self.transition(state, "task", "accepted", "Artifact changed after verification", expected=2)

        after = self.read_state(state)
        self.assertEqual(after["nodes"]["task"]["status"], "verifying")
        self.assertEqual(after["version"], before["version"], "Rejected acceptance must not write state")

    def test_acceptance_rejects_input_changed_after_evidence_recording(self) -> None:
        source = self.project / "source.txt"
        source.write_text("source v1\n", encoding="utf-8")
        dag = self.write_dag("input-before-acceptance", [node("task", inputs=["source.txt"])])
        state = self.init_state(dag)
        self.prepare_node_for_acceptance(state, "task")
        source.write_text("source v2\n", encoding="utf-8")
        before = self.read_state(state)

        self.transition(state, "task", "accepted", "Input changed after verification", expected=2)

        after = self.read_state(state)
        self.assertEqual(after["nodes"]["task"]["status"], "verifying")
        self.assertEqual(after["version"], before["version"], "Rejected acceptance must not write state")

    def test_report_does_not_certify_stale_artifact_without_evidence_check(self) -> None:
        dag = self.write_dag("stale-artifact-report", [node("task")])
        state = self.init_state(dag)
        self.accept_node(state, "task", artifact="result.txt")
        (self.project / "result.txt").write_text("changed after acceptance\n", encoding="utf-8")

        report = self.cli("report", "--state", str(state), "--format", "json")

        self.require_success(report)
        data = json.loads(report.stdout)
        self.assertFalse(data["certified"])
        self.assertEqual(data["stale_evidence"][0]["reason"], "artifact_changed")
        self.assertEqual(data["accepted_without_current_evidence"], ["task"])
        self.assertEqual(self.read_state(state)["nodes"]["task"]["status"], "accepted", "Reporting must remain read-only")

        markdown = self.cli("report", "--state", str(state), "--format", "markdown")
        self.require_success(markdown)
        self.assertIn("## Stale evidence\n\n- `task/", markdown.stdout)
        self.assertIn("## Accepted nodes without current evidence\n\n- `task`", markdown.stdout)

    def test_report_does_not_certify_changed_input_without_evidence_check(self) -> None:
        source = self.project / "source.txt"
        source.write_text("source v1\n", encoding="utf-8")
        dag = self.write_dag("changed-input-report", [node("task", inputs=["source.txt"])])
        state = self.init_state(dag)
        self.accept_node(state, "task")
        source.write_text("source v2\n", encoding="utf-8")

        report = self.cli("report", "--state", str(state), "--format", "json")

        self.require_success(report)
        data = json.loads(report.stdout)
        self.assertFalse(data["certified"])
        self.assertEqual(data["changed_inputs"], ["source.txt"])
        self.assertEqual(data["stale_evidence"][0]["reason"], "input_changed")
        self.assertEqual(data["accepted_without_current_evidence"], ["task"])

        markdown = self.cli("report", "--state", str(state), "--format", "markdown")
        self.require_success(markdown)
        self.assertIn("## Changed inputs\n\n- `source.txt`", markdown.stdout)
        self.assertIn("## Accepted nodes without current evidence\n\n- `task`", markdown.stdout)

    def test_new_current_evidence_supersedes_stale_history_after_recovery(self) -> None:
        dag = self.write_dag("stale-history-recovery", [node("task")])
        state = self.init_state(dag)
        self.accept_node(state, "task", artifact="result.txt")
        (self.project / "result.txt").write_text("changed before recovery\n", encoding="utf-8")
        self.require_success(self.cli("evidence", "check", "--state", str(state)))
        self.assertEqual(self.read_state(state)["nodes"]["task"]["status"], "obsolete")
        self.require_success(
            self.cli(
                "resume",
                "--dag",
                str(dag),
                "--state",
                str(state),
                "--project-root",
                str(self.project),
            )
        )

        self.transition(state, "task", "running", "Resume the affected node")
        self.require_success(
            self.cli(
                "attempt",
                "begin",
                "--state",
                str(state),
                "task",
                "--hypothesis",
                "A corrected output and a new verification will replace the stale evidence.",
            )
        )
        self.transition(state, "task", "verifying", "Verify the recovered output")
        self.require_success(
            self.cli(
                "attempt",
                "verify",
                "--state",
                str(state),
                "task",
                "--attempt",
                "2",
                "--result",
                "pass",
                "--summary",
                "The recovered output passed verification.",
            )
        )
        (self.project / "result.txt").write_text("verified artifact after recovery\n", encoding="utf-8")
        self.require_success(
            self.cli(
                "evidence",
                "add",
                "--state",
                str(state),
                "task",
                "--command",
                "verify recovered artifact",
                "--exit-code",
                "0",
                "--artifact",
                "result.txt",
            )
        )
        self.transition(state, "task", "accepted", "Recovered evidence is current")

        self.require_success(self.cli("evidence", "check", "--state", str(state)))
        report = self.cli("report", "--state", str(state), "--format", "json")

        self.require_success(report)
        data = json.loads(report.stdout)
        self.assertTrue(data["certified"])
        self.assertEqual(data["stale_evidence"], [])
        self.assertEqual(data["superseded_stale_evidence"][0]["reason"], "artifact_changed")

        markdown = self.cli("report", "--state", str(state), "--format", "markdown")
        self.require_success(markdown)
        self.assertIn("## Superseded stale evidence\n\n- `task/", markdown.stdout)

    def test_changed_inputs_invalidate_only_affected_acceptance(self) -> None:
        (self.project / "alpha.txt").write_text("alpha v1\n", encoding="utf-8")
        (self.project / "beta.txt").write_text("beta v1\n", encoding="utf-8")
        dag = self.write_dag(
            "changed-inputs",
            [
                node("alpha-work", inputs=["alpha.txt"], file_scope=["alpha-output.txt"]),
                node("beta-work", inputs=["beta.txt"], file_scope=["beta-output.txt"]),
                node(
                    "alpha-integration",
                    dependencies=["alpha-work"],
                    inputs=["alpha.txt"],
                    file_scope=["integration-output.txt"],
                ),
            ],
        )
        state = self.init_state(dag)
        self.accept_node(state, "alpha-work")
        self.accept_node(state, "beta-work")
        self.accept_node(state, "alpha-integration")
        (self.project / "alpha.txt").write_text("alpha v2\n", encoding="utf-8")
        self.require_success(self.cli("evidence", "check", "--state", str(state)))
        after_check = self.read_state(state)
        self.assertEqual(after_check["nodes"]["alpha-work"]["status"], "obsolete")
        self.assertEqual(after_check["nodes"]["alpha-integration"]["status"], "obsolete")
        self.assertEqual(after_check["nodes"]["beta-work"]["status"], "accepted")
        self.transition(state, "alpha-work", "ready", "Only resume may reopen obsolete work", expected=2)

        self.require_success(
            self.cli(
                "resume",
                "--dag",
                str(dag),
                "--state",
                str(state),
                "--project-root",
                str(self.project),
            )
        )
        resumed = self.read_state(state)
        self.assertNotEqual(resumed["nodes"]["alpha-work"]["status"], "accepted")
        self.assertNotEqual(resumed["nodes"]["alpha-integration"]["status"], "accepted")
        self.assertEqual(resumed["nodes"]["beta-work"]["status"], "accepted")
        for node_id in ("alpha-work", "beta-work", "alpha-integration"):
            self.assertEqual(len(resumed["nodes"][node_id]["attempts"]), 1)

    def test_stale_artifact_invalidates_acceptance_and_recorded_command_is_not_run(self) -> None:
        dag = self.write_dag("stale-artifact", [node("task")])
        state = self.init_state(dag)
        marker = self.project / "must-not-exist.txt"
        self.accept_node(state, "task", artifact="result.txt")
        self.require_success(
            self.cli(
                "evidence",
                "add",
                "--state",
                str(state),
                "task",
                "--command",
                f"create {marker}",
                "--exit-code",
                "0",
                "--artifact",
                "result.txt",
            )
        )
        self.assertFalse(marker.exists(), "Evidence command text must be recorded, never executed")
        (self.project / "result.txt").write_text("changed after evidence\n", encoding="utf-8")
        self.require_success(self.cli("evidence", "check", "--state", str(state)))
        saved = self.read_state(state)
        self.assertEqual(saved["nodes"]["task"]["status"], "obsolete")
        self.assertFalse(marker.exists(), "Evidence checking must not execute recorded command text")

    def test_required_deferred_gate_blocks_final_certification(self) -> None:
        gate = {
            "id": "external-runtime-check",
            "description": "Exercise the named external client in its supported runtime.",
            "required": True,
            "status": "DEFERRED_EXTERNAL",
            "evidence": [],
        }
        dag = self.write_dag("deferred-gate", [node("component", obligations=[gate])])
        self.require_success(self.cli("validate", "dag", str(dag)))
        state = self.init_state(dag)
        self.accept_node(state, "component")
        report = self.cli("report", "--state", str(state), "--format", "json")
        self.require_success(report)
        serialized = json.dumps(json.loads(report.stdout), sort_keys=True)
        self.assertIn("DEFERRED_EXTERNAL", serialized)
        self.assertNotIn('"certified": true', serialized.lower())

    def test_concurrent_state_writes_do_not_corrupt_or_lose_events(self) -> None:
        dag = self.write_dag("concurrent", [node("task")])
        state = self.init_state(dag)
        self.transition(state, "task", "ready", "No dependencies")
        before = self.read_state(state)
        start = threading.Barrier(3)
        results: list[subprocess.CompletedProcess[str]] = []

        def write_transition(target: str) -> None:
            start.wait()
            results.append(
                self.cli(
                    "state",
                    "transition",
                    "--state",
                    str(state),
                    "task",
                    "--to",
                    target,
                    "--reason",
                    f"Concurrent request to {target}",
                )
            )

        writers = [threading.Thread(target=write_transition, args=(status,)) for status in ("running", "blocked")]
        for writer in writers:
            writer.start()
        start.wait()
        for writer in writers:
            writer.join()
        self.assertTrue(all(result.returncode in (0, 2, 3) for result in results))
        self.assertTrue(any(result.returncode == 0 for result in results), "At least one writer should commit")
        saved = self.read_state(state)
        self.assertIn(saved["nodes"]["task"]["status"], {"running", "blocked"})
        successful_writes = sum(result.returncode == 0 for result in results)
        self.assertEqual(saved["version"], before["version"] + successful_writes)
        self.assertEqual(len(saved["events"]), len(before["events"]) + successful_writes)

    def test_symlinked_project_scope_is_rejected(self) -> None:
        outside = self.base / "outside"
        outside.mkdir()
        (outside / "source.txt").write_text("outside project data\n", encoding="utf-8")
        link = self.project / "linked-directory"
        try:
            link.symlink_to(outside, target_is_directory=True)
        except (OSError, NotImplementedError) as error:
            self.skipTest(f"This Windows account cannot create a symlink: {error}")
        dag = self.write_dag("symlink-scope", [node("task", file_scope=["linked-directory/source.txt"])])
        project_file = self.base / "project.json"
        project_file.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "id": "symlink-project",
                    "name": "Symlink acceptance project",
                    "root": str(self.project),
                    "inputs": [],
                    "profile": "acceptance-profile",
                }
            ),
            encoding="utf-8",
        )
        result = self.cli("validate", "dag", str(dag), "--project", str(project_file))
        self.assertEqual(
            result.returncode,
            4,
            f"Expected symlink path rejection; stdout={result.stdout!r}, stderr={result.stderr!r}",
        )
        install_target = self.base / "unsafe-install-target"
        install_target.symlink_to(outside, target_is_directory=True)
        unsafe_install = self.cli(
            "install",
            "--edition",
            "codex",
            "--target",
            str(install_target),
            "--skill",
            "orqivra-orchestrate",
            "--apply",
        )
        self.assertEqual(
            unsafe_install.returncode,
            4,
            f"Expected unsafe installation root rejection; stdout={unsafe_install.stdout!r}, stderr={unsafe_install.stderr!r}",
        )
        self.assertEqual(list(outside.iterdir()), [outside / "source.txt"], "Unsafe install must not write through a symlink")

    def test_cross_edition_builds_share_capability_set_and_contract_content(self) -> None:
        per_edition: dict[str, dict[str, str]] = {}
        expected_terms = {
            "orqivra-orchestrate": ("solo", "delegate", "audit", "full"),
            "orqivra-architecture": ("inputs", "outputs", "invariants"),
            "orqivra-verify": ("independent", "deferred_external"),
            "orqivra-recover": ("hypothesis", "five"),
        }
        for edition in EDITIONS:
            output = self.base / f"build-{edition}"
            self.require_success(self.cli("build", "--edition", edition, "--output", str(output)))
            self.require_success(self.cli("validate", "skills", str(output)))
            skills: dict[str, str] = {}
            for skill_file in output.rglob("SKILL.md"):
                skills[skill_file.parent.name] = skill_file.read_text(encoding="utf-8").lower()
            self.assertTrue(skills, f"The {edition} build should contain client skills")
            for skill_name, terms in expected_terms.items():
                self.assertIn(skill_name, skills, f"The {edition} build is missing {skill_name}")
                for term in terms:
                    self.assertIn(term, skills[skill_name], f"{edition} {skill_name} lacks {term}")
            per_edition[edition] = skills
        expected_names = set(per_edition[EDITIONS[0]])
        for edition in EDITIONS[1:]:
            self.assertEqual(
                set(per_edition[edition]),
                expected_names,
                f"Edition {edition} should expose the same shared capability set",
            )

    def test_selective_installation_modified_destination_and_limited_uninstall(self) -> None:
        target = self.base / "selected-install"
        default_run = self.cli(
            "install",
            "--edition",
            "codex",
            "--target",
            str(target),
            "--skill",
            "orqivra-orchestrate",
        )
        self.require_success(default_run)
        self.assertFalse(target.exists() and any(target.iterdir()), "Install must default to a dry run")
        dry_run = self.cli(
            "install",
            "--edition",
            "codex",
            "--target",
            str(target),
            "--skill",
            "orqivra-orchestrate",
            "--dry-run",
        )
        self.require_success(dry_run)
        self.assertFalse(target.exists() and any(target.iterdir()), "A dry run must not write target files")

        install = self.cli(
            "install",
            "--edition",
            "codex",
            "--target",
            str(target),
            "--skill",
            "orqivra-orchestrate",
            "--apply",
        )
        self.require_success(install)
        files = sorted(path for path in target.rglob("*") if path.is_file())
        self.assertTrue(files, "An installation request should create selected skill files")
        manifest_candidates = [path for path in files if "manifest" in path.name.lower()]
        self.assertTrue(manifest_candidates, "An installation should record its owned files in a manifest")
        installed_files = [path for path in files if path not in manifest_candidates]
        self.assertTrue(installed_files, "The selected capability should install at least one owned file")
        for path in installed_files:
            components = {part.lower() for part in path.relative_to(target).parts}
            self.assertIn("orqivra-orchestrate", components)
            self.assertFalse(components.intersection(set(CAPABILITIES) - {"orqivra-orchestrate"}))

        self.require_success(self.cli("verify-install", "--target", str(target)))
        changed = installed_files[0]
        original = changed.read_bytes()
        changed.write_bytes(original + b"user modification\n")
        refused = self.cli(
            "install",
            "--edition",
            "codex",
            "--target",
            str(target),
            "--skill",
            "orqivra-orchestrate",
            "--apply",
        )
        self.assertNotEqual(refused.returncode, 0, "Installation must refuse a modified owned destination")
        modified_bytes = changed.read_bytes()
        self.assertEqual(modified_bytes, original + b"user modification\n")
        invalid_verification = self.cli("verify-install", "--target", str(target))
        self.assertNotEqual(invalid_verification.returncode, 0, "Install verification must refuse a modified owned file")
        refused_uninstall = self.cli("uninstall", "--target", str(target), "--apply")
        self.assertNotEqual(refused_uninstall.returncode, 0, "Uninstall must refuse a modified owned file")
        self.assertEqual(changed.read_bytes(), modified_bytes)

        clean_target = self.base / "clean-install"
        clean_install = self.cli(
            "install",
            "--edition",
            "codex",
            "--target",
            str(clean_target),
            "--skill",
            "orqivra-orchestrate",
            "--apply",
        )
        self.require_success(clean_install)
        unrelated = clean_target / "unrelated-user-file.txt"
        unrelated.write_text("keep this file\n", encoding="utf-8")
        uninstall = self.cli("uninstall", "--target", str(clean_target), "--apply")
        self.require_success(uninstall)
        self.assertEqual(unrelated.read_text(encoding="utf-8"), "keep this file\n")
        self.assertEqual(
            [path for path in clean_target.rglob("*") if path.is_file()],
            [unrelated],
            "Uninstall should remove only manifest-owned files and keep unrelated files",
        )

    def test_install_refuses_to_overwrite_an_existing_temporary_path(self) -> None:
        target = self.base / "temporary-collision"
        temporary_file = target / "orqivra-orchestrate" / "SKILL.md.orqivra-tmp"
        temporary_file.parent.mkdir(parents=True)
        temporary_file.write_text("preserve user data\n", encoding="utf-8")

        result = self.cli(
            "install",
            "--edition",
            "codex",
            "--target",
            str(target),
            "--skill",
            "orqivra-orchestrate",
            "--apply",
        )

        self.assertEqual(result.returncode, 2, f"Expected a temporary-path collision to be refused: {result.stderr!r}")
        self.assertEqual(temporary_file.read_text(encoding="utf-8"), "preserve user data\n")
        self.assertFalse((target / "orqivra-orchestrate" / "SKILL.md").exists())
        self.assertFalse((target / ".orqivra-manifest.json").exists())


if __name__ == "__main__":
    unittest.main()
