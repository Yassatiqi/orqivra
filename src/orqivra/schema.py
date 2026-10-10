"""JSON Schema loading and validation with the declared jsonschema dependency."""

from __future__ import annotations

import json
import sys
import sysconfig
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

from .errors import InputOutputError, OrqivraError


def schema_directory() -> Path:
    """Locate schemas in a source checkout or a standard installation."""
    candidates = [
        Path(__file__).resolve().parents[2] / "schemas",
        Path(sysconfig.get_path("data")) / "share" / "orqivra" / "schemas",
        Path(sys.prefix) / "share" / "orqivra" / "schemas",
    ]
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    raise InputOutputError("ORQIVRA schemas were not found in this installation.")


def load_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as stream:
            return json.load(stream)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise OrqivraError(f"Could not read valid UTF-8 JSON from {path}: {exc}") from exc


def _registry() -> Registry:
    resources: list[tuple[str, Resource[Any]]] = []
    for schema_path in sorted(schema_directory().glob("*.schema.json")):
        schema = load_json(schema_path)
        Draft202012Validator.check_schema(schema)
        schema_id = schema.get("$id")
        if not schema_id:
            raise OrqivraError(f"Schema is missing $id: {schema_path.name}")
        resources.append((schema_id, Resource.from_contents(schema)))
    return Registry().with_resources(resources)


def validate_data(data: Any, schema_name: str) -> list[str]:
    schema_path = schema_directory() / schema_name
    if not schema_path.is_file():
        raise OrqivraError(f"Unknown schema: {schema_name}")
    schema = load_json(schema_path)
    errors = Draft202012Validator(schema, registry=_registry(), format_checker=FormatChecker()).iter_errors(data)
    return sorted(f"{error.json_path or '$'}: {error.message}" for error in errors)


def require_valid(data: Any, schema_name: str) -> None:
    errors = validate_data(data, schema_name)
    if errors:
        raise OrqivraError(f"{schema_name} validation failed:\n- " + "\n- ".join(errors))
