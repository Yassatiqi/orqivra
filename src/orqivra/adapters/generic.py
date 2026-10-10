"""Generic project adapter with no provider- or MIP-specific obligations."""

from __future__ import annotations

from typing import Any


def normalize_project(project: dict[str, Any]) -> dict[str, Any]:
    """Return a shallow normalized project without adding inferred policy."""
    result = dict(project)
    result.setdefault("adapter", "generic")
    result.setdefault("obligations", [])
    return result
