"""Deterministic edition packaging and manifest-scoped installation."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

import yaml

from . import __version__
from .errors import InputOutputError, OrqivraError, UnsafePathError
from .paths import reject_symlink_components, reject_symlink_path, safe_join, safe_relative_path, sha256_file
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
        if (candidate / "editions").is_dir() and (candidate / "schemas").is_dir():
            return candidate
    import sysconfig

    installed = Path(sysconfig.get_path("data")) / "share" / "orqivra"
    if (installed / "editions").is_dir():
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


def _is_linklike(path: Path) -> bool:
    junction_check = getattr(path, "is_junction", None)
    return path.is_symlink() or bool(junction_check and junction_check())


def parse_skill(path: Path) -> tuple[dict[str, Any], str]:
    if _is_linklike(path) or not path.is_file():
        raise UnsafePathError(f"Skill file must be regular and not a symlink or junction: {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise OrqivraError(f"Could not read skill file {path}: {exc}") from exc
    if not text.startswith("---\n"):
        raise OrqivraError(f"Skill frontmatter must begin with ---: {path}")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise OrqivraError(f"Skill frontmatter is not closed: {path}")
    try:
        metadata = yaml.safe_load(text[4:end])
    except yaml.YAMLError as exc:
        raise OrqivraError(f"Invalid YAML frontmatter in {path}: {exc}") from exc
    if not isinstance(metadata, dict):
        raise OrqivraError(f"Skill frontmatter must be a mapping: {path}")
    return metadata, text[end + 5 :]


def validate_skills(root: Path) -> dict[str, Any]:
    if not root.is_dir():
        raise OrqivraError(f"Skill directory does not exist: {root}")
    skill_files = sorted(root.rglob("SKILL.md"))
    if len(skill_files) != 4:
        raise OrqivraError(f"An edition must contain exactly four SKILL.md files; found {len(skill_files)}.")
    names: set[str] = set()
    results = []
    for path in skill_files:
        metadata, body = parse_skill(path)
        errors = validate_data(metadata, "skill.schema.json")
        if errors:
            raise OrqivraError(f"Invalid metadata in {path}:\n- " + "\n- ".join(errors))
        if metadata["name"] != path.parent.name:
            raise OrqivraError(f"Skill name must match its directory name: {path}")
        if metadata["name"] in names:
            raise OrqivraError(f"Duplicate skill name: {metadata['name']}")
        names.add(metadata["name"])
        word_count = len(body.split())
        if not 500 <= word_count <= 900:
            raise OrqivraError(f"Skill body must contain 500-900 words: {path} has {word_count}.")
        results.append({"name": metadata["name"], "words": word_count})
    if names != SKILL_NAMES:
        raise OrqivraError("Edition skills must be exactly: " + ", ".join(sorted(SKILL_NAMES)))
    return {"skills": results, "count": len(results)}


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
        if _is_linklike(item):
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
    native_root = skills_root(edition_root)
    validate_skills(native_root)
    profile = root / "profiles" / f"{edition}.json"
    require_valid(load_json(profile), "profile.schema.json")
    hashes = _copy_tree_files(native_root, output, prefix=native_root.relative_to(edition_root))
    for name, source in (
        (Path("profiles") / profile.name, profile),
        (Path("contracts") / "capabilities.md", root / "core" / "contracts" / "capabilities.md"),
    ):
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
        hashes[name.as_posix()] = sha256_file(target)
    hashes.update(_copy_tree_files(root / "schemas", output, prefix=Path("schemas")))
    return hashes


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
    if manifest.get("format_version") != 1 or manifest.get("owner") != "ORQIVRA" or manifest.get("edition") not in EDITIONS:
        raise OrqivraError("ORQIVRA ownership manifest is invalid or unsupported.")
    files = manifest.get("files")
    if not isinstance(files, dict):
        raise OrqivraError("ORQIVRA ownership manifest has no files map.")
    for relative, digest in files.items():
        normalized = safe_relative_path(relative)
        if normalized != relative or normalized.split("/", 1)[0] not in SKILL_NAMES:
            raise UnsafePathError(f"Manifest contains an invalid owned path: {relative}")
        if not isinstance(digest, str) or len(digest) != 64:
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
        if current.is_symlink() or (hasattr(current, "is_junction") and current.is_junction()):
            raise UnsafePathError(f"Installation path crosses a symlink: {current}")
        current = current / component
    return current


def install(edition: str, target: Path, selected: list[str] | None = None, *, apply: bool = False) -> dict[str, Any]:
    edition_root = _edition_dir(edition)
    native_root = skills_root(edition_root)
    validation = validate_skills(native_root)
    selected_names = sorted(set(selected or SKILL_NAMES))
    unknown = set(selected_names) - SKILL_NAMES
    if unknown:
        raise OrqivraError("Unknown skill selection: " + ", ".join(sorted(unknown)))
    target = _existing_target(target)
    manifest_path = target / MANIFEST_NAME
    current: dict[str, Any] | None = None
    if target.exists() and manifest_path.exists():
        current = _read_manifest(target)
        if current["edition"] != edition:
            raise OrqivraError("The target already belongs to another ORQIVRA edition.")
        for relative, old_hash in current["files"].items():
            path = safe_join(target, relative)
            if sha256_file(path) != old_hash:
                raise OrqivraError(f"An installed file was modified; refusing to overwrite it: {relative}")
    elif target.exists() and manifest_path.is_symlink():
        raise UnsafePathError(f"Installation manifest is a symlink: {manifest_path}")

    new_files = dict(current["files"]) if current else {}
    planned = []
    for name in selected_names:
        source_dir = native_root / name
        for source in sorted(source_dir.rglob("*")):
            if _is_linklike(source):
                raise UnsafePathError(f"Skill source contains a symlink or junction: {source}")
            if not source.is_file():
                continue
            relative = (Path(name) / source.relative_to(source_dir)).as_posix()
            digest = sha256_file(source)
            destination = _safe_destination(target, relative)
            owned_hash = new_files.get(relative)
            if destination.exists():
                if destination.is_symlink():
                    raise UnsafePathError(f"Installation destination is a symlink: {destination}")
                if owned_hash is None:
                    raise OrqivraError(f"Unowned destination already exists: {destination}")
                if sha256_file(destination) != owned_hash:
                    raise OrqivraError(f"An installed file was modified; refusing to overwrite it: {relative}")
            planned.append(relative)
            new_files[relative] = digest

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
        pending = []
        for relative in planned:
            destination = _safe_destination(target, relative)
            temp = destination.with_name(destination.name + ".orqivra-tmp")
            reject_symlink_path(temp)
            if temp.exists():
                raise OrqivraError(f"Temporary installation path already exists: {temp}")
            pending.append((relative, destination, temp))
        manifest_temp = manifest_path.with_name(manifest_path.name + ".orqivra-tmp")
        reject_symlink_path(manifest_temp)
        if manifest_temp.exists():
            raise OrqivraError(f"Temporary installation path already exists: {manifest_temp}")
        for name in selected_names:
            source_dir = native_root / name
            for source in sorted(source_dir.rglob("*")):
                if _is_linklike(source):
                    raise UnsafePathError(f"Skill source contains a symlink or junction: {source}")
                if not source.is_file():
                    continue
                relative = (Path(name) / source.relative_to(source_dir)).as_posix()
                _, destination, temp = next(item for item in pending if item[0] == relative)
                destination.parent.mkdir(parents=True, exist_ok=True)
                created_temp = False
                try:
                    with temp.open("xb") as stream:
                        created_temp = True
                        stream.write(source.read_bytes())
                        stream.flush()
                        os.fsync(stream.fileno())
                    os.replace(temp, destination)
                finally:
                    if created_temp:
                        temp.unlink(missing_ok=True)
        _write_manifest(target, manifest)
    return {"edition": edition, "target": str(target), "dry_run": not apply, "files": sorted(planned), "skill_count": len(validation["skills"])}


def _write_manifest(target: Path, manifest: dict[str, Any]) -> None:
    path = target / MANIFEST_NAME
    reject_symlink_path(path)
    temp = path.with_name(path.name + ".orqivra-tmp")
    reject_symlink_path(temp)
    if temp.exists():
        raise OrqivraError(f"Temporary installation path already exists: {temp}")
    created_temp = False
    try:
        with temp.open("x", encoding="utf-8", newline="\n") as stream:
            created_temp = True
            stream.write(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
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
    verified = verify_install(target)
    files = sorted(manifest["files"], reverse=True)
    if apply:
        for relative in files:
            safe_join(target, relative).unlink()
        (target / MANIFEST_NAME).unlink()
        directories = sorted({(target / Path(*relative.split("/"))).parent for relative in files}, key=lambda path: len(path.parts), reverse=True)
        for directory in directories:
            try:
                directory.rmdir()
            except OSError:
                pass
    return {"edition": manifest["edition"], "target": str(target), "dry_run": not apply, "removed_files": files, "verified_files": verified["verified_files"]}
