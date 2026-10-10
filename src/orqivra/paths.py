"""Path validation and content hashing without executing external data."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path, PurePosixPath, PureWindowsPath

from .errors import InputOutputError, UnsafePathError


def safe_relative_path(value: str, *, allow_subtree: bool = False) -> str:
    """Validate and normalize a project-relative POSIX path."""
    if not isinstance(value, str) or not value or "\x00" in value:
        raise UnsafePathError("Path must be a non-empty relative string.")
    raw = value.replace("\\", "/")
    if raw.startswith("/") or PureWindowsPath(value).drive:
        raise UnsafePathError(f"Absolute paths are not allowed: {value}")
    subtree = allow_subtree and raw.endswith("/**")
    raw = raw[:-3] if subtree else raw
    raw_parts = raw.split("/")
    if any(part in {"", ".", ".."} for part in raw_parts):
        raise UnsafePathError(f"Path traversal or empty path components are not allowed: {value}")
    parts = PurePosixPath(raw).parts
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise UnsafePathError(f"Path traversal is not allowed: {value}")
    if any("*" in part or "?" in part or ":" in part for part in parts):
        raise UnsafePathError(f"Only a trailing /** directory scope is supported: {value}")
    return "/".join(parts) + ("/**" if subtree else "")


def safe_join(root: Path, relative: str, *, allow_missing: bool = False) -> Path:
    """Join a relative path to a root and reject symlink traversal."""
    normalized = safe_relative_path(relative)
    reject_symlink_components(root)
    base = root.resolve(strict=True)
    if not base.is_dir():
        raise UnsafePathError(f"Selected root is not a directory: {root}")
    candidate = base.joinpath(*PurePosixPath(normalized).parts)
    try:
        candidate.absolute().relative_to(base)
    except ValueError as exc:
        raise UnsafePathError(f"Path escapes selected root: {relative}") from exc
    current = base
    for part in PurePosixPath(normalized).parts:
        current = current / part
        if _is_symlinklike(current):
            raise UnsafePathError(f"Symlinks are not allowed under the selected root: {current}")
        if not current.exists() and not allow_missing:
            raise InputOutputError(f"Path does not exist: {current}")
    try:
        candidate.resolve(strict=not allow_missing).relative_to(base)
    except (OSError, ValueError) as exc:
        raise UnsafePathError(f"Path escapes selected root: {relative}") from exc
    return candidate


def sha256_file(path: Path) -> str:
    """Return the lowercase SHA-256 digest of a regular file."""
    if path.is_symlink() or not path.is_file():
        raise UnsafePathError(f"Expected a regular non-symlink file: {path}")
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise InputOutputError(f"Could not read file: {path}") from exc
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest_json(value: object) -> str:
    """Hash canonical UTF-8 JSON data."""
    import json

    data = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return sha256_bytes(data)


def _is_symlinklike(path: Path) -> bool:
    junction_check = getattr(path, "is_junction", None)
    return path.is_symlink() or bool(junction_check and junction_check())


def reject_symlink_path(path: Path) -> None:
    """Reject a symlink at the selected path itself."""
    try:
        if _is_symlinklike(path):
            raise UnsafePathError(f"Selected path is a symlink: {path}")
    except OSError as exc:
        raise InputOutputError(f"Could not inspect path: {path}") from exc


def reject_symlink_components(path: Path) -> None:
    """Reject symlinks or junctions in an absolute path and its ancestors."""
    absolute = path.absolute()
    parts = absolute.parts
    if not parts:
        return
    current = Path(parts[0])
    for component in parts[1:]:
        current = current / component
        try:
            if _is_symlinklike(current):
                raise UnsafePathError(f"Path crosses a symlink or junction: {current}")
        except OSError as exc:
            raise InputOutputError(f"Could not inspect path: {current}") from exc


def is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=True))
    except (ValueError, OSError):
        return False
    return True
