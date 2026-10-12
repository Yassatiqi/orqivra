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
    def object_without_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON object key: {key}")
            result[key] = value
        return result

    def safe_integer(value: str) -> int:
        result = int(value)
        if abs(result) > 9_007_199_254_740_991:
            raise ValueError("JSON integers must be within the interoperable safe range.")
        return result

    def reject_fraction(value: str) -> Any:
        raise ValueError(f"Fractional JSON numbers are not supported: {value}")

    def reject_constant(value: str) -> Any:
        raise ValueError(f"Non-finite JSON numbers are not supported: {value}")

    def reject_lone_surrogates(value: Any, location: str = "$") -> None:
        if isinstance(value, str):
            if any(0xD800 <= ord(character) <= 0xDFFF for character in value):
                raise ValueError(f"Lone surrogate code point is not allowed at {location}.")
        elif isinstance(value, list):
            for index, item in enumerate(value):
                reject_lone_surrogates(item, f"{location}/{index}")
        elif isinstance(value, dict):
            for key, item in value.items():
                reject_lone_surrogates(key, f"{location}/<key>")
                reject_lone_surrogates(item, f"{location}/{key}")

    try:
        with path.open("r", encoding="utf-8") as stream:
            value = json.load(
                stream,
                object_pairs_hook=object_without_duplicate_keys,
                parse_int=safe_integer,
                parse_float=reject_fraction,
                parse_constant=reject_constant,
            )
        reject_lone_surrogates(value)
        return value
    except OSError as exc:
        raise InputOutputError(f"Could not read {path}: {exc}") from exc
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
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
