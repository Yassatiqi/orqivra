"""Black-box parity and cross-runtime interoperability checks for Python and Node."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures"
CASES_PATH = FIXTURE_ROOT / "cases.json"
EXPECTATIONS_PATH = Path(__file__).resolve().parent / "expectations.json"
NODE_CLI = ROOT / "node" / "dist" / "cli.js"


class ParityFailure(AssertionError):
    """A parity expectation did not match observed CLI behavior."""


class Harness:
    def __init__(self, python_executable: str, node_executable: str) -> None:
        self.executables = {"python": python_executable, "node": node_executable}
        self.cases: dict[str, Any] = json.loads(CASES_PATH.read_text(encoding="utf-8"))
        self.expectations: dict[str, Any] = json.loads(EXPECTATIONS_PATH.read_text(encoding="utf-8"))
        self.passed: list[str] = []
        self.skipped: list[dict[str, str]] = []

    def command(self, runtime: str, args: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
        if runtime == "python":
            command = [self.executables[runtime], "-m", "orqivra.cli", *args]
        else:
            command = [self.executables[runtime], str(NODE_CLI), *args]
        environment = os.environ.copy()
        environment.pop("ORQIVRA_DATA_DIR", None)
        source_path = str(ROOT / "src")
        existing_path = environment.get("PYTHONPATH")
        environment["PYTHONPATH"] = source_path if not existing_path else source_path + os.pathsep + existing_path
        return subprocess.run(
            command,
            cwd=cwd or ROOT,
            env=environment,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
        )

    def successful_json(self, runtime: str, args: list[str], *, cwd: Path | None = None) -> Any:
        result = self.command(runtime, args, cwd=cwd)
        if result.returncode != 0:
            raise ParityFailure(f"{runtime} command failed ({result.returncode}): {args}\n{result.stderr}")
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as error:
            raise ParityFailure(f"{runtime} command returned invalid JSON: {args}\n{result.stdout}") from error

    def expect_exit(self, runtime: str, args: list[str], exit_code: int, *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
        result = self.command(runtime, args, cwd=cwd)
        if result.returncode != exit_code:
            raise ParityFailure(
                f"{runtime} expected exit {exit_code}, got {result.returncode}: {args}\n"
                f"stdout: {result.stdout}\nstderr: {result.stderr}"
            )
        return result

    def record(self, name: str) -> None:
        self.passed.append(name)

    def run_shared_fixtures(self) -> None:
        cases = [*self.cases["validation_cases"], *self.cases["planning_cases"]]
        for case in cases:
            source = Path(case["source"])
            path = (ROOT / source) if source.parts[0] in {"profiles", "examples"} else (FIXTURE_ROOT / source)
            if case["operation"] == "validate_project":
                args = ["validate", "project", str(path)]
            elif case["operation"] == "validate_profile":
                args = ["validate", "profile", str(path)]
            elif case["operation"] == "validate_dag":
                args = ["validate", "dag", str(path)]
            elif case["operation"] == "plan":
                args = ["plan", str(path)]
            else:
                raise ParityFailure(f"Unknown fixture operation: {case['operation']}")

            responses = []
            for runtime in ("python", "node"):
                result = self.command(runtime, args)
                if result.returncode != case["exit_code"]:
                    raise ParityFailure(
                        f"{case['id']} {runtime} exit mismatch: expected {case['exit_code']}, got {result.returncode}\n"
                        f"{result.stderr}"
                    )
                if "diagnostic_contains" in case:
                    diagnostic = f"{result.stdout}\n{result.stderr}".lower()
                    if case["diagnostic_contains"] not in diagnostic or "traceback" in diagnostic:
                        raise ParityFailure(f"{case['id']} {runtime} did not return a controlled diagnostic: {diagnostic}")
                if "json" in case:
                    try:
                        data = json.loads(result.stdout)
                    except json.JSONDecodeError as error:
                        raise ParityFailure(f"{case['id']} {runtime} did not return JSON: {result.stdout}") from error
                    if data != case["json"]:
                        raise ParityFailure(f"{case['id']} {runtime} JSON mismatch: {data!r} != {case['json']!r}")
                    responses.append(data)
            if len(responses) == 2 and responses[0] != responses[1]:
                raise ParityFailure(f"{case['id']} runtimes returned different structured results")
            self.record(f"shared-fixture:{case['id']}")

    @staticmethod
    def make_node(node_id: str, dependencies: list[str], inputs: list[str], scope: str) -> dict[str, Any]:
        return {
            "id": node_id,
            "objective": f"Exercise parity node {node_id}.",
            "inputs": inputs,
            "dependencies": dependencies,
            "role": "implementer",
            "profile": "local-default",
            "file_scope": [scope],
            "risk": "low",
            "acceptance_criteria": [f"The parity assertion for {node_id} succeeds."],
            "verification": ["Run the shared black-box acceptance harness."],
            "status": "planned",
            "attempts": 0,
            "evidence": [],
            "blocking_reason": None,
        }

    def write_dag(self, directory: Path, dag_id: str, nodes: list[dict[str, Any]]) -> Path:
        path = directory / f"{dag_id}.json"
        data = {
            "schema_version": 1,
            "id": dag_id,
            "objective": f"Exercise ORQIVRA {dag_id} interoperability.",
            "input_snapshot": "sha256:" + "0" * 64,
            "nodes": nodes,
        }
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        return path

    def state_path(self, directory: Path, name: str) -> Path:
        project = directory / f"project {name}"
        project.mkdir(parents=True, exist_ok=True)
        return project / ".orqivra" / "state.json"

    def complete_node(self, runtime: str, state: Path, node_id: str, hypothesis: str, artifact: Path | None = None) -> None:
        args = ["--state", str(state), node_id]
        self.successful_json(runtime, ["state", "transition", *args, "--to", "ready", "--reason", "parity setup"])
        started = self.successful_json(runtime, ["attempt", "begin", *args, "--hypothesis", hypothesis])
        attempt_number = started["nodes"][node_id]["attempts"][-1]["number"]
        self.successful_json(runtime, ["state", "transition", *args, "--to", "verifying", "--reason", "parity verification"])
        self.successful_json(
            runtime,
            ["attempt", "verify", *args, "--attempt", str(attempt_number), "--result", "pass", "--summary", "Parity verification passed."],
        )
        evidence = ["evidence", "add", *args, "--command", "parity fixture command", "--exit-code", "0"]
        if artifact is not None:
            evidence.extend(["--artifact", str(artifact)])
        self.successful_json(runtime, evidence)
        self.successful_json(runtime, ["state", "transition", *args, "--to", "accepted", "--reason", "parity acceptance"])

    def run_state_handoff(self, directory: Path, *, initial_runtime: str) -> None:
        dag = self.write_dag(directory, f"handoff-{initial_runtime}", [self.make_node("A", [], [], "README.md")])
        state = self.state_path(directory, f"handoff-{initial_runtime}")
        opposite = "node" if initial_runtime == "python" else "python"
        self.successful_json(initial_runtime, ["state", "init", str(dag), "--state", str(state), "--project-root", str(state.parent.parent)])
        self.successful_json(opposite, ["state", "transition", "--state", str(state), "A", "--to", "ready", "--reason", "cross-runtime transition"])
        self.successful_json(initial_runtime, ["attempt", "begin", "--state", str(state), "A", "--hypothesis", "Start in one runtime and resume in the other."])
        resumed = self.successful_json(opposite, ["resume", "--dag", str(dag), "--state", str(state)])
        if resumed["affected_nodes"] != ["A"]:
            raise ParityFailure(f"Expected one interrupted A attempt, got {resumed['affected_nodes']!r}")
        current = json.loads(state.read_text(encoding="utf-8"))
        attempt = current["nodes"]["A"]["attempts"][0]
        if attempt["verification_result"] != self.expectations["interrupted_attempt_result"]:
            raise ParityFailure(f"Interrupted attempt was not preserved: {attempt!r}")
        self.successful_json(initial_runtime, ["attempt", "diagnose", "--state", str(state), "A", "--attempt", "1", "--diagnosis", "The handoff correctly preserved the unfinished attempt."])
        self.successful_json(opposite, ["state", "transition", "--state", str(state), "A", "--to", "ready", "--reason", "diagnosis recorded"])
        self.successful_json(initial_runtime, ["attempt", "begin", "--state", str(state), "A", "--hypothesis", "A distinct post-resume attempt succeeds."])
        self.successful_json(opposite, ["state", "transition", "--state", str(state), "A", "--to", "verifying", "--reason", "verification starts"])
        self.successful_json(initial_runtime, ["attempt", "verify", "--state", str(state), "A", "--attempt", "2", "--result", "pass", "--summary", "The resumed attempt passed."])
        self.successful_json(opposite, ["evidence", "add", "--state", str(state), "A", "--command", "record-only parity evidence", "--exit-code", "0"])
        self.successful_json(initial_runtime, ["state", "transition", "--state", str(state), "A", "--to", "accepted", "--reason", "current evidence recorded"])
        report = self.successful_json(opposite, ["report", "--state", str(state), "--format", "json"])
        if report["nodes"] != {"A": "accepted"} or not report["certified"]:
            raise ParityFailure(f"Cross-runtime completed report differs: {report!r}")
        self.record(f"state-handoff:{initial_runtime}-to-{opposite}")

    def run_attempt_ceiling(self, directory: Path) -> None:
        dag = self.write_dag(directory, "attempt-ceiling", [self.make_node("A", [], [], "README.md")])
        for runtime in ("python", "node"):
            state = self.state_path(directory, f"attempt-ceiling-{runtime}")
            self.successful_json(runtime, ["state", "init", str(dag), "--state", str(state), "--project-root", str(state.parent.parent)])
            args = ["--state", str(state), "A"]
            self.successful_json(runtime, ["state", "transition", *args, "--to", "ready", "--reason", "attempt ceiling setup"])
            for number in range(1, self.expectations["maximum_attempts"] + 1):
                self.successful_json(runtime, ["attempt", "begin", *args, "--hypothesis", f"Distinct failing attempt hypothesis {number}."])
                self.successful_json(runtime, ["state", "transition", *args, "--to", "verifying", "--reason", "negative verification"])
                self.successful_json(runtime, ["attempt", "verify", *args, "--attempt", str(number), "--result", "fail", "--summary", f"Expected negative result {number}."])
                self.successful_json(runtime, ["attempt", "diagnose", *args, "--attempt", str(number), "--diagnosis", f"Cause for expected negative result {number}."])
                self.successful_json(runtime, ["state", "transition", *args, "--to", "fix_required", "--reason", "prepare bounded retry"])
                self.successful_json(runtime, ["state", "transition", *args, "--to", "ready", "--reason", "diagnosis complete"])
            self.expect_exit(runtime, ["attempt", "begin", *args, "--hypothesis", "A sixth distinct attempt must be refused."], self.expectations["invalid_case_exit_code"])
            stored = json.loads(state.read_text(encoding="utf-8"))
            if len(stored["nodes"]["A"]["attempts"]) != self.expectations["maximum_attempts"]:
                raise ParityFailure(f"{runtime} changed the bounded attempt count")
            self.record(f"attempt-ceiling:{runtime}")

    def run_scoped_invalidation_and_readonly_report(self, directory: Path) -> None:
        nodes = [
            self.make_node("A", [], ["input-a.txt"], "output/a.txt"),
            self.make_node("B", ["A"], [], "output/b.txt"),
            self.make_node("C", [], ["input-c.txt"], "output/c.txt"),
        ]
        dag = self.write_dag(directory, "scoped-invalidation", nodes)
        for runtime in ("python", "node"):
            project = directory / f"project scoped {runtime}"
            project.mkdir()
            (project / "input-a.txt").write_text("input A v1\n", encoding="utf-8")
            (project / "input-c.txt").write_text("independent input C\n", encoding="utf-8")
            artifact = project / "evidence-a.txt"
            artifact.write_text("artifact v1\n", encoding="utf-8")
            state = project / ".orqivra" / "state.json"
            self.successful_json(runtime, ["state", "init", str(dag), "--state", str(state), "--project-root", str(project)])
            self.complete_node(runtime, state, "A", "Accept A with a tracked artifact.", artifact)
            self.complete_node(runtime, state, "B", "Accept B after A.")
            self.complete_node(runtime, state, "C", "Accept independent C.")

            before_report = self.command(runtime, ["report", "--state", str(state), "--format", "json"])
            if before_report.returncode != 0:
                raise ParityFailure(f"{runtime} report failed before read-only check: {before_report.stderr}")
            state_hash = hashlib.sha256(state.read_bytes()).hexdigest()
            after_report = self.command(runtime, ["report", "--state", str(state), "--format", "json"])
            if after_report.returncode != 0 or after_report.stdout != before_report.stdout:
                raise ParityFailure(f"{runtime} JSON report output was not repeatable/read-only")
            if hashlib.sha256(state.read_bytes()).hexdigest() != state_hash:
                raise ParityFailure(f"{runtime} report modified state bytes")

            (project / "input-a.txt").write_text("input A v2\n", encoding="utf-8")
            artifact.write_text("artifact v2\n", encoding="utf-8")
            check = self.successful_json(runtime, ["evidence", "check", "--state", str(state)])
            state_after_check = json.loads(state.read_text(encoding="utf-8"))
            statuses = {name: node["status"] for name, node in state_after_check["nodes"].items()}
            expected = self.expectations["scoped_invalidation"]
            if statuses != {"A": "obsolete", "B": "obsolete", "C": "accepted"}:
                raise ParityFailure(f"{runtime} did not scope input/artifact invalidation: {statuses!r}; {check!r}")
            if not any("A" in item for item in check["stale_evidence"]):
                raise ParityFailure(f"{runtime} did not report the stale A artifact evidence: {check!r}")
            self.successful_json(runtime, ["resume", "--dag", str(dag), "--state", str(state)])
            resumed = json.loads(state.read_text(encoding="utf-8"))
            resumed_statuses = {name: node["status"] for name, node in resumed["nodes"].items()}
            if resumed_statuses != expected["resumed_statuses"]:
                raise ParityFailure(f"{runtime} did not preserve the independent branch on resume: {resumed_statuses!r}")

            self.successful_json(runtime, ["state", "transition", "--state", str(state), "A", "--to", "obsolete", "--reason", "manual scoped obsoletion"])
            self.successful_json(runtime, ["resume", "--dag", str(dag), "--state", str(state)])
            manually_resumed = json.loads(state.read_text(encoding="utf-8"))
            final_statuses = {name: node["status"] for name, node in manually_resumed["nodes"].items()}
            if final_statuses != expected["resumed_statuses"]:
                raise ParityFailure(f"{runtime} manual obsoletion affected an independent branch: {final_statuses!r}")
            self.record(f"scoped-invalidation-and-readonly-report:{runtime}")

    def run_installation_interop(self, directory: Path) -> None:
        target_node = directory / "node skill target with spaces" / ".agents" / "skills"
        target_node.mkdir(parents=True)
        sentinel = target_node / "user-data.txt"
        sentinel.write_text("preserve this unrelated file\n", encoding="utf-8")
        self.successful_json("node", ["install", "--edition", "codex", "--target", str(target_node), "--apply"])
        manifest = json.loads((target_node / ".orqivra-manifest.json").read_text(encoding="utf-8"))
        wanted_manifest = self.expectations["manifest"]
        if manifest.get("owner") != wanted_manifest["owner"] or manifest.get("format_version") != wanted_manifest["format_version"]:
            raise ParityFailure(f"Unexpected Node installation manifest: {manifest!r}")
        self.successful_json("python", ["verify-install", "--target", str(target_node)])
        owned = target_node / "orqivra-architecture" / "SKILL.md"
        original = owned.read_bytes()
        owned.write_bytes(original + b"\nmodified by parity fixture\n")
        self.expect_exit("node", ["verify-install", "--target", str(target_node)], self.expectations["invalid_case_exit_code"])
        self.expect_exit("python", ["uninstall", "--target", str(target_node), "--apply"], self.expectations["invalid_case_exit_code"])
        if not owned.exists() or b"modified by parity fixture" not in owned.read_bytes():
            raise ParityFailure("Python uninstall removed a modified Node-owned skill")
        owned.write_bytes(original)
        self.successful_json("python", ["verify-install", "--target", str(target_node)])
        self.successful_json("python", ["uninstall", "--target", str(target_node), "--apply"])
        if not sentinel.exists() or sentinel.read_text(encoding="utf-8") != "preserve this unrelated file\n":
            raise ParityFailure("Uninstall removed an unrelated user file")

        target_python = directory / "python skill target with spaces" / ".agents" / "skills"
        target_python.mkdir(parents=True)
        self.successful_json("python", ["install", "--edition", "codex", "--target", str(target_python), "--apply"])
        self.successful_json("node", ["verify-install", "--target", str(target_python)])
        self.successful_json("node", ["uninstall", "--target", str(target_python), "--apply"])

        for runtime in ("python", "node"):
            collision = directory / f"collision target {runtime}" / ".agents" / "skills"
            owned_collision = collision / "orqivra-architecture" / "SKILL.md"
            owned_collision.parent.mkdir(parents=True)
            owned_collision.write_text("unowned user content\n", encoding="utf-8")
            self.expect_exit(runtime, ["install", "--edition", "codex", "--target", str(collision), "--apply"], self.expectations["invalid_case_exit_code"])
            if owned_collision.read_text(encoding="utf-8") != "unowned user content\n":
                raise ParityFailure(f"{runtime} overwrote an unowned skill collision")
            if (collision / ".orqivra-manifest.json").exists():
                raise ParityFailure(f"{runtime} created a manifest after refusing a collision")
        self.record("installation-manifest-cross-runtime-and-safety")

    def run_unsafe_paths(self, directory: Path) -> str:
        traversal_project = directory / "traversal-project.json"
        project_data = json.loads((FIXTURE_ROOT / "valid-project.json").read_text(encoding="utf-8"))
        project_data["inputs"] = ["../outside.txt"]
        traversal_project.write_text(json.dumps(project_data, indent=2) + "\n", encoding="utf-8")
        for runtime in ("python", "node"):
            self.expect_exit(runtime, ["validate", "project", str(traversal_project)], self.expectations["invalid_case_exit_code"])
        self.record("project-input-traversal-refused-by-both-runtimes")

        real_root = directory / "real project root"
        real_root.mkdir()
        dag = self.write_dag(directory, "symlink-project", [self.make_node("A", [], [], "README.md")])
        link = directory / "linked project root"
        link_status: str
        try:
            os.symlink(real_root, link, target_is_directory=True)
            link_status = "symbolic link created and rejected by both runtimes"
        except (OSError, NotImplementedError) as symlink_error:
            if os.name == "nt":
                system_root = Path(os.environ.get("SystemRoot", "C:" + chr(92) + "Windows"))
                powershell = system_root / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
                command = "$ErrorActionPreference = 'Stop'; New-Item -ItemType Junction -Path $env:ORQIVRA_JUNCTION_PATH -Target $env:ORQIVRA_JUNCTION_TARGET | Out-Null"
                environment = os.environ.copy()
                environment["ORQIVRA_JUNCTION_PATH"] = str(link)
                environment["ORQIVRA_JUNCTION_TARGET"] = str(real_root)
                result = subprocess.run(
                    [str(powershell), "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", command],
                    capture_output=True,
                    text=True,
                    env=environment,
                    check=False,
                )
                if result.returncode == 0 and link.exists():
                    link_status = "junction created and rejected by both runtimes"
                else:
                    reason = result.stderr.strip() or result.stdout.strip() or str(symlink_error)
                    self.skipped.append({"check": "symlink-or-junction-protection", "reason": reason})
                    return "unavailable: " + reason
            else:
                reason = str(symlink_error)
                self.skipped.append({"check": "symlink-or-junction-protection", "reason": reason})
                return "unavailable: " + reason

        for runtime in ("python", "node"):
            state = directory / f"linked-state-{runtime}.json"
            self.expect_exit(runtime, ["state", "init", str(dag), "--state", str(state), "--project-root", str(link)], self.expectations["unsafe_path_exit_code"])
        self.record("symlink-or-junction-protection")
        return link_status

    def create_directory_link(self, link: Path, target: Path) -> str | None:
        try:
            os.symlink(target, link, target_is_directory=True)
            return "symbolic link"
        except (OSError, NotImplementedError) as symlink_error:
            if os.name != "nt":
                return None
            system_root = Path(os.environ.get("SystemRoot", "C:" + chr(92) + "Windows"))
            powershell = system_root / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
            command = "$ErrorActionPreference = 'Stop'; New-Item -ItemType Junction -Path $env:ORQIVRA_JUNCTION_PATH -Target $env:ORQIVRA_JUNCTION_TARGET | Out-Null"
            environment = os.environ.copy()
            environment["ORQIVRA_JUNCTION_PATH"] = str(link)
            environment["ORQIVRA_JUNCTION_TARGET"] = str(target)
            result = subprocess.run(
                [str(powershell), "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", command],
                capture_output=True,
                text=True,
                env=environment,
                check=False,
            )
            return "junction" if result.returncode == 0 and link.exists() else None

    def run_path_regressions(self, directory: Path) -> None:
        dag = self.write_dag(directory, "non-regular-input", [self.make_node("A", [], ["directory-input"], "README.md")])
        for runtime in ("python", "node"):
            project = directory / f"non-regular-input-project-{runtime}"
            project.mkdir()
            (project / "directory-input").mkdir()
            state = directory / f"non-regular-input-{runtime}.json"
            self.expect_exit(
                runtime,
                ["state", "init", str(dag), "--state", str(state), "--project-root", str(project)],
                self.expectations["invalid_case_exit_code"],
            )
        self.record("existing-directory-input-rejected-by-both-runtimes")

        normalization_dag = self.write_dag(directory, "hypothesis-normalization", [self.make_node("A", [], [], "README.md")])
        for runtime in ("python", "node"):
            state = directory / f"normalization-{runtime}.json"
            self.successful_json(runtime, ["state", "init", str(normalization_dag), "--state", str(state), "--project-root", str(directory)])
            args = ["--state", str(state), "A"]
            self.successful_json(runtime, ["state", "transition", *args, "--to", "ready", "--reason", "normalization setup"])
            self.successful_json(runtime, ["attempt", "begin", *args, "--hypothesis", "  cafe\u0301   test  "])
            self.successful_json(runtime, ["state", "transition", *args, "--to", "verifying", "--reason", "negative normalization check"])
            self.successful_json(runtime, ["attempt", "verify", *args, "--attempt", "1", "--result", "fail", "--summary", "Prepare duplicate hypothesis probe."])
            self.successful_json(runtime, ["attempt", "diagnose", *args, "--attempt", "1", "--diagnosis", "The duplicate probe is intentional."])
            self.successful_json(runtime, ["state", "transition", *args, "--to", "fix_required", "--reason", "finish first attempt"])
            self.successful_json(runtime, ["state", "transition", *args, "--to", "ready", "--reason", "diagnosis recorded"])
            self.expect_exit(runtime, ["attempt", "begin", *args, "--hypothesis", "CAFÉ\tTEST"], self.expectations["invalid_case_exit_code"])
            stored = json.loads(state.read_text(encoding="utf-8"))
            if len(stored["nodes"]["A"]["attempts"]) != 1:
                raise ParityFailure(f"{runtime} started a duplicate normalized hypothesis")
        self.record("unicode-hypothesis-normalization-parity")

        replacement_dag = self.write_dag(directory, "root-replacement", [self.make_node("A", [], [], "README.md")])
        for runtime in ("python", "node"):
            project = directory / f"root-replacement-original-{runtime}"
            moved_project = directory / f"root-replacement-target-{runtime}"
            project.mkdir()
            state = directory / f"root-replacement-state-{runtime}.json"
            self.successful_json(runtime, ["state", "init", str(replacement_dag), "--state", str(state), "--project-root", str(project)])
            self.complete_node(runtime, state, "A", "Accept an empty-input task before replacing its root.")
            project.rename(moved_project)
            link_type = self.create_directory_link(project, moved_project)
            if link_type is None:
                self.skipped.append({"check": "saved-project-root-replacement", "reason": f"Could not create symlink or junction for {runtime} on {os.name}."})
                return
            self.expect_exit(runtime, ["report", "--state", str(state), "--format", "json"], self.expectations["unsafe_path_exit_code"])
            self.successful_json(
                runtime,
                ["resume", "--dag", str(replacement_dag), "--state", str(state), "--project-root", str(moved_project)],
            )
            resumed_state = json.loads(state.read_text(encoding="utf-8"))
            if Path(resumed_state["project_root"]).resolve() != moved_project.resolve():
                raise ParityFailure(f"{runtime} did not persist the explicitly selected project root during resume")
            self.successful_json(runtime, ["report", "--state", str(state), "--format", "json"])
        self.record("saved-project-root-replacement-rejected-and-explicit-root-resume-persisted")

    def wait_for_file(self, path: Path, process: subprocess.Popen[str], timeout_seconds: float = 10.0) -> None:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if path.exists():
                return
            if process.poll() is not None:
                raise ParityFailure(f"Lock holder exited before acquiring the lock: {process.stderr.read() if process.stderr else ''}")
            time.sleep(0.02)
        process.kill()
        raise ParityFailure(f"Timed out waiting for lock holder marker: {path}")

    def run_lock_interop(self, directory: Path) -> None:
        dag = self.write_dag(directory, "lock-interop", [self.make_node("A", [], [], "README.md")])
        node_module = NODE_CLI.parent / "core" / "state.js"
        node_module_url = node_module.as_uri()
        python_holder = textwrap.dedent(
            """
            from pathlib import Path
            import sys
            import time
            from orqivra.state import mutate_state
            state, started, release = map(Path, sys.argv[1:4])
            def hold(_value):
                started.write_text("acquired", encoding="utf-8")
                deadline = time.monotonic() + 15
                while not release.exists() and time.monotonic() < deadline:
                    time.sleep(0.01)
                if not release.exists():
                    raise RuntimeError("lock release timed out")
            mutate_state(state, "parity_lock_probe", None, {}, hold)
            """
        )
        node_holder = textwrap.dedent(
            """
            import { existsSync, writeFileSync } from 'node:fs';
            const { mutateState } = await import(process.argv[1]);
            const [state, started, release] = process.argv.slice(2);
            mutateState(state, 'parity_lock_probe', null, {}, () => {
              writeFileSync(started, 'acquired');
              const wait = new Int32Array(new SharedArrayBuffer(4));
              const deadline = Date.now() + 15000;
              while (!existsSync(release) && Date.now() < deadline) Atomics.wait(wait, 0, 0, 10);
              if (!existsSync(release)) throw new Error('lock release timed out');
            });
            """
        )

        for holder_runtime in ("node", "python"):
            state = self.state_path(directory, f"lock-{holder_runtime}")
            self.successful_json("python", ["state", "init", str(dag), "--state", str(state), "--project-root", str(state.parent.parent)])
            started = directory / f"{holder_runtime}-lock-started"
            release = directory / f"{holder_runtime}-lock-release"
            environment = os.environ.copy()
            environment.pop("ORQIVRA_DATA_DIR", None)
            environment["PYTHONPATH"] = str(ROOT / "src") + (os.pathsep + environment["PYTHONPATH"] if environment.get("PYTHONPATH") else "")
            if holder_runtime == "node":
                process = subprocess.Popen(
                    [self.executables["node"], "-e", node_holder, node_module_url, str(state), str(started), str(release)],
                    cwd=ROOT,
                    env=environment,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
            else:
                process = subprocess.Popen(
                    [self.executables["python"], "-c", python_holder, str(state), str(started), str(release)],
                    cwd=ROOT,
                    env=environment,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
            try:
                self.wait_for_file(started, process)
                lock = Path(str(state) + ".lock")
                lock_bytes = lock.read_bytes()
                state_bytes = state.read_bytes()
                competing_runtime = "python" if holder_runtime == "node" else "node"
                self.expect_exit(
                    competing_runtime,
                    ["state", "transition", "--state", str(state), "A", "--to", "ready", "--reason", "cross-runtime lock conflict"],
                    self.expectations["concurrent_writer_exit_code"],
                )
                if lock.read_bytes() != lock_bytes or state.read_bytes() != state_bytes:
                    raise ParityFailure(f"{competing_runtime} changed state or lock bytes while {holder_runtime} held the lock")
            finally:
                release.write_text("release", encoding="utf-8")
                try:
                    stdout, stderr = process.communicate(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    stdout, stderr = process.communicate()
                    raise ParityFailure(f"{holder_runtime} lock holder did not exit: {stdout}\n{stderr}")
                if process.returncode != 0:
                    raise ParityFailure(f"{holder_runtime} lock holder failed: {stdout}\n{stderr}")
        self.record("cross-runtime-writer-lock-conflicts-both-directions")

    def run(self) -> dict[str, Any]:
        if not NODE_CLI.is_file():
            raise ParityFailure(f"Node CLI build is missing: {NODE_CLI}; run npm test --prefix node first")
        with tempfile.TemporaryDirectory(prefix="orqivra parity project ") as temporary:
            directory = Path(temporary)
            self.run_shared_fixtures()
            self.run_state_handoff(directory, initial_runtime="python")
            self.run_state_handoff(directory, initial_runtime="node")
            self.run_attempt_ceiling(directory)
            self.run_scoped_invalidation_and_readonly_report(directory)
            self.run_installation_interop(directory)
            symlink_status = self.run_unsafe_paths(directory)
            self.run_path_regressions(directory)
            self.run_lock_interop(directory)
        return {
            "passed_count": len(self.passed),
            "passed": self.passed,
            "skipped": self.skipped,
            "symlink_or_junction": symlink_status,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python-executable", default=os.environ.get("ORQIVRA_PYTHON", sys.executable))
    parser.add_argument("--node-executable", default=os.environ.get("ORQIVRA_NODE", shutil.which("node") or "node"))
    arguments = parser.parse_args()
    try:
        report = Harness(arguments.python_executable, arguments.node_executable).run()
    except (OSError, ParityFailure) as error:
        print(json.dumps({"passed": False, "error": str(error)}, indent=2), file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
