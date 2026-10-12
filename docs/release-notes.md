# ORQIVRA v0.2.0

ORQIVRA v0.2.0 prepares two independent ways to use the full CLI:

- Node.js 24 or newer with npm, without Python.
- Python 3.11 or newer with pipx, without Node.js.

The two implementations share JSON Schemas, canonical skills, profiles, edition adapters, fixtures, command names, state files, and installation manifests. Shared JSON uses compact UTF-8 serialization, recursively sorted object keys, safe integers, and SHA-256 hashes.

The release adds manifest-scoped skill installation with explicit targets, dry-run defaults, collision and modified-file refusal, verification, and safe uninstall in the Node implementation. Python packaging now includes the canonical runtime assets in the wheel and source archive.

## Installation status

The v0.2.0 wheel, source archive, and npm tarball are prepared as local artifacts. This task does not publish them to PyPI or npm. Use the local artifact instructions in [installation](installation.md); registry commands are conditional on a future public release.

## Qualification

The packaging and CLIs were exercised on Windows with Python 3.13.2 and Node.js 24.20.0. The client skill files were rendered and validated. Codex, Claude Code, and Gemini CLI runtime discovery and invocation were not tested. The profiles do not activate models or grant client permissions. See [compatibility](compatibility.md) and the final [release report](release-report.md).
