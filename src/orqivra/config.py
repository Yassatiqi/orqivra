"""Project configuration loading and advisory client profile resolution.

Configuration is local data. This module validates it and renders effective
advice without invoking a provider or changing client settings.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .errors import InputOutputError, OrqivraError
from .installer import source_root
from .schema import load_json, require_valid

EDITIONS = ("codex", "claude-code", "gemini-cli")
ROLES = ("orchestrator", "implementer", "complex_implementer", "reviewer")
PROVIDER_FOR_EDITION = {"codex": "openai", "claude-code": "anthropic", "gemini-cli": "google"}
CONTROL_FOR_PROVIDER = {
    "openai": "codex.model_reasoning_effort",
    "anthropic": "claude-code.effort",
    "google": None,
}


def _parse_config_text(text: str, source: Path) -> Any:
    """Parse JSON with the shared cross-runtime restrictions."""

    def object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON object key: {key}")
            result[key] = value
        return result

    def safe_integer(raw: str) -> int:
        value = int(raw)
        if abs(value) > 9_007_199_254_740_991:
            raise ValueError("JSON integers must be within the interoperable safe range.")
        return value

    def reject_number(raw: str) -> Any:
        raise ValueError(f"Fractional JSON numbers are not supported: {raw}")

    def reject_constant(raw: str) -> Any:
        raise ValueError(f"Non-finite JSON numbers are not supported: {raw}")

    def reject_surrogates(value: Any, location: str = "$") -> None:
        if isinstance(value, str):
            if any(0xD800 <= ord(char) <= 0xDFFF for char in value):
                raise ValueError(f"Lone surrogate code point is not allowed at {location}.")
        elif isinstance(value, list):
            for index, item in enumerate(value):
                reject_surrogates(item, f"{location}/{index}")
        elif isinstance(value, dict):
            for key, item in value.items():
                reject_surrogates(key, f"{location}/<key>")
                reject_surrogates(item, f"{location}/{key}")

    try:
        value = json.loads(
            text,
            object_pairs_hook=object_without_duplicates,
            parse_int=safe_integer,
            parse_float=reject_number,
            parse_constant=reject_constant,
        )
        reject_surrogates(value)
        return value
    except (json.JSONDecodeError, ValueError) as exc:
        raise OrqivraError(f"Could not read valid UTF-8 JSON from {source}: {exc}") from exc


def _read_config_file(path: Path, *, explicit: bool) -> tuple[dict[str, Any], bool]:
    try:
        path.lstat()
    except FileNotFoundError:
        if explicit:
            raise InputOutputError(
                f"Explicit configuration file was not found: {path}. Create the file or omit --config to use defaults."
            )
        return {}, False
    except OSError as exc:
        raise InputOutputError(f"Could not inspect configuration file {path}: {exc}") from exc
    try:
        raw = path.read_bytes()
        text = raw.decode("utf-8")
    except OSError as exc:
        raise InputOutputError(f"Could not read configuration file {path}: {exc}") from exc
    except UnicodeDecodeError as exc:
        raise OrqivraError(f"Configuration file is not valid UTF-8: {path}: {exc}") from exc
    value = {} if not text.strip() else _parse_config_text(text, path)
    require_valid(value, "config.schema.json")
    return value, True


def _merge(base: Any, override: Any) -> Any:
    if isinstance(base, dict) and isinstance(override, dict):
        result = dict(base)
        for key, value in override.items():
            result[key] = _merge(result[key], value) if key in result else value
        return result
    # Arrays and scalars replace; explicit null is consequently preserved.
    return override


def load_project_config(config_path: Path | None, *, cwd: Path | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    """Load config, distinguishing default discovery from explicit selection."""
    root = source_root()
    defaults_path = root / "defaults" / "config.json"
    defaults = load_json(defaults_path)
    require_valid(defaults, "config.schema.json")
    if config_path is None:
        discovered = (cwd or Path.cwd()) / "orqivra.config.json"
        override, discovered_config = _read_config_file(discovered, explicit=False)
        source = {"kind": "file", "path": "orqivra.config.json"} if discovered_config else {"kind": "defaults", "path": None}
    else:
        override, _ = _read_config_file(config_path, explicit=True)
        source = {"kind": "file", "path": str(config_path)}
    effective = _merge(defaults, override)
    require_valid(effective, "config.schema.json")
    return effective, source


def _profile_and_catalog(edition: str) -> tuple[dict[str, Any], dict[str, Any]]:
    if edition not in EDITIONS:
        raise OrqivraError(f"Unknown edition: {edition}. Choose one of: {', '.join(EDITIONS)}.")
    root = source_root()
    profile = load_json(root / "profiles" / f"{edition}.json")
    if not isinstance(profile, dict):
        raise OrqivraError(f"The {edition} model profile must be a JSON object.")
    profile_schema = "profile-v2.schema.json" if profile.get("schema_version") == 2 else "profile.schema.json"
    require_valid(profile, profile_schema)
    if profile.get("edition") != edition:
        raise OrqivraError(f"Profile edition does not match requested edition: {edition}.")
    catalog = load_json(root / "models" / "catalog.json")
    require_valid(catalog, "model-catalog.schema.json")
    if profile.get("schema_version") == 2 and profile.get("catalog_version") != catalog.get("version"):
        raise OrqivraError(
            f"Profile '{profile['id']}' references model catalog version '{profile.get('catalog_version')}', "
            f"but the loaded catalog is version '{catalog.get('version')}'. Update the profile or install the matching catalog."
        )
    return profile, catalog


def _role_config(config: dict[str, Any], edition: str, role: str) -> dict[str, Any]:
    return config.get("editions", {}).get(edition, {}).get("roles", {}).get(role, {})


def _model_info(catalog: dict[str, Any], edition: str, provider: str, model: str, path: str) -> dict[str, Any]:
    entry = catalog.get("models", {}).get(model)
    if entry is None:
        raise OrqivraError(
            f"{path}.model '{model}' is not in the catalog. Add model_source: 'user-supplied' to use a custom model; compatibility will be unverified."
        )
    if entry.get("edition") != edition or entry.get("provider") != provider:
        raise OrqivraError(
            f"{path}.model '{model}' is catalogued for {entry.get('edition') or 'no supported client edition'}, not {edition}; choose a model supported by this edition or a genuinely custom model ID."
        )
    return entry


def _reasoning_result(
    *,
    configured: Any,
    has_override: bool,
    inherited: Any,
    model_changed: bool,
    model_entry: dict[str, Any] | None,
    model_source: str,
    path: str,
    provider: str,
) -> tuple[Any, str]:
    if has_override and configured is None:
        return None, "client-default"

    if has_override:
        selected = configured
        explicit = True
    else:
        selected = inherited
        explicit = False
        if selected is None:
            return None, "client-default"

    if not isinstance(selected, dict):
        return None, "client-default"
    control = selected.get("control")
    value = selected.get("value")
    native = CONTROL_FOR_PROVIDER[provider]
    if control != native or native is None:
        raise OrqivraError(
            f"{path}.reasoning.control '{control}' is incompatible with model/provider '{provider}'. Choose a compatible control or set reasoning to null to use the client-native default."
        )

    # Unknown custom-model capabilities are never used to justify an inherited
    # preference across a model change. Explicit settings remain visibly
    # unverified advice after provider/control shape validation.
    if model_source == "user-supplied":
        if not explicit and model_changed:
            raise OrqivraError(
                f"{path}.reasoning cannot be inherited after changing to a custom model. Set reasoning to null for the client-native default or provide an explicit provider control; compatibility will be unverified."
            )
        return selected, "UNVERIFIED custom model"

    reasoning_info = (model_entry or {}).get("reasoning")
    known_control = reasoning_info.get("control") if isinstance(reasoning_info, dict) else None
    known_values = reasoning_info.get("values") if isinstance(reasoning_info, dict) else None

    if known_control is not None and control != known_control:
        raise OrqivraError(
            f"{path}.reasoning.control '{control}' is incompatible with model/provider '{provider}'. Choose a compatible control or set reasoning to null to use the client-native default."
        )
    if isinstance(known_values, list) and value not in known_values:
        raise OrqivraError(
            f"{path}.reasoning.value '{value}' is incompatible with the selected model. Choose one of {', '.join(known_values)} or set reasoning to null to defer to the client-native default."
        )
    if not explicit and model_changed:
        if not isinstance(known_values, list):
            raise OrqivraError(
                f"{path}.reasoning cannot be safely inherited after the model changed because compatibility is unknown. Set reasoning to null for the client-native default or explicitly choose a documented compatible value."
            )
    if isinstance(known_values, list):
        return selected, "catalog-compatible"
    return selected, "UNVERIFIED; catalog does not enumerate compatible values"


def resolve_edition(config: dict[str, Any], edition: str) -> dict[str, Any]:
    profile, catalog = _profile_and_catalog(edition)
    expected_provider = PROVIDER_FOR_EDITION[edition]
    output_roles: dict[str, Any] = {}
    for role in ROLES:
        path = f"editions.{edition}.roles.{role}"
        base = profile["roles"][role]
        override = _role_config(config, edition, role)
        provider = override.get("provider") or base["provider"]
        if provider != expected_provider:
            raise OrqivraError(
                f"{path}.provider must be '{expected_provider}' for edition '{edition}', not '{provider}'."
            )
        model = override.get("model") or base["model"]
        model_changed = model != base["model"]
        source = override.get("model_source")
        if source is None:
            source = "catalog"
        if source == "user-supplied":
            if model in catalog.get("models", {}):
                raise OrqivraError(
                    f"{path}.model_source cannot be 'user-supplied' for catalog model '{model}'; use model_source: 'catalog'."
                )
            entry = None
        else:
            entry = _model_info(catalog, edition, provider, model, path)
        has_reasoning = "reasoning" in override
        reasoning, compatibility = _reasoning_result(
            configured=override.get("reasoning"),
            has_override=has_reasoning,
            inherited=base.get("reasoning"),
            model_changed=model_changed,
            model_entry=entry,
            model_source=source,
            path=path,
            provider=provider,
        )
        resolution = "configuration" if has_reasoning and reasoning is not None else ("profile" if reasoning is not None else "client-default")
        documentation_status = entry.get("status", "user-supplied") if entry else "user-supplied"
        # Catalog and profile data can describe compatibility, but cannot
        # qualify a client runtime. Only execution can change NOT_RUN; custom
        # identifiers remain unverified even before such an execution.
        runtime_qualification = "UNVERIFIED" if source == "user-supplied" else "NOT_RUN"
        client_instructions = []
        if entry and entry.get("client_support"):
            client_instructions.append(str(entry["client_support"]))
        if source == "user-supplied":
            client_instructions.append(
                "Configure this custom model in the client; ORQIVRA cannot verify its compatibility or availability. "
                "Custom model compatibility is UNVERIFIED."
            )
        elif compatibility.startswith("UNVERIFIED"):
            client_instructions.append(compatibility)
        if entry and entry.get("native_fallback"):
            client_instructions.append(str(entry["native_fallback"]))
        if not client_instructions:
            client_instructions.append(base.get("qualification", "Configure this model in the client; activation is not performed by ORQIVRA."))
        role_out: dict[str, Any] = {
            "provider": provider,
            "model": model,
            "model_source": source,
            "reasoning": reasoning,
            "reasoning_resolution": resolution,
            "documentation_status": documentation_status,
            "runtime_qualification": runtime_qualification,
            "activatable": False,
            "client_instructions": "; ".join(client_instructions),
        }
        output_roles[role] = role_out
    return {
        "schema_version": 1,
        "edition": edition,
        "profile_id": profile["id"],
        "catalog_version": catalog.get("version"),
        "config_source": {"kind": "defaults", "path": None},
        "workflow": {
            "preferred_route": config.get("workflow", {}).get("preferred_route", "recommend"),
            "preferred_parallelism": config.get("workflow", {}).get("preferred_parallelism", 2),
            "preferred_parallelism_advisory": True,
        },
        "fallback": {"policy": config.get("fallback", {}).get("policy", "none")},
        "roles": output_roles,
    }


def config_show(config_path: Path | None, edition: str, *, cwd: Path | None = None) -> dict[str, Any]:
    config, source = load_project_config(config_path, cwd=cwd)
    result = resolve_edition(config, edition)
    result["config_source"] = source
    return result


def markdown_show(result: dict[str, Any]) -> str:
    lines = [
        f"# ORQIVRA configuration: {result['edition']}",
        "",
        f"- Configuration source: `{result['config_source']['path'] or 'defaults'}`",
        f"- Model catalog: `{result['catalog_version']}`",
        f"- Preferred route: `{result['workflow'].get('preferred_route', 'recommend')}`",
        f"- Preferred parallelism: `{result['workflow'].get('preferred_parallelism', 2)}` (advisory maximum)",
        "- Fallback policy: `none` (ORQIVRA policy; client-native routing may still apply)",
        "- Provider calls: none; this output does not change client settings.",
        "",
        "## Roles",
        "",
    ]
    for role, details in result["roles"].items():
        lines.append(f"- `{role}`: `{details['model']}` ({details['provider']}); reasoning {details['reasoning']!r} ({details['reasoning_resolution']}); documentation `{details['documentation_status']}`; runtime `{details['runtime_qualification']}`; {details['client_instructions']}")
    return "\n".join(lines) + "\n"
