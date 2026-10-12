"""Deterministic edition packaging and manifest-scoped installation."""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

import yaml

from . import __version__
from .errors import InputOutputError, OrqivraError, UnsafePathError
from .paths import is_linklike, reject_symlink_components, reject_symlink_path, safe_join, safe_relative_path, sha256_bytes, sha256_file
from .schema import load_json, require_valid, validate_data

SKILL_NAMES = {
    "orqivra-orchestrate",
    "orqivra-architecture",
    "orqivra-verify",
    "orqivra-recover",
}
EDITIONS = {"codex", "claude-code", "gemini-cli"}
MANIFEST_NAME = ".orqivra-manifest.json"


def source_root() -> Path:
    candidates = [
        Path(__file__).resolve().parents[2],
    ]
    configured = os.environ.get("ORQIVRA_DATA_DIR")
    if configured:
        candidates.insert(0, Path(configured))
    for candidate in candidates:
        if (candidate / "editions").is_dir() and (candidate / "schemas").is_dir() and (candidate / "skills").is_dir():
            return candidate
    import sysconfig

    installed = Path(sysconfig.get_path("data")) / "share" / "orqivra"
    if (installed / "editions").is_dir() and (installed / "skills").is_dir():
        return installed
    raise InputOutputError("ORQIVRA edition resources were not found in this installation.")


def skills_root(edition_root: Path) -> Path:
    matches = [path for path in edition_root.rglob("SKILL.md") if path.parent.name in SKILL_NAMES]
    roots = {path.parent.parent for path in matches}
    for root in sorted(roots):
        present = {path.name for path in root.iterdir() if path.is_dir() and path.name in SKILL_NAMES}
        if present == SKILL_NAMES:
            return root
    raise OrqivraError(f"Edition does not contain all four required skills: {edition_root}")


def parse_skill(path: Path) -> tuple[dict[str, Any], str]:
    if is_linklike(path) or not path.is_file():
        raise UnsafePathError(f"Skill file must be regular and not a symlink or junction: {path}")
    try:
        text = path.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise OrqivraError(f"Could not read skill file {path}: {exc}") from exc
    return parse_skill_text(text, str(path))


def validate_skills(root: Path) -> dict[str, Any]:
    if not root.is_dir():
        raise OrqivraError(f"Skill directory does not exist: {root}")
    skill_files = sorted(root.rglob("SKILL.md"))
    if len(skill_files) != 4:
        raise OrqivraError(f"An edition must contain exactly four SKILL.md files; found {len(skill_files)}.")
    contents: dict[str, str] = {}
    for path in skill_files:
        if is_linklike(path) or not path.is_file():
            raise UnsafePathError(f"Skill file must be regular and not a symlink or junction: {path}")
        try:
            contents[path.parent.name] = path.read_bytes().decode("utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise OrqivraError(f"Could not read skill file {path}: {exc}") from exc
    return validate_skill_contents(contents)


def validate_skill_contents(contents: dict[str, str]) -> dict[str, Any]:
    if set(contents) != SKILL_NAMES:
        raise OrqivraError("Edition skills must be exactly: " + ", ".join(sorted(SKILL_NAMES)))
    results = []
    for name, text in sorted(contents.items()):
        metadata, body = parse_skill_text(text, name)
        errors = validate_data(metadata, "skill.schema.json")
        if errors:
            raise OrqivraError(f"Invalid metadata in {name}/SKILL.md:\n- " + "\n- ".join(errors))
        if metadata["name"] != name:
            raise OrqivraError(f"Skill name must match its directory name: {name}/SKILL.md")
        word_count = len(body.split())
        if not 500 <= word_count <= 900:
            raise OrqivraError(f"Skill body must contain 500-900 words: {name}/SKILL.md has {word_count}.")
        results.append({"name": metadata["name"], "words": word_count})
    return {"skills": results, "count": len(results)}


def parse_skill_text(text: str, source: str) -> tuple[dict[str, Any], str]:
    if text.startswith("\ufeff"):
        text = text[1:]
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if not text.startswith("---\n"):
        raise OrqivraError(f"Skill frontmatter must begin with ---: {source}")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise OrqivraError(f"Skill frontmatter is not closed: {source}")
    try:
        metadata = yaml.safe_load(text[4:end])
    except yaml.YAMLError as exc:
        raise OrqivraError(f"Invalid YAML frontmatter in {source}: {exc}") from exc
    if not isinstance(metadata, dict):
        raise OrqivraError(f"Skill frontmatter must be a mapping: {source}")
    return metadata, text[end + 5 :]


def render_edition_skills(edition: str) -> tuple[dict[str, str], dict[str, Any]]:
    edition_root = _edition_dir(edition)
    root = source_root()
    adapter_path = edition_root / "adapter.json"
    if is_linklike(adapter_path) or not adapter_path.is_file():
        raise UnsafePathError(f"Edition adapter must be a regular file: {adapter_path}")
    adapter = load_json(adapter_path)
    require_valid(adapter, "edition-adapter.schema.json")
    if adapter["edition"] != edition:
        raise OrqivraError(f"Edition adapter ID does not match its directory: {adapter_path}")
    expected_paths = {
        "codex": ".agents/skills",
        "claude-code": ".claude/skills",
        "gemini-cli": ".gemini/skills",
    }
    if adapter["native_skills_path"] != expected_paths[edition]:
        raise OrqivraError(f"Edition adapter has an unexpected native skill path: {adapter_path}")
    rendered: dict[str, str] = {}
    marker = "<!-- ORQIVRA_CLIENT_ADAPTER -->"
    adapter_section = f"## {adapter['client_name']} discovery, invocation, and permissions\n\n{adapter['guidance']}"
    for name in sorted(SKILL_NAMES):
        source = root / "skills" / name / "SKILL.md"
        if is_linklike(source) or not source.is_file():
            raise UnsafePathError(f"Canonical skill source must be a regular file: {source}")
        try:
            text = source.read_bytes().decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
        except (OSError, UnicodeDecodeError) as exc:
            raise OrqivraError(f"Could not read canonical skill source {source}: {exc}") from exc
        if text.count(marker) != 1:
            raise OrqivraError(f"Canonical skill source must contain one client adapter marker: {source}")
        rendered[name] = text.replace(marker, adapter_section)
    validation = validate_skill_contents(rendered)
    return rendered, validation


def _edition_dir(edition: str) -> Path:
    if edition not in EDITIONS:
        raise OrqivraError(f"Unknown edition: {edition}")
    path = source_root() / "editions" / edition
    if not path.is_dir():
        raise OrqivraError(f"Edition resources are missing: {edition}")
    return path


def _native_relative(source: Path, edition_root: Path) -> Path:
    return source.relative_to(edition_root)


def _copy_tree_files(source: Path, destination: Path, *, prefix: Path = Path()) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for item in sorted(source.rglob("*")):
        relative = item.relative_to(source)
        if is_linklike(item):
            raise UnsafePathError(f"Edition source contains a symlink or junction: {item}")
        if item.is_dir():
            continue
        if not item.is_file():
            raise UnsafePathError(f"Edition source contains a non-regular file: {item}")
        target_relative = prefix / relative
        target = destination / target_relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(item.read_bytes())
        hashes[target_relative.as_posix()] = sha256_file(target)
    return hashes


def _bundle_files(edition: str, output: Path) -> dict[str, str]:
    root = source_root()
    edition_root = _edition_dir(edition)
    rendered, _ = render_edition_skills(edition)
    adapter = load_json(edition_root / "adapter.json")
    native_path = Path(adapter["native_skills_path"])
    profile = root / "profiles" / f"{edition}.json"
    require_valid(load_json(profile), "profile.schema.json")
    hashes: dict[str, str] = {}
    for name, text in rendered.items():
        relative = native_path / name / "SKILL.md"
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = text.encode("utf-8")
        target.write_bytes(payload)
        hashes[relative.as_posix()] = sha256_bytes(payload)
    for name, source in (
        (Path("profiles") / profile.name, profile),
        (Path("contracts") / "capabilities.md", root / "core" / "contracts" / "capabilities.md"),
        (Path("editions") / edition / "adapter.json", edition_root / "adapter.json"),
        (Path("LICENSE"), root / "LICENSE"),
    ):
        hashes[name.as_posix()] = _copy_regular_file(source, output / name)
    hashes.update(_copy_tree_files(root / "schemas", output, prefix=Path("schemas")))
    return hashes


def _copy_regular_file(source: Path, target: Path) -> str:
    if is_linklike(source) or not source.is_file():
        raise UnsafePathError(f"Bundle source must be a regular file: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = source.read_bytes()
    target.write_bytes(payload)
    return sha256_bytes(payload)


def build(edition: str, output: Path) -> list[Path]:
    editions = sorted(EDITIONS) if edition == "all" else [edition]
    if edition != "all" and edition not in EDITIONS:
        raise OrqivraError(f"Unknown edition: {edition}")
    target = output.absolute()
    reject_symlink_components(target)
    reject_symlink_path(target)
    if target.exists() and (not target.is_dir() or any(target.iterdir())):
        raise OrqivraError(f"Build output must be a new or empty directory: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    stage: Path | None = Path(tempfile.mkdtemp(prefix=f".{target.name}.orqivra-", dir=target.parent))
    staged_paths = []
    try:
        for name in editions:
            edition_out = stage / name
            edition_out.mkdir()
            hashes = _bundle_files(name, edition_out)
            manifest = {
                "format_version": 1,
                "framework_version": __version__,
                "edition": name,
                "files": dict(sorted(hashes.items())),
            }
            (edition_out / "BUILD-MANIFEST.json").write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            staged_paths.append(target / name)
        if target.exists():
            target.rmdir()
        os.replace(stage, target)
        stage = None
    except OSError as exc:
        raise InputOutputError(f"Could not build edition bundle: {exc}") from exc
    finally:
        if stage is not None and stage.exists():
            shutil.rmtree(stage)
    return staged_paths


def _read_manifest(target: Path) -> dict[str, Any]:
    manifest_path = target / MANIFEST_NAME
    reject_symlink_path(manifest_path)
    if not manifest_path.is_file():
        raise OrqivraError(f"No ORQIVRA ownership manifest found under {target}.")
    manifest = load_json(manifest_path)
    if (
        not isinstance(manifest, dict)
        or type(manifest.get("format_version")) is not int
        or manifest["format_version"] != 1
        or manifest.get("owner") != "ORQIVRA"
        or not isinstance(manifest.get("edition"), str)
        or manifest["edition"] not in EDITIONS
    ):
        raise OrqivraError("ORQIVRA ownership manifest is invalid or unsupported.")
    files = manifest.get("files")
    if not isinstance(files, dict):
        raise OrqivraError("ORQIVRA ownership manifest has no files map.")
    for relative, digest in files.items():
        normalized = safe_relative_path(relative)
        if normalized != relative or normalized.split("/", 1)[0] not in SKILL_NAMES:
            raise UnsafePathError(f"Manifest contains an invalid owned path: {relative}")
        if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            raise OrqivraError(f"Manifest contains an invalid file digest: {relative}")
    return manifest


def _existing_target(target: Path) -> Path:
    target = target.absolute()
    reject_symlink_components(target)
    if target.exists() and not target.is_dir():
        raise OrqivraError(f"Installation target must be a directory: {target}")
    return target


def _safe_destination(root: Path, relative: str) -> Path:
    normalized = safe_relative_path(relative)
    current = root
    for component in normalized.split("/"):
        if is_linklike(current):
            raise UnsafePathError(f"Installation path crosses a symlink: {current}")
        current = current / component
    return current


def _assert_install_destination_state(target: Path, relative: str, expected_hash: str | None) -> Path:
    """Recheck a destination's ownership immediately before replacing it.

    These metadata and digest checks reduce race windows; they cannot make a
    path-based filesystem operation race-proof against a concurrent writer.
    """
    reject_symlink_components(target)
    destination = _safe_destination(target, relative)
    reject_symlink_components(destination)
    reject_symlink_path(destination)
    if expected_hash is None:
        if destination.exists():
            raise OrqivraError(f"An unowned destination appeared during installation: {destination}")
    else:
        try:
            actual = sha256_file(destination)
        except OrqivraError as exc:
            raise OrqivraError(f"An installed destination changed during installation: {relative}") from exc
        if actual != expected_hash:
            raise OrqivraError(f"An installed destination was modified during installation: {relative}")
    return destination


def _assert_manifest_state(target: Path, expected_hash: str | None) -> Path:
    """Ensure manifest ownership is unchanged immediately before replacement/removal."""
    reject_symlink_components(target)
    manifest_path = target / MANIFEST_NAME
    reject_symlink_components(manifest_path)
    reject_symlink_path(manifest_path)
    if expected_hash is None:
        if manifest_path.exists():
            raise OrqivraError("An installation manifest appeared during the operation; refusing to overwrite it.")
    else:
        try:
            actual = sha256_file(manifest_path)
        except OrqivraError as exc:
            raise OrqivraError("The ORQIVRA installation manifest changed during the operation.") from exc
        if actual != expected_hash:
            raise OrqivraError("The ORQIVRA installation manifest changed during the operation.")
    return manifest_path


def install(edition: str, target: Path, selected: list[str] | None = None, *, apply: bool = False) -> dict[str, Any]:
    rendered, validation = render_edition_skills(edition)
    selected_names = sorted(set(selected or SKILL_NAMES))
    unknown = set(selected_names) - SKILL_NAMES
    if unknown:
        raise OrqivraError("Unknown skill selection: " + ", ".join(sorted(unknown)))
    target = _existing_target(target)
    manifest_path = target / MANIFEST_NAME
    current: dict[str, Any] | None = None
    manifest_hash: str | None = None
    if target.exists() and manifest_path.exists():
        current = _read_manifest(target)
        manifest_hash = sha256_file(manifest_path)
        if current["edition"] != edition:
            raise OrqivraError("The target already belongs to another ORQIVRA edition.")
        for relative, old_hash in current["files"].items():
            path = safe_join(target, relative)
            if sha256_file(path) != old_hash:
                raise OrqivraError(f"An installed file was modified; refusing to overwrite it: {relative}")
    elif target.exists() and is_linklike(manifest_path):
        raise UnsafePathError(f"Installation manifest is a symlink: {manifest_path}")

    new_files = dict(current["files"]) if current else {}
    planned = []
    payloads: dict[str, bytes] = {}
    for name in selected_names:
        relative = (Path(name) / "SKILL.md").as_posix()
        payload = rendered[name].encode("utf-8")
        digest = sha256_bytes(payload)
        destination = _safe_destination(target, relative)
        owned_hash = new_files.get(relative)
        if destination.exists():
            if is_linklike(destination):
                raise UnsafePathError(f"Installation destination is a symlink: {destination}")
            if owned_hash is None:
                raise OrqivraError(f"Unowned destination already exists: {destination}")
            if sha256_file(destination) != owned_hash:
                raise OrqivraError(f"An installed file was modified; refusing to overwrite it: {relative}")
        planned.append(relative)
        new_files[relative] = digest
        payloads[relative] = payload

    manifest = {
        "format_version": 1,
        "owner": "ORQIVRA",
        "framework_version": __version__,
        "edition": edition,
        "skills": sorted({relative.split("/", 1)[0] for relative in new_files}),
        "files": dict(sorted(new_files.items())),
    }
    if apply:
        target.mkdir(parents=True, exist_ok=True)
        reject_symlink_components(target)
        pending = []
        for relative in planned:
            destination = _safe_destination(target, relative)
            temp = destination.with_name(destination.name + ".orqivra-tmp")
            reject_symlink_path(temp)
            if temp.exists():
                raise OrqivraError(f"Temporary installation path already exists: {temp}")
            pending.append((relative, destination, temp, payloads[relative], current["files"].get(relative) if current else None))
        manifest_temp = manifest_path.with_name(manifest_path.name + ".orqivra-tmp")
        reject_symlink_path(manifest_temp)
        if manifest_temp.exists():
            raise OrqivraError(f"Temporary installation path already exists: {manifest_temp}")
        for relative, destination, temp, payload, expected_hash in pending:
            destination.parent.mkdir(parents=True, exist_ok=True)
            reject_symlink_components(destination)
            created_temp = False
            try:
                with temp.open("xb") as stream:
                    created_temp = True
                    stream.write(payload)
                    stream.flush()
                    os.fsync(stream.fileno())
                reject_symlink_components(temp)
                reject_symlink_path(temp)
                if sha256_file(temp) != sha256_bytes(payload):
                    raise OrqivraError(f"Staged installation file changed before replacement: {relative}")
                destination = _assert_install_destination_state(target, relative, expected_hash)
                os.replace(temp, destination)
            finally:
                if created_temp:
                    temp.unlink(missing_ok=True)
        _write_manifest(target, manifest, expected_hash=manifest_hash)
    return {"edition": edition, "target": str(target), "dry_run": not apply, "files": sorted(planned), "skill_count": len(validation["skills"])}


def _write_manifest(target: Path, manifest: dict[str, Any], *, expected_hash: str | None = None) -> None:
    path = target / MANIFEST_NAME
    reject_symlink_path(path)
    temp = path.with_name(path.name + ".orqivra-tmp")
    reject_symlink_path(temp)
    if temp.exists():
        raise OrqivraError(f"Temporary installation path already exists: {temp}")
    created_temp = False
    payload = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    try:
        with temp.open("x", encoding="utf-8", newline="\n") as stream:
            created_temp = True
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        reject_symlink_components(temp)
        reject_symlink_path(temp)
        if sha256_file(temp) != sha256_bytes(payload.encode("utf-8")):
            raise OrqivraError(f"Staged installation manifest changed before replacement: {temp}")
        _assert_manifest_state(target, expected_hash)
        os.replace(temp, path)
    finally:
        if created_temp:
            temp.unlink(missing_ok=True)


def verify_install(target: Path) -> dict[str, Any]:
    target = _existing_target(target)
    manifest = _read_manifest(target)
    mismatches = []
    for relative, expected in sorted(manifest["files"].items()):
        try:
            actual = sha256_file(safe_join(target, relative))
        except OrqivraError:
            actual = None
        if actual != expected:
            mismatches.append(relative)
    if mismatches:
        raise OrqivraError("Installed files are missing or modified: " + ", ".join(mismatches))
    return {"edition": manifest["edition"], "target": str(target), "verified_files": len(manifest["files"]), "valid": True}


def uninstall(target: Path, *, apply: bool = False) -> dict[str, Any]:
    target = _existing_target(target)
    manifest = _read_manifest(target)
    manifest_hash = sha256_file(target / MANIFEST_NAME)
    verified = verify_install(target)
    files = sorted(manifest["files"], reverse=True)
    if apply:
        for relative in files:
            _assert_manifest_state(target, manifest_hash)
            destination = safe_join(target, relative)
            reject_symlink_components(destination)
            reject_symlink_path(destination)
            if sha256_file(destination) != manifest["files"][relative]:
                raise OrqivraError(f"An installed file was modified; refusing to remove it: {relative}")
            destination.unlink()
        manifest_path = _assert_manifest_state(target, manifest_hash)
        manifest_path.unlink()
        directories = sorted({(target / Path(*relative.split("/"))).parent for relative in files}, key=lambda path: len(path.parts), reverse=True)
        for directory in directories:
            try:
                directory.rmdir()
            except OSError:
                pass
    return {"edition": manifest["edition"], "target": str(target), "dry_run": not apply, "removed_files": files, "verified_files": verified["verified_files"]}
