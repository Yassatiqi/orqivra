"""MIP adapter for external validation obligations."""

from __future__ import annotations

from typing import Any


def normalize_project(project: dict[str, Any]) -> dict[str, Any]:
    """Preserve MIP obligations without applying them to generic projects."""
    result = dict(project)
    result["adapter"] = "mip"
    result["obligations"] = [dict(obligation) for obligation in project.get("obligations", [])]
    for obligation in result["obligations"]:
        obligation.setdefault("status", "DEFERRED_EXTERNAL")
        obligation["evidence"] = list(obligation.get("evidence", []))
    return result


def resolve_obligation(
    obligation: dict[str, Any],
    *,
    final_validation_sprint: bool,
    external_validation_observed: bool,
    evidence_ids: list[str],
) -> dict[str, Any]:
    """Resolve an external check only with direct final-sprint observations."""
    result = dict(obligation)
    if not final_validation_sprint or not external_validation_observed or not evidence_ids:
        result["status"] = "DEFERRED_EXTERNAL"
        result["evidence"] = list(obligation.get("evidence", []))
        return result
    result["status"] = "VERIFIED"
    result["evidence"] = sorted(set(obligation.get("evidence", [])) | set(evidence_ids))
    return result
