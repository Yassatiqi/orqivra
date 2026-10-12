# Security Model

## Reporting security vulnerabilities

This local pre-release tree has no verified public repository or maintainer security contact. Before publishing, maintainers should enable a private vulnerability-reporting route on the public repository or add a verified security contact and response guidance.

When the repository is public, use GitHub's private vulnerability-reporting flow if it is enabled. If it is unavailable, open a public issue asking maintainers for a private contact, without posting exploit details. Include the affected ORQIVRA version, runtime and operating system, reproducible steps, and impact; omit credentials, personal data, and third-party private data. See [GitHub's private vulnerability reporting guidance](https://docs.github.com/en/code-security/how-tos/report-and-fix-vulnerabilities/report-privately).

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

## Third-party components and packaged assets

The Python runtime declares `jsonschema>=4.22,<5` and `PyYAML>=6,<7`. The inspected Python 3.13.2 pipx environment resolved jsonschema 4.26.0 and PyYAML 6.0.3; both distributions reported MIT metadata. That jsonschema environment also installed attrs 26.1.0, jsonschema-specifications 2025.9.1, referencing 0.37.0, and rpds-py 2026.9.1, each reporting MIT metadata. These are installed as separate dependencies, not copied into ORQIVRA's wheel or source archive.

The npm package has no production dependencies. Its lockfile records TypeScript 7.0.2 (Apache-2.0), `@types/node` 24.19.2 (MIT), and development-only transitive packages; `node_modules` is excluded from the npm tarball. The inspected tarball contains the compiled CLI and ORQIVRA-owned schemas, profiles, contracts, skills, adapters, README, and project license. No third-party code or skill text was copied into those assets. External GitHub Actions used by CI remain referenced at their upstream repositories and are not redistributed.

These findings describe the inspected package manifests, tarballs, and resolved dependency metadata for this build. Python dependency ranges may resolve to different versions later; review the exact distributions and their notices when producing another release. This inventory does not make a broader license compatibility determination.
