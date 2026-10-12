"""DAG validation, ownership analysis, and deterministic READY frontiers."""

from __future__ import annotations

from collections import defaultdict, deque
from pathlib import Path
from typing import Any

from .errors import OrqivraError
from .paths import reject_symlink_components, safe_relative_path, sha256_file, digest_json
from .schema import load_json, require_valid


def read_dag(path: Path) -> dict[str, Any]:
    dag = load_json(path)
    require_valid(dag, "dag.schema.json")
    validate_graph(dag)
    return dag


def _scope_root(scope: str) -> tuple[str, ...]:
    normalized = safe_relative_path(scope, allow_subtree=True)
    raw = normalized[:-3] if normalized.endswith("/**") else normalized
    return tuple(raw.split("/"))


def _scopes_overlap(left: str, right: str) -> bool:
    a, b = _scope_root(left), _scope_root(right)
    shorter = min(len(a), len(b))
    return a[:shorter] == b[:shorter]


def _dependency_reachability(nodes: dict[str, dict[str, Any]]) -> dict[str, set[str]]:
    reachable: dict[str, set[str]] = {node_id: set() for node_id in nodes}
    for node_id in nodes:
        pending = list(nodes[node_id]["dependencies"])
        while pending:
            dependency = pending.pop()
            if dependency not in reachable[node_id]:
                reachable[node_id].add(dependency)
                pending.extend(nodes[dependency]["dependencies"])
    return reachable


def validate_graph(dag: dict[str, Any]) -> None:
    raw_nodes = dag.get("nodes")
    if not isinstance(raw_nodes, list):
        raise OrqivraError("DAG nodes must be an array.")
    nodes: dict[str, dict[str, Any]] = {}
    for node in raw_nodes:
        node_id = node.get("id")
        if node_id in nodes:
            raise OrqivraError(f"Duplicate node ID: {node_id}")
        nodes[node_id] = node
        if node_id in node.get("dependencies", []):
            raise OrqivraError(f"Node cannot depend on itself: {node_id}")
        for path in node.get("inputs", []):
            safe_relative_path(path)
        for scope in node.get("file_scope", []):
            safe_relative_path(scope, allow_subtree=True)
    for node_id, node in nodes.items():
        for dependency in node["dependencies"]:
            if dependency not in nodes:
                raise OrqivraError(f"Node {node_id} has missing dependency: {dependency}")

    indegree = {node_id: len(node["dependencies"]) for node_id, node in nodes.items()}
    dependents: dict[str, list[str]] = defaultdict(list)
    for node_id, node in nodes.items():
        for dependency in node["dependencies"]:
            dependents[dependency].append(node_id)
    queue = deque(sorted(node_id for node_id, degree in indegree.items() if degree == 0))
    visited = 0
    while queue:
        node_id = queue.popleft()
        visited += 1
        for dependent in sorted(dependents[node_id]):
            indegree[dependent] -= 1
            if indegree[dependent] == 0:
                queue.append(dependent)
    if visited != len(nodes):
        cyclic = sorted(node_id for node_id, degree in indegree.items() if degree > 0)
        raise OrqivraError("DAG contains a dependency cycle involving: " + ", ".join(cyclic))

    reachable = _dependency_reachability(nodes)
    node_ids = sorted(nodes)
    for index, left_id in enumerate(node_ids):
        for right_id in node_ids[index + 1 :]:
            if left_id in reachable[right_id] or right_id in reachable[left_id]:
                continue
            for left_scope in nodes[left_id]["file_scope"]:
                for right_scope in nodes[right_id]["file_scope"]:
                    if _scopes_overlap(left_scope, right_scope):
                        raise OrqivraError(
                            f"Independent nodes {left_id} and {right_id} have overlapping file scopes: "
                            f"{left_scope} and {right_scope}"
                        )


def node_definitions(dag: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {node["id"]: node for node in dag["nodes"]}


def plan_hashes(
    dag: dict[str, Any], project_root: Path, *, allow_missing_inputs: bool = False
) -> tuple[str, str, dict[str, str], dict[str, str]]:
    """Return plan hash, header hash, input hashes, and per-node definition hashes."""
    reject_symlink_components(project_root)
    project_root = project_root.resolve(strict=True)
    definitions = node_definitions(dag)
    header = {key: value for key, value in dag.items() if key != "nodes"}
    plan = digest_json(dag)
    header_hash = digest_json(header)
    input_paths = sorted({value for node in dag["nodes"] for value in node["inputs"]})
    input_hashes: dict[str, str] = {}
    for path in input_paths:
        input_file = _safe_input(project_root, path, allow_missing=allow_missing_inputs)
        if input_file.is_file():
            input_hashes[path] = sha256_file(input_file)
        elif input_file.exists():
            raise OrqivraError(f"Input path is not a regular file: {path}")
        elif not allow_missing_inputs:
            raise OrqivraError(f"Required input file does not exist: {path}")
    definition_hashes: dict[str, str] = {}
    for node_id, node in definitions.items():
        definition = {key: value for key, value in node.items() if key not in {"status", "attempts", "evidence", "blocking_reason"}}
        definition_hashes[node_id] = digest_json(definition)
    return plan, header_hash, input_hashes, definition_hashes


def _safe_input(root: Path, relative: str, *, allow_missing: bool = False) -> Path:
    from .paths import safe_join

    return safe_join(root, relative, allow_missing=allow_missing)


def current_snapshot(plan_hash: str, input_hashes: dict[str, str]) -> str:
    return "sha256:" + digest_json({"plan_hash": plan_hash, "input_hashes": input_hashes})


def ready_frontier(dag: dict[str, Any], state: dict[str, Any] | None = None) -> list[str]:
    statuses: dict[str, str] = {}
    for node in dag["nodes"]:
        node_id = node["id"]
        if state is not None and node_id in state["nodes"]:
            statuses[node_id] = state["nodes"][node_id]["status"]
        else:
            statuses[node_id] = node["status"]
    ready = []
    for node in dag["nodes"]:
        node_id = node["id"]
        if statuses[node_id] not in {"planned", "ready"}:
            continue
        if all(statuses.get(dependency) == "accepted" for dependency in node["dependencies"]):
            ready.append(node_id)
    return sorted(ready)
