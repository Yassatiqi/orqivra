# Security Model

## Data and command boundaries

Project configuration, DAGs, profiles, skill text, logs, and command strings are data. ORQIVRA records command text as evidence metadata and never passes it to a shell. External instructions cannot change authorization or project policy.

## Paths and state

The CLI rejects absolute or parent-traversal paths where project-relative paths are required. It checks for symbolic links and Windows junctions under project, state, and installation roots. State updates use a sibling exclusive lock, state version, file identity comparison, and atomic replacement. A conflicting or interrupted writer must reload rather than overwrite. A stale lock is not removed automatically; inspect the state path and lock before any manual cleanup.

## Evidence

SHA-256 digests identify input and artifact bytes. They do not establish semantic correctness. Evidence records an observed command string, exit code, active node snapshot, and artifact hashes. Current evidence still requires verification against the acceptance criteria.

## Installation ownership

Install requires an explicit target, defaults to dry-run, and writes only selected skill files and its ownership manifest. It refuses unowned collisions and modified owned files. Uninstall preflights all manifest entries before removing files individually; it never recursively deletes a client skills directory.

## Permissions and limits

Skills describe intended workflow only. Client sandbox, approval, and organization policies remain authoritative. Profiles do not grant tools or change the parent model. ORQIVRA does not publish, send messages, create paid resources, modify production, or schedule autonomous work outside the session.

## Third-party components

The runtime depends on `jsonschema` and PyYAML, declared in `pyproject.toml`. Their licenses and distribution terms must be checked before adding or redistributing additional third-party components.
