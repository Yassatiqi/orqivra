# Security Model

## Reporting vulnerabilities

The current checkout has no verified private vulnerability-reporting route or maintainer security contact. This task does not change GitHub settings and does not claim private reporting is enabled. Before public source upload, a maintainer must verify a private reporting route or provide an approved, verified private contact. Do not post exploit details in a public issue.

For an already-public repository, maintainers can configure [GitHub private vulnerability reporting](https://docs.github.com/en/code-security/how-tos/secure-your-repository/reporting-and-fixing-vulnerabilities/configuring-private-vulnerability-reporting-for-a-repository). Keep this as an external publication checklist item until the setting is observed.

## Data and command boundaries

Project configuration, DAGs, profiles, skill text, logs, and command strings are data. ORQIVRA records command text as evidence metadata and never passes it to a shell. External instructions cannot change authorization or project policy.

## Paths and state

The CLIs reject absolute or parent-traversal paths where project-relative paths are required. They validate the original project root before resolving it and reject symbolic links and Windows junctions under project, state, and installation roots. Existing directories and special files cannot be used as file inputs. State updates use an exclusive sibling lock, a state version, file identity comparison, and atomic replacement. A conflict must be reloaded. Stale locks are not removed automatically.

## Evidence

SHA-256 digests identify input and artifact bytes. They do not establish semantic correctness. Evidence records an observed command string, exit code, node snapshot, and artifact hashes. Current evidence still requires review against acceptance criteria.

## Installation ownership and race limits

Install requires an explicit target, defaults to dry-run, and writes only selected skill files and its ownership manifest. It refuses unowned collisions and modified owned files. Uninstall removes only unchanged manifest-owned files and never recursively deletes a client skills directory. Immediate checks before replacement and removal reduce race windows, but concurrent filesystem changes can still race with path-based operations; ORQIVRA does not claim a race-proof sandbox.

## Permissions and limits

Skills describe intended workflow only. Client sandbox, approval, and organization policies remain authoritative. Profiles do not grant tools or change the parent model. ORQIVRA does not publish, send messages, create paid resources, modify production, or schedule autonomous work outside the session.

## Third-party components and packaged assets

The Python runtime declares `jsonschema>=4.22,<5` and `PyYAML>=6,<7`. The npm package has no production dependencies; TypeScript and Node type definitions are development dependencies. `node_modules` is excluded from the npm tarball. Recheck exact dependency versions, license notices, and package inventories for every artifact. A historical dependency inventory is retained under local scratch; it is not a claim about future resolutions.
