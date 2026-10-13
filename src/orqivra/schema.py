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
                raise ValueError("Duplicate JSON object key.")
            result[key] = value
        return result

    def safe_integer(value: str) -> int:
        result = int(value)
        if abs(result) > 9_007_199_254_740_991:
            raise ValueError("JSON integers must be within the interoperable safe range.")
        return result

    def reject_fraction(value: str) -> Any:
        raise ValueError("Fractional JSON numbers are not supported.")

    def reject_constant(value: str) -> Any:
        raise ValueError("Non-finite JSON numbers are not supported.")

    def reject_lone_surrogates(value: Any) -> None:
        if isinstance(value, str):
            if any(0xD800 <= ord(character) <= 0xDFFF for character in value):
                raise ValueError("Lone surrogate code point is not allowed.")
        elif isinstance(value, list):
            for item in value:
                reject_lone_surrogates(item)
        elif isinstance(value, dict):
            for key, item in value.items():
                reject_lone_surrogates(key)
                reject_lone_surrogates(item)

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


def require_valid_config(data: Any) -> None:
    """Validate project configuration without formatting user-supplied values."""
    schema_name = "config.schema.json"
    schema = load_json(schema_directory() / schema_name)
    validator = Draft202012Validator(schema, registry=_registry(), format_checker=FormatChecker())
    errors = sorted(
        (_safe_config_error(error, schema) for error in validator.iter_errors(data)),
        key=lambda item: item,
    )
    if errors:
        raise OrqivraError(f"{schema_name} validation failed:\n- " + "\n- ".join(errors))


def _safe_config_error(error: Any, root_schema: dict[str, Any]) -> str:
    location, unknown_component = _safe_config_location(error.absolute_path, root_schema)
    validator = error.validator
    if validator == "type":
        expected = error.validator_value
        expected_text = " or ".join(expected) if isinstance(expected, list) else str(expected)
        return f"{location}: expected {expected_text}. {_type_remediation(expected)}"
    if validator == "enum":
        allowed = error.validator_value
        choices = ", ".join(_safe_schema_literal(item) for item in allowed)
        return f"{location}: must be one of the documented values: {choices}. Choose one of these values."
    if validator == "const":
        fixed = _safe_schema_literal(error.validator_value)
        return f"{location}: must use the schema-defined value {fixed}. Restore this documented value."
    if validator == "minimum":
        return f"{location}: must be at least {error.validator_value}. Increase this value to at least {error.validator_value}."
    if validator == "maximum":
        return f"{location}: must be at most {error.validator_value}. Reduce this value to no more than {error.validator_value}."
    if validator == "minLength":
        return f"{location}: must contain at least {error.validator_value} character(s). Enter a longer non-empty value."
    if validator == "required":
        missing = next((name for name in error.validator_value if name not in error.instance), None)
        suffix = f" '{missing}'" if isinstance(missing, str) else ""
        return f"{location}: add the required property{suffix}."
    if validator == "additionalProperties" or unknown_component:
        return f"{location}: remove unsupported properties; configuration keys are defined by the schema."
    return f"{location}: does not satisfy the configuration schema constraint."


def _safe_schema_literal(value: Any) -> str:
    """Render trusted schema metadata, never an invalid submitted value."""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _type_remediation(expected: Any) -> str:
    types = expected if isinstance(expected, list) else [expected]
    if len(types) != 1:
        return f"Set this field to one of these types: {' or '.join(str(item) for item in types)}."
    remediation = {
        "integer": "Set this field to a whole number.",
        "number": "Set this field to a number.",
        "string": "Set this field to a string.",
        "boolean": "Set this field to true or false.",
        "object": "Set this field to a JSON object.",
        "array": "Set this field to a JSON array.",
        "null": "Set this field to null.",
    }
    return remediation.get(types[0], "Set this field to the documented type.")


def _safe_config_location(components: Any, schema: dict[str, Any]) -> tuple[str, bool]:
    location = "$"
    current: Any = schema
    unknown = False
    for component in components:
        current = _resolve_local_config_ref(current, schema)
        if isinstance(component, int):
            items = current.get("items") if isinstance(current, dict) else None
            if not isinstance(items, dict):
                break
            location += f"[{component}]"
            current = items
            continue
        properties = current.get("properties", {}) if isinstance(current, dict) else {}
        if not isinstance(properties, dict) or component not in properties:
            unknown = True
            break
        location += f".{component}"
        current = properties[component]
    return location, unknown


def _resolve_local_config_ref(value: Any, root_schema: dict[str, Any]) -> Any:
    while isinstance(value, dict) and isinstance(value.get("$ref"), str):
        reference = value["$ref"]
        if not reference.startswith("#/"):
            break
        resolved: Any = root_schema
        for component in reference[2:].split("/"):
            if not isinstance(resolved, dict) or component not in resolved:
                return value
            resolved = resolved[component]
        value = resolved
    return value
