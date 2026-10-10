"""Atomic task-state updates, recovery, attempts, and snapshot-bound evidence."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .dag import current_snapshot, plan_hashes, read_dag
from .errors import ConcurrentUpdateError, InputOutputError, OrqivraError, UnsafePathError
from .paths import digest_json, reject_symlink_components, reject_symlink_path, safe_join, sha256_file, safe_relative_path
from .schema import load_json, require_valid

TRANSITIONS = {
    "planned": {"ready", "blocked", "obsolete"},
    "ready": {"running", "blocked", "obsolete"},
    "running": {"verifying", "fix_required", "blocked", "obsolete"},
    "verifying": {"accepted", "fix_required", "blocked", "obsolete"},
    "fix_required": {"ready", "blocked", "obsolete"},
    "blocked": {"ready", "obsolete"},
    "accepted": {"obsolete"},
    "obsolete": {"ready"},
}
MAX_ATTEMPTS = 5


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _write_json_atomic(path: Path, state: dict[str, Any]) -> None:
    payload = (json.dumps(state, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
    descriptor = None
    temporary = None
    try:
        descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        temporary = Path(name)
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = None
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        temporary = None
        try:
            directory_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except (OSError, AttributeError):
            pass
    except OSError as exc:
        raise InputOutputError(f"Could not write state file {path}: {exc}") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def _load_state(path: Path) -> dict[str, Any]:
    reject_symlink_components(path)
    reject_symlink_path(path)
    state = load_json(path)
    require_valid(state, "state.schema.json")
    return state


def _validate_state_for_write(state: dict[str, Any]) -> None:
    require_valid(state, "state.schema.json")


def mutate_state(
    path: Path,
    action: str,
    node_id: str | None,
    detail: dict[str, Any],
    mutation: Callable[[dict[str, Any]], None],
) -> dict[str, Any]:
    """Serialize one state update under an exclusive lock and replace atomically."""
    path = path.absolute()
    reject_symlink_components(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    reject_symlink_components(path)
    reject_symlink_path(path)
    lock_path = path.with_name(path.name + ".lock")
    reject_symlink_path(lock_path)
    try:
        lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise ConcurrentUpdateError(f"State is locked by another writer: {lock_path}") from exc
    except OSError as exc:
        raise InputOutputError(f"Could not acquire state lock {lock_path}: {exc}") from exc

    try:
        os.write(lock_fd, f"pid={os.getpid()}\n".encode("ascii"))
        os.fsync(lock_fd)
        os.close(lock_fd)
        lock_fd = -1
        existed = path.exists()
        before = path.read_bytes() if existed else None
        if existed:
            state = _load_state(path)
        else:
            state = {}
        mutation(state)
        if existed:
            state["version"] += 1
        state.setdefault("events", []).append(
            {
                "version": state.get("version", 1),
                "timestamp": utc_now(),
                "action": action,
                "node_id": node_id,
                "detail": detail,
            }
        )
        _validate_state_for_write(state)
        if existed:
            try:
                current = path.read_bytes()
            except OSError as exc:
                raise ConcurrentUpdateError(f"State file changed during update: {path}") from exc
            if current != before:
                raise ConcurrentUpdateError(f"State file changed during update: {path}")
        elif path.exists():
            raise ConcurrentUpdateError(f"State file appeared during initialization: {path}")
        _write_json_atomic(path, state)
        return state
    except OSError as exc:
        raise InputOutputError(f"Could not update state file {path}: {exc}") from exc
    finally:
        if "lock_fd" in locals() and lock_fd >= 0:
            os.close(lock_fd)
        try:
            lock_path.unlink(missing_ok=True)
        except OSError:
            pass


def read_state(path: Path) -> dict[str, Any]:
    return _load_state(path)


def _dependency_closure(state: dict[str, Any], node_id: str) -> set[str]:
    closure: set[str] = set()
    pending = [node_id]
    while pending:
        current = pending.pop()
        if current in closure:
            continue
        closure.add(current)
        pending.extend(state["nodes"][current]["dependencies"])
    return closure


def node_snapshot(state: dict[str, Any], node_id: str) -> str:
    closure = _dependency_closure(state, node_id)
    input_names = sorted({path for item in closure for path in state["nodes"][item]["inputs"]})
    inputs = {path: state["input_hashes"].get(path) for path in input_names}
    definitions = {item: state["nodes"][item]["definition_hash"] for item in sorted(closure)}
    body = {"header": state["plan_header_hash"], "definitions": definitions, "inputs": inputs}
    return "sha256:" + digest_json(body)


def _node(state: dict[str, Any], node_id: str) -> dict[str, Any]:
    try:
        return state["nodes"][node_id]
    except KeyError as exc:
        raise OrqivraError(f"Unknown node ID: {node_id}") from exc


def _latest_evidence(node: dict[str, Any]) -> dict[str, Any] | None:
    return node["evidence"][-1] if node["evidence"] else None


def _changed_input_paths(state: dict[str, Any]) -> list[str]:
    current = _collect_input_hashes(state)
    saved = state["input_hashes"]
    return sorted(path for path in set(saved) | set(current) if saved.get(path) != current.get(path))


def _evidence_stale_reason(state: dict[str, Any], node_id: str, item: dict[str, Any]) -> str | None:
    if item["snapshot"] != node_snapshot(state, node_id):
        return "snapshot_changed"
    root = Path(state["project_root"]).resolve(strict=True)
    for artifact in item["artifacts"]:
        try:
            actual = sha256_file(safe_join(root, artifact["path"]))
        except (OrqivraError, OSError):
            actual = None
        if actual != artifact["sha256"]:
            return "artifact_changed"
    return None


def initialize_state(dag_path: Path, state_path: Path, project_root: Path) -> dict[str, Any]:
    dag = read_dag(dag_path)
    reject_symlink_components(project_root)
    root = project_root.resolve(strict=True)
    plan_hash, header_hash, input_hashes, definition_hashes = plan_hashes(dag, root)
    initial = {
        "schema_version": 1,
        "project_id": root.name or dag["id"],
        "project_root": str(root),
        "dag_id": dag["id"],
        "plan_hash": plan_hash,
        "plan_header_hash": header_hash,
        "dag_snapshot": current_snapshot(plan_hash, input_hashes),
        "version": 1,
        "input_hashes": input_hashes,
        "pending_resume": [],
        "nodes": {
            node["id"]: {
                "status": "planned",
                "definition_hash": definition_hashes[node["id"]],
                "dependencies": list(node["dependencies"]),
                "inputs": list(node["inputs"]),
                "attempts": [],
                "evidence": [],
                "obligations": list(node.get("obligations", [])),
                "blocking_reason": node.get("blocking_reason"),
            }
            for node in dag["nodes"]
        },
        "events": [],
    }

    def create(state: dict[str, Any]) -> None:
        if state:
            raise ConcurrentUpdateError(f"State file already exists: {state_path}")
        state.update(initial)

    return mutate_state(state_path, "state_initialized", None, {"dag_id": dag["id"]}, create)


def transition(path: Path, node_id: str, target: str, reason: str) -> dict[str, Any]:
    if target not in TRANSITIONS:
        raise OrqivraError(f"Unknown state: {target}")

    def apply(state: dict[str, Any]) -> None:
        node = _node(state, node_id)
        source = node["status"]
        if target not in TRANSITIONS[source] or (source == "obsolete" and target == "ready"):
            raise OrqivraError(f"Illegal state transition for {node_id}: {source} -> {target}")
        if target == "ready":
            if source == "obsolete" and len(node["attempts"]) >= MAX_ATTEMPTS:
                raise OrqivraError(f"Attempt limit reached for node {node_id}.")
            unmet = [dep for dep in node["dependencies"] if state["nodes"][dep]["status"] != "accepted"]
            if unmet:
                raise OrqivraError(f"Node {node_id} is not ready; dependencies are not accepted: {', '.join(unmet)}")
        if target == "blocked" and not reason.strip():
            raise OrqivraError("A blocking reason is required when entering blocked.")
        if target == "accepted":
            attempts = node["attempts"]
            if not attempts or attempts[-1]["verification_result"] != "pass":
                raise OrqivraError(f"Node {node_id} requires a passing verification attempt before acceptance.")
            changed_inputs = set(_changed_input_paths(state))
            relevant_inputs = {
                path
                for dependency in _dependency_closure(state, node_id)
                for path in state["nodes"][dependency]["inputs"]
            }
            if changed_inputs.intersection(relevant_inputs):
                raise OrqivraError(
                    f"Node {node_id} inputs changed; run evidence check and resume before acceptance."
                )
            current = _latest_evidence(node)
            if (
                current is None
                or current["snapshot"] != node_snapshot(state, node_id)
                or current["exit_code"] != 0
                or _evidence_stale_reason(state, node_id, current) is not None
            ):
                raise OrqivraError(f"Node {node_id} requires current successful evidence before acceptance.")
        if target == "obsolete":
            affected = _invalidate_affected(state, {node_id})
            state["pending_resume"] = sorted(set(state["pending_resume"]) | affected)
            if reason.strip():
                state["nodes"][node_id]["blocking_reason"] = reason.strip()
            return
        node["status"] = target
        node["blocking_reason"] = reason.strip() if target == "blocked" else None

    return mutate_state(path, "state_transition", node_id, {"to": target, "reason": reason}, apply)


def begin_attempt(path: Path, node_id: str, hypothesis: str) -> dict[str, Any]:
    cleaned = hypothesis.strip()
    if not cleaned:
        raise OrqivraError("An attempt hypothesis is required.")

    def apply(state: dict[str, Any]) -> None:
        node = _node(state, node_id)
        if node["status"] not in {"ready", "running"}:
            raise OrqivraError(f"Node {node_id} must be ready or running before an attempt begins.")
        if len(node["attempts"]) >= MAX_ATTEMPTS:
            raise OrqivraError(f"Attempt limit reached for node {node_id}.")
        normalized = " ".join(cleaned.casefold().split())
        prior = {" ".join(item["hypothesis"].casefold().split()) for item in node["attempts"]}
        if normalized in prior:
            raise OrqivraError("A correction attempt must use a new hypothesis.")
        if node["attempts"] and node["attempts"][-1]["verification_result"] in {"fail", "interrupted"} and not node["attempts"][-1]["diagnosis"]:
            raise OrqivraError("Record a diagnosis before starting a correction attempt.")
        if node["attempts"] and node["attempts"][-1]["verification_result"] == "pending":
            raise OrqivraError("The previous attempt is unfinished; inspect state and resume before retrying.")
        number = len(node["attempts"]) + 1
        node["attempts"].append(
            {
                "number": number,
                "hypothesis": cleaned,
                "started_at": utc_now(),
                "diagnosis": None,
                "changes": [],
                "verification_result": "pending",
                "verification_summary": None,
            }
        )
        node["status"] = "running"
        node["blocking_reason"] = None

    return mutate_state(path, "attempt_started", node_id, {"hypothesis": cleaned}, apply)


def _get_attempt(state: dict[str, Any], node_id: str, number: int) -> dict[str, Any]:
    node = _node(state, node_id)
    if number < 1 or number > len(node["attempts"]):
        raise OrqivraError(f"Attempt {number} does not exist for node {node_id}.")
    return node["attempts"][number - 1]


def diagnose(path: Path, node_id: str, number: int, diagnosis_text: str) -> dict[str, Any]:
    cleaned = diagnosis_text.strip()
    if not cleaned:
        raise OrqivraError("A diagnosis is required.")

    def apply(state: dict[str, Any]) -> None:
        attempt = _get_attempt(state, node_id, number)
        attempt["diagnosis"] = cleaned

    return mutate_state(path, "attempt_diagnosed", node_id, {"attempt": number, "diagnosis": cleaned}, apply)


def record_change(path: Path, node_id: str, number: int, summary: str) -> dict[str, Any]:
    cleaned = summary.strip()
    if not cleaned:
        raise OrqivraError("A change summary is required.")

    def apply(state: dict[str, Any]) -> None:
        attempt = _get_attempt(state, node_id, number)
        attempt["changes"].append(cleaned)

    return mutate_state(path, "attempt_change_recorded", node_id, {"attempt": number, "summary": cleaned}, apply)


def record_verification(path: Path, node_id: str, number: int, result: str, summary: str) -> dict[str, Any]:
    cleaned = summary.strip()
    if result not in {"pass", "fail"} or not cleaned:
        raise OrqivraError("Verification requires result pass|fail and a non-empty summary.")

    def apply(state: dict[str, Any]) -> None:
        node = _node(state, node_id)
        if node["status"] != "verifying":
            raise OrqivraError(f"Node {node_id} must be verifying before verification is recorded.")
        attempt = _get_attempt(state, node_id, number)
        if number != len(node["attempts"]):
            raise OrqivraError("Verification must be recorded for the latest attempt.")
        if attempt["verification_result"] != "pending":
            raise OrqivraError("Verification has already been recorded for this attempt.")
        attempt["verification_result"] = result
        attempt["verification_summary"] = cleaned

    return mutate_state(path, "attempt_verified", node_id, {"attempt": number, "result": result, "summary": cleaned}, apply)


def add_evidence(path: Path, node_id: str, command: str, exit_code: int, artifacts: list[str]) -> dict[str, Any]:
    if not command.strip():
        raise OrqivraError("Evidence command text is required.")

    def apply(state: dict[str, Any]) -> None:
        node = _node(state, node_id)
        if node["status"] not in {"running", "verifying", "accepted"}:
            raise OrqivraError(f"Evidence for {node_id} can be recorded only while it is active or accepted.")
        root = Path(state["project_root"]).resolve(strict=True)
        artifact_records = []
        for raw_path in artifacts:
            path_value = Path(raw_path)
            if path_value.is_absolute():
                reject_symlink_components(path_value)
                try:
                    relative = path_value.resolve(strict=True).relative_to(root).as_posix()
                except (ValueError, OSError) as exc:
                    raise UnsafePathError(f"Artifact must be inside the project root: {raw_path}") from exc
            else:
                relative = safe_relative_path(raw_path)
            resolved = safe_join(root, relative)
            artifact_records.append({"path": relative, "sha256": sha256_file(resolved)})
        entry = {
            "id": f"{node_id}-evidence-{len(node['evidence']) + 1}",
            "command": command.strip(),
            "exit_code": exit_code,
            "snapshot": node_snapshot(state, node_id),
            "recorded_at": utc_now(),
            "artifacts": artifact_records,
        }
        node["evidence"].append(entry)

    return mutate_state(path, "evidence_recorded", node_id, {"command": command, "exit_code": exit_code}, apply)


def _descendants(state: dict[str, Any], seeds: set[str]) -> set[str]:
    result = set(seeds)
    changed = True
    while changed:
        changed = False
        for node_id, node in state["nodes"].items():
            if node_id not in result and any(dep in result for dep in node["dependencies"]):
                result.add(node_id)
                changed = True
    return result


def _invalidate_affected(state: dict[str, Any], affected: set[str]) -> set[str]:
    affected = _descendants(state, affected)
    for node_id in affected:
        node = state["nodes"][node_id]
        if node["status"] in {"running", "verifying"} and node["attempts"] and node["attempts"][-1]["verification_result"] == "pending":
            node["attempts"][-1]["verification_result"] = "interrupted"
            node["attempts"][-1]["verification_summary"] = "The active session ended before verification; inspect current files before retrying."
        if node["status"] != "obsolete":
            node["status"] = "obsolete"
            node["blocking_reason"] = "Inputs, plan, or evidence changed; resume to recheck prerequisites."
    return affected


def _reopen_affected(state: dict[str, Any], affected: set[str]) -> set[str]:
    affected = _invalidate_affected(state, affected)
    ordered = _topological_ids(state["nodes"])
    for node_id in ordered:
        if node_id not in affected:
            continue
        node = state["nodes"][node_id]
        if node["attempts"] and node["attempts"][-1]["verification_result"] == "interrupted":
            node["status"] = "fix_required"
            node["blocking_reason"] = "An interrupted attempt requires diagnosis before retry."
            continue
        if len(node["attempts"]) >= MAX_ATTEMPTS:
            node["blocking_reason"] = "Attempt limit reached; node cannot be retried."
            continue
        if all(state["nodes"][dependency]["status"] == "accepted" for dependency in node["dependencies"]):
            node["status"] = "ready"
            node["blocking_reason"] = None
        else:
            node["status"] = "planned"
            node["blocking_reason"] = None
    return affected


def _topological_ids(nodes: dict[str, dict[str, Any]]) -> list[str]:
    remaining = {node_id: set(node["dependencies"]) for node_id, node in nodes.items()}
    result = []
    while remaining:
        ready = sorted(node_id for node_id, dependencies in remaining.items() if not dependencies)
        if not ready:
            raise OrqivraError("Stored state contains a dependency cycle.")
        for node_id in ready:
            result.append(node_id)
            del remaining[node_id]
        for dependencies in remaining.values():
            dependencies.difference_update(ready)
    return result


def _collect_input_hashes(state: dict[str, Any]) -> dict[str, str]:
    root = Path(state["project_root"]).resolve(strict=True)
    paths = sorted({value for node in state["nodes"].values() for value in node["inputs"]})
    current: dict[str, str] = {}
    for relative in paths:
        input_path = safe_join(root, relative, allow_missing=True)
        if input_path.is_file():
            current[relative] = sha256_file(input_path)
    return current


def check_evidence(path: Path) -> tuple[dict[str, Any], list[str]]:
    stale: list[str] = []

    def apply(state: dict[str, Any]) -> None:
        old_inputs = state["input_hashes"]
        current_inputs = _collect_input_hashes(state)
        changed_inputs = {key for key in set(old_inputs) | set(current_inputs) if old_inputs.get(key) != current_inputs.get(key)}
        affected = {node_id for node_id, node in state["nodes"].items() if changed_inputs.intersection(node["inputs"])}
        state["input_hashes"] = current_inputs
        state["dag_snapshot"] = current_snapshot(state["plan_hash"], current_inputs)
        for node_id, node in state["nodes"].items():
            item = _latest_evidence(node)
            if item is not None and _evidence_stale_reason(state, node_id, item) is not None:
                stale.append(f"{node_id}:{item['id']}")
                affected.add(node_id)
        if affected:
            affected = _invalidate_affected(state, affected)
            state["pending_resume"] = sorted(set(state["pending_resume"]) | affected)
            stale.extend(
                f"{node_id}:{item['id']}"
                for node_id in affected
                for item in state["nodes"][node_id]["evidence"]
                if item["snapshot"] != node_snapshot(state, node_id)
            )

    result = mutate_state(path, "evidence_checked", None, {}, apply)
    return result, sorted(set(stale))


def resume(dag_path: Path, state_path: Path, project_root: Path | None = None) -> tuple[dict[str, Any], list[str]]:
    dag = read_dag(dag_path)
    changed: list[str] = []
    root = project_root or Path(read_state(state_path)["project_root"])
    reject_symlink_components(root)
    root = root.resolve(strict=True)
    plan_hash, header_hash, input_hashes, definition_hashes = plan_hashes(dag, root, allow_missing_inputs=True)

    def apply(state: dict[str, Any]) -> None:
        if state["dag_id"] != dag["id"]:
            raise OrqivraError("DAG ID differs from stored state; initialize a new state for a new DAG.")
        if set(state["nodes"]) != set(definition_hashes):
            raise OrqivraError("DAG node IDs changed; use a new DAG ID to preserve attempt history.")
        affected: set[str] = set(state["pending_resume"])
        if state["plan_header_hash"] != header_hash:
            affected.update(state["nodes"])
        for node_id, definition_hash in definition_hashes.items():
            if state["nodes"][node_id]["definition_hash"] != definition_hash:
                affected.add(node_id)
        for node_id, node in state["nodes"].items():
            if any(state["input_hashes"].get(item) != input_hashes.get(item) for item in node["inputs"]):
                affected.add(node_id)
        state["plan_hash"] = plan_hash
        state["plan_header_hash"] = header_hash
        state["input_hashes"] = input_hashes
        state["dag_snapshot"] = current_snapshot(plan_hash, input_hashes)
        for node_id, source in node_definitions(dag).items():
            node = state["nodes"][node_id]
            node["definition_hash"] = definition_hashes[node_id]
            node["dependencies"] = list(source["dependencies"])
            node["inputs"] = list(source["inputs"])
            node["obligations"] = list(source.get("obligations", []))
        if affected:
            reopened = _reopen_affected(state, affected)
            changed.extend(sorted(reopened))
        for node_id, node in state["nodes"].items():
            if node["status"] in {"running", "verifying"}:
                if node["attempts"] and node["attempts"][-1]["verification_result"] == "pending":
                    node["attempts"][-1]["verification_result"] = "interrupted"
                    node["attempts"][-1]["verification_summary"] = "The prior session ended before verification; inspect current files before retrying."
                    node["status"] = "fix_required"
                    node["blocking_reason"] = "An interrupted attempt requires diagnosis before retry."
                    changed.append(node_id)
                elif not node["attempts"]:
                    node["status"] = "blocked"
                    node["blocking_reason"] = "The prior session ended before an attempt was recorded; inspect the work before resuming."
                    changed.append(node_id)
        state["pending_resume"] = []

    from .dag import node_definitions

    result = mutate_state(state_path, "state_resumed", None, {"plan_hash": plan_hash}, apply)
    return result, sorted(set(changed))


def report_state(state: dict[str, Any]) -> dict[str, Any]:
    required_gates = [
        {"node_id": node_id, **gate}
        for node_id, node in state["nodes"].items()
        for gate in node["obligations"]
        if gate["required"] and (gate["status"] != "VERIFIED" or not gate["evidence"])
    ]
    changed_inputs = _changed_input_paths(state)
    changed_input_set = set(changed_inputs)
    stale = []
    superseded_stale = []
    accepted_without_current_evidence = []
    for node_id, node in state["nodes"].items():
        relevant_inputs = {
            path
            for dependency in _dependency_closure(state, node_id)
            for path in state["nodes"][dependency]["inputs"]
        }
        inputs_changed = bool(changed_input_set.intersection(relevant_inputs))
        latest = _latest_evidence(node)
        for item in node["evidence"]:
            reason = "input_changed" if inputs_changed else _evidence_stale_reason(state, node_id, item)
            if reason:
                record = {"node_id": node_id, "evidence_id": item["id"], "reason": reason}
                if item is latest:
                    stale.append(record)
                else:
                    superseded_stale.append(record)
        if node["status"] == "accepted" and (
            inputs_changed
            or latest is None
            or latest["exit_code"] != 0
            or _evidence_stale_reason(state, node_id, latest) is not None
        ):
            accepted_without_current_evidence.append(node_id)
    all_accepted = all(node["status"] == "accepted" for node in state["nodes"].values())
    return {
        "schema_version": 1,
        "project_id": state["project_id"],
        "dag_id": state["dag_id"],
        "version": state["version"],
        "snapshot": state["dag_snapshot"],
        "nodes": {node_id: node["status"] for node_id, node in sorted(state["nodes"].items())},
        "ready_frontier": sorted(
            node_id
            for node_id, node in state["nodes"].items()
            if node["status"] in {"planned", "ready"}
            and all(state["nodes"][dependency]["status"] == "accepted" for dependency in node["dependencies"])
        ),
        "changed_inputs": changed_inputs,
        "stale_evidence": stale,
        "superseded_stale_evidence": superseded_stale,
        "accepted_without_current_evidence": accepted_without_current_evidence,
        "unresolved_required_gates": required_gates,
        "certified": (
            all_accepted
            and not accepted_without_current_evidence
            and not changed_inputs
            and not stale
            and not required_gates
        ),
    }
