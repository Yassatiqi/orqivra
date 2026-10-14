"""Run a small operator-driven ORQIVRA plan, failure, correction, and pass."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRATCH = ROOT / "scratch"
NODE = "require-nonempty-project-name"


def render_command(args: list[str]) -> str:
    return subprocess.list2cmdline(args) if os.name == "nt" else shlex.join(args)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="A new run directory under this checkout's ignored scratch/ directory.",
    )
    args = parser.parse_args()
    if SCRATCH.is_symlink():
        parser.error(f"{SCRATCH} must not be a symlink; choose a normal checkout scratch directory.")
    output = args.output if args.output.is_absolute() else ROOT / args.output
    output = output.resolve()
    try:
        output.relative_to(SCRATCH.resolve())
    except ValueError:
        parser.error(f"--output must be inside {SCRATCH}")
    if output.exists():
        parser.error(f"--output already exists; choose a fresh run directory: {output}")

    project = output / "project"
    project.mkdir(parents=True)
    state = output / "state.json"
    dag_path = output / "demo-dag.json"
    config = project / "config.json"
    checker = project / "check_config.py"
    transcript = output / "transcript.txt"
    config.write_text('{"project_name": ""}\n', encoding="utf-8", newline="\n")
    checker.write_text(
        "import json, sys\n"
        "from pathlib import Path\n"
        "name = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8')).get('project_name')\n"
        "if not isinstance(name, str) or not name.strip():\n"
        "    print('FAIL: project_name must be a non-empty string')\n"
        "    raise SystemExit(1)\n"
        "print('PASS: project_name is non-empty')\n",
        encoding="utf-8",
        newline="\n",
    )
    transcript.write_text(
        "ORQIVRA operator-driven onboarding demo\n"
        f"Python: {sys.executable} ({sys.version.split()[0]})\n"
        f"Output: {output}\n"
        "No agents or clients are launched.\n",
        encoding="utf-8",
        newline="\n",
    )
    dag_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "id": "onboarding-correction-demo",
                "objective": "Reject an empty project name and preserve correction history.",
                "input_snapshot": "sha256:" + "0" * 64,
                "nodes": [
                    {
                        "id": NODE,
                        "objective": "Require a non-empty project_name in config.json.",
                        "inputs": ["config.json"],
                        "dependencies": [],
                        "role": "implementer",
                        "profile": "local-default",
                        "file_scope": ["config.json"],
                        "risk": "low",
                        "acceptance_criteria": ["The check passes only for a non-empty name."],
                        "verification": ["Run check_config.py against config.json."],
                        "status": "planned",
                        "attempts": 0,
                        "evidence": [],
                        "blocking_reason": None,
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )

    def invoke(
        command: list[str],
        *,
        cwd: Path,
        expected: int = 0,
        screen: str,
        show_output: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(command, cwd=cwd, text=True, encoding="utf-8", capture_output=True)
        captured = result.stdout + result.stderr
        if captured and not captured.endswith("\n"):
            captured += "\n"
        with transcript.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(f"\n$ {render_command(command)}\n{captured}")
            stream.write(f"[exit {result.returncode}; expected {expected}]\n")
        print(screen)
        if show_output and captured:
            print(captured, end="" if captured.endswith("\n") else "\n")
        if result.returncode != expected:
            raise RuntimeError(f"Command returned {result.returncode}, expected {expected}: {render_command(command)}")
        return result

    def cli(*command: str, screen: str, show_output: bool = False) -> subprocess.CompletedProcess[str]:
        return invoke(
            [sys.executable, "-m", "orqivra.cli", *command],
            cwd=project,
            screen=screen,
            show_output=show_output,
        )

    def verify(expected: int) -> tuple[str, int]:
        command = [sys.executable, str(checker), str(config)]
        label = "First check (intentional failure)" if expected else "Corrected check"
        result = invoke(command, cwd=project, expected=expected, screen=label, show_output=True)
        return render_command(command), result.returncode

    print("Operator-driven Python CLI demonstration; no agents or clients are launched.")
    print(f"Fresh output: {output}")
    cli("validate", "dag", str(dag_path), screen="DAG validated.")
    plan = json.loads(cli("plan", str(dag_path), screen="Plan created.").stdout)
    if plan["ready_frontier"] != [NODE]:
        raise RuntimeError(f"Unexpected READY frontier: {plan['ready_frontier']}")
    print(f"READY: {NODE}")
    cli("state", "init", str(dag_path), "--state", str(state), "--project-root", str(project), screen="State initialized.")
    cli("state", "transition", "--state", str(state), NODE, "--to", "ready", "--reason", "Inputs are ready.", screen="Node ready.")
    cli("attempt", "begin", "--state", str(state), NODE, "--hypothesis", "The initial project name is empty.", screen="Attempt 1 hypothesis recorded.")

    failed_command, failed_code = verify(1)
    cli("state", "transition", "--state", str(state), NODE, "--to", "verifying", "--reason", "Run the project-name check.", screen="Verification started.")
    cli("attempt", "verify", "--state", str(state), NODE, "--attempt", "1", "--result", "fail", "--summary", "The check rejected the empty project_name.", screen="Attempt 1 recorded as failed.")
    cli("evidence", "add", "--state", str(state), NODE, "--command", failed_command, "--exit-code", str(failed_code), "--artifact", "config.json", screen="Failed evidence recorded.")
    cli("attempt", "diagnose", "--state", str(state), NODE, "--attempt", "1", "--diagnosis", "config.json contains an empty project_name.", screen="Diagnosis recorded: the input is empty.")
    cli("state", "transition", "--state", str(state), NODE, "--to", "fix_required", "--reason", "Correct the project input.", screen="Node moved to fix_required.")
    cli("attempt", "record-change", "--state", str(state), NODE, "--attempt", "1", "--summary", "Set project_name to ORQIVRA demo.", screen="Correction recorded.")
    config.write_text('{"project_name": "ORQIVRA demo"}\n', encoding="utf-8", newline="\n")

    freshness = json.loads(cli("evidence", "check", "--state", str(state), screen="Evidence checked after the input change.").stdout)
    if not freshness["stale_evidence"]:
        raise RuntimeError("Expected evidence for the previous config input to be marked stale.")
    print(f"Prior evidence marked stale: {len(freshness['stale_evidence'])} entry.")
    cli("resume", "--dag", str(dag_path), "--state", str(state), "--project-root", str(project), screen="Resumed with attempt 1 preserved.")
    cli("attempt", "begin", "--state", str(state), NODE, "--hypothesis", "The corrected non-empty project name will pass.", screen="Attempt 2 hypothesis recorded.")

    passing_command, passing_code = verify(0)
    cli("state", "transition", "--state", str(state), NODE, "--to", "verifying", "--reason", "Rerun the check after correction.", screen="Verification rerun started.")
    cli("attempt", "verify", "--state", str(state), NODE, "--attempt", "2", "--result", "pass", "--summary", "The check accepted the corrected project_name.", screen="Attempt 2 recorded as passed.")
    cli("evidence", "add", "--state", str(state), NODE, "--command", passing_command, "--exit-code", str(passing_code), "--artifact", "config.json", screen="Passing evidence recorded.")
    cli("state", "transition", "--state", str(state), NODE, "--to", "accepted", "--reason", "Current successful evidence is available.", screen="Node accepted.")
    report = cli("report", "--state", str(state), "--format", "markdown", screen="Final report:", show_output=True)

    saved = json.loads(state.read_text(encoding="utf-8"))
    node = saved["nodes"][NODE]
    outcomes = [attempt["verification_result"] for attempt in node["attempts"]]
    codes = [entry["exit_code"] for entry in node["evidence"]]
    if node["status"] != "accepted" or outcomes != ["fail", "pass"] or codes != [1, 0]:
        raise RuntimeError(f"Unexpected final state: {node['status']}, {outcomes}, {codes}")
    with transcript.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(f"\nFinal report length: {len(report.stdout)} characters.\n")
        stream.write(f"Final status: {node['status']}; attempts: {outcomes}; evidence exit codes: {codes}.\n")
    print(f"Verified: {node['status']}; attempts={outcomes}; evidence exit codes={codes}.")
    print(f"Transcript and generated state remain under {output}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
