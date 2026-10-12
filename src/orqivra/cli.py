"""Command-line interface for ORQIVRA local workflow operations."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .dag import plan_hashes, read_dag, ready_frontier
from .errors import OrqivraError
from .installer import build, install, skills_root, uninstall, validate_skills, verify_install
from .schema import load_json, require_valid
from .state import (
    add_evidence,
    begin_attempt,
    check_evidence,
    diagnose,
    initialize_state,
    read_state,
    record_change,
    record_verification,
    report_state,
    resume,
    transition,
)
from .paths import safe_join, safe_relative_path


def _emit(data: Any) -> None:
    print(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=True))


def _add_state_option(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--state", required=True, type=Path, help="Explicit state JSON path")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="orqivra", description="Local, provider-independent agent workflow tools")
    parser.add_argument("--version", action="version", version=f"orqivra {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)

    validate_parser = commands.add_parser("validate", help="Validate a public configuration or skill edition")
    validate_kinds = validate_parser.add_subparsers(dest="kind", required=True)
    project_parser = validate_kinds.add_parser("project")
    project_parser.add_argument("path", type=Path)
    dag_parser = validate_kinds.add_parser("dag")
    dag_parser.add_argument("path", type=Path)
    dag_parser.add_argument("--project", type=Path)
    profile_parser = validate_kinds.add_parser("profile")
    profile_parser.add_argument("path", type=Path)
    skills_parser = validate_kinds.add_parser("skills")
    skills_parser.add_argument("path", type=Path)

    plan_parser = commands.add_parser("plan", help="Validate a DAG and print its deterministic READY frontier")
    plan_parser.add_argument("dag", type=Path)
    plan_parser.add_argument("--state", type=Path)

    state_parser = commands.add_parser("state", help="Initialize or transition persistent task state")
    state_commands = state_parser.add_subparsers(dest="state_action", required=True)
    init_parser = state_commands.add_parser("init")
    init_parser.add_argument("dag", type=Path)
    _add_state_option(init_parser)
    init_parser.add_argument("--project-root", type=Path, default=Path.cwd())
    transition_parser = state_commands.add_parser("transition")
    _add_state_option(transition_parser)
    transition_parser.add_argument("node")
    transition_parser.add_argument("--to", required=True)
    transition_parser.add_argument("--reason", required=True)

    attempt_parser = commands.add_parser("attempt", help="Record attempt start, diagnosis, change, or verification")
    attempt_commands = attempt_parser.add_subparsers(dest="attempt_action", required=True)
    begin_parser = attempt_commands.add_parser("begin")
    _add_state_option(begin_parser)
    begin_parser.add_argument("node")
    begin_parser.add_argument("--hypothesis", required=True)
    for action, option, help_text in (
        ("diagnose", "--diagnosis", "Record a diagnosis"),
        ("record-change", "--summary", "Record a modification"),
    ):
        action_parser = attempt_commands.add_parser(action, help=help_text)
        _add_state_option(action_parser)
        action_parser.add_argument("node")
        action_parser.add_argument("--attempt", type=int, required=True)
        action_parser.add_argument(option, required=True)
    verify_parser = attempt_commands.add_parser("verify")
    _add_state_option(verify_parser)
    verify_parser.add_argument("node")
    verify_parser.add_argument("--attempt", type=int, required=True)
    verify_parser.add_argument("--result", choices=["pass", "fail"], required=True)
    verify_parser.add_argument("--summary", required=True)

    evidence_parser = commands.add_parser("evidence", help="Record evidence or check recorded evidence freshness")
    evidence_commands = evidence_parser.add_subparsers(dest="evidence_action", required=True)
    evidence_add = evidence_commands.add_parser("add")
    _add_state_option(evidence_add)
    evidence_add.add_argument("node")
    evidence_add.add_argument("--command", dest="command_text", required=True)
    evidence_add.add_argument("--exit-code", type=int, required=True)
    evidence_add.add_argument("--artifact", action="append", default=[])
    evidence_check = evidence_commands.add_parser("check")
    _add_state_option(evidence_check)

    resume_parser = commands.add_parser("resume", help="Reconcile a saved state with the current DAG and input snapshot")
    resume_parser.add_argument("--dag", required=True, type=Path)
    _add_state_option(resume_parser)
    resume_parser.add_argument("--project-root", type=Path)

    report_parser = commands.add_parser("report", help="Generate a deterministic report from stored state")
    _add_state_option(report_parser)
    report_parser.add_argument("--format", choices=["json", "markdown"], default="json")

    build_parser = commands.add_parser("build", help="Create a deterministic standalone edition bundle")
    build_parser.add_argument("--edition", required=True, choices=["codex", "claude-code", "gemini-cli", "all"])
    build_parser.add_argument("--output", required=True, type=Path)

    install_parser = commands.add_parser("install", help="Install selected skill files to an explicit target")
    install_parser.add_argument("--edition", required=True, choices=["codex", "claude-code", "gemini-cli"])
    install_parser.add_argument("--target", required=True, type=Path)
    install_parser.add_argument("--skill", action="append", default=[])
    install_mode = install_parser.add_mutually_exclusive_group()
    install_mode.add_argument("--dry-run", action="store_true", default=True)
    install_mode.add_argument("--apply", action="store_true")

    verify_install_parser = commands.add_parser("verify-install", help="Verify an ORQIVRA-owned installation manifest")
    verify_install_parser.add_argument("--target", required=True, type=Path)

    uninstall_parser = commands.add_parser("uninstall", help="Remove only verified ORQIVRA-owned files")
    uninstall_parser.add_argument("--target", required=True, type=Path)
    uninstall_mode = uninstall_parser.add_mutually_exclusive_group()
    uninstall_mode.add_argument("--dry-run", action="store_true", default=True)
    uninstall_mode.add_argument("--apply", action="store_true")
    return parser


def _load_project(path: Path) -> dict[str, Any]:
    data = load_json(path)
    require_valid(data, "project.schema.json")
    for relative in data["inputs"]:
        safe_relative_path(relative)
    return data


def _validate(args: argparse.Namespace) -> Any:
    if args.kind == "project":
        project = _load_project(args.path)
        return {"valid": True, "kind": "project", "id": project["id"]}
    if args.kind == "dag":
        dag = read_dag(args.path)
        snapshot = None
        if args.project:
            project = _load_project(args.project)
            root = Path(project["root"])
            if not root.is_absolute():
                root = args.project.parent / root
            for node in dag["nodes"]:
                for scope in node["file_scope"]:
                    relative = scope[:-3] if scope.endswith("/**") else scope
                    safe_join(root, relative, allow_missing=True)
            plan, _, input_hashes, _ = plan_hashes(dag, root)
            snapshot = {"plan_hash": plan, "input_hashes": input_hashes}
        return {"valid": True, "kind": "dag", "id": dag["id"], "node_count": len(dag["nodes"]), "snapshot_inputs": snapshot}
    if args.kind == "profile":
        profile = load_json(args.path)
        require_valid(profile, "profile.schema.json")
        return {"valid": True, "kind": "profile", "id": profile["id"], "edition": profile["edition"]}
    found_root = skills_root(args.path)
    return {"valid": True, "kind": "skills", **validate_skills(found_root)}


def _markdown_report(report: dict[str, Any]) -> str:
    lines = [
        f"# ORQIVRA Report: {report['dag_id']}",
        "",
        f"- Project: `{report['project_id']}`",
        f"- State version: {report['version']}",
        f"- Snapshot: `{report['snapshot']}`",
        f"- Certified: {'yes' if report['certified'] else 'no'}",
        "",
        "## Nodes",
        "",
    ]
    lines.extend(f"- `{node_id}`: `{status}`" for node_id, status in report["nodes"].items())
    lines.extend(["", "## Ready frontier", ""])
    lines.extend(f"- `{node_id}`" for node_id in report["ready_frontier"])
    if not report["ready_frontier"]:
        lines.append("- None")
    lines.extend(["", "## Unresolved required gates", ""])
    lines.extend(f"- `{gate['node_id']}/{gate['id']}`: `{gate['status']}` — {gate['description']}" for gate in report["unresolved_required_gates"])
    if not report["unresolved_required_gates"]:
        lines.append("- None")
    lines.extend(["", "## Changed inputs", ""])
    lines.extend(f"- `{path}`" for path in report["changed_inputs"])
    if not report["changed_inputs"]:
        lines.append("- None")
    lines.extend(["", "## Stale evidence", ""])
    lines.extend(f"- `{item['node_id']}/{item['evidence_id']}`: {item['reason']}" for item in report["stale_evidence"])
    if not report["stale_evidence"]:
        lines.append("- None")
    lines.extend(["", "## Superseded stale evidence", ""])
    lines.extend(f"- `{item['node_id']}/{item['evidence_id']}`: {item['reason']}" for item in report["superseded_stale_evidence"])
    if not report["superseded_stale_evidence"]:
        lines.append("- None")
    lines.extend(["", "## Accepted nodes without current evidence", ""])
    lines.extend(f"- `{node_id}`" for node_id in report["accepted_without_current_evidence"])
    if not report["accepted_without_current_evidence"]:
        lines.append("- None")
    return "\n".join(lines) + "\n"


def _run(args: argparse.Namespace) -> int:
    if args.command == "validate":
        _emit(_validate(args))
    elif args.command == "plan":
        dag = read_dag(args.dag)
        state = read_state(args.state) if args.state else None
        if state and state["dag_id"] != dag["id"]:
            raise OrqivraError("DAG ID differs from state file.")
        _emit({"dag_id": dag["id"], "ready_frontier": ready_frontier(dag, state)})
    elif args.command == "state" and args.state_action == "init":
        _emit(initialize_state(args.dag, args.state, args.project_root))
    elif args.command == "state" and args.state_action == "transition":
        _emit(transition(args.state, args.node, args.to, args.reason))
    elif args.command == "attempt" and args.attempt_action == "begin":
        _emit(begin_attempt(args.state, args.node, args.hypothesis))
    elif args.command == "attempt" and args.attempt_action == "diagnose":
        _emit(diagnose(args.state, args.node, args.attempt, args.diagnosis))
    elif args.command == "attempt" and args.attempt_action == "record-change":
        _emit(record_change(args.state, args.node, args.attempt, args.summary))
    elif args.command == "attempt" and args.attempt_action == "verify":
        _emit(record_verification(args.state, args.node, args.attempt, args.result, args.summary))
    elif args.command == "evidence" and args.evidence_action == "add":
        _emit(add_evidence(args.state, args.node, args.command_text, args.exit_code, args.artifact))
    elif args.command == "evidence" and args.evidence_action == "check":
        state, stale = check_evidence(args.state)
        _emit({"version": state["version"], "stale_evidence": stale, "snapshot": state["dag_snapshot"]})
    elif args.command == "resume":
        state, changed = resume(args.dag, args.state, args.project_root)
        _emit({"version": state["version"], "snapshot": state["dag_snapshot"], "affected_nodes": changed})
    elif args.command == "report":
        report = report_state(read_state(args.state))
        if args.format == "markdown":
            print(_markdown_report(report), end="")
        else:
            _emit(report)
    elif args.command == "build":
        _emit({"built": [str(path) for path in build(args.edition, args.output)]})
    elif args.command == "install":
        _emit(install(args.edition, args.target, args.skill, apply=args.apply))
    elif args.command == "verify-install":
        _emit(verify_install(args.target))
    elif args.command == "uninstall":
        _emit(uninstall(args.target, apply=args.apply))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        return _run(args)
    except OrqivraError as exc:
        print(f"orqivra: {exc}", file=sys.stderr)
        return exc.exit_code
    except OSError as exc:
        print(f"orqivra: local file operation failed: {exc}", file=sys.stderr)
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
