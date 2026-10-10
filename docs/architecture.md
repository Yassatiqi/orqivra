# Architecture and Shared Contracts

## Product boundary

ORQIVRA is a local session framework for provider-independent engineering work. It supplies four composable capabilities: orchestration, architecture, verification, and recovery. A deterministic Python CLI tracks a user-authored task DAG, evidence, attempts, and state. It does not schedule autonomous work beyond the current session.

The three editions share these contracts but adapt their triggers, discovery paths, invocation syntax, and available client controls. A model profile is configuration, not an agent or skill. Project policy describes intended constraints; a client's permission system remains authoritative.

## Data ownership and snapshot identity

The DAG JSON is the immutable plan input for one state initialization. The state JSON records its normalized plan hash, a snapshot hash over that plan and project-root-relative input hashes, an integer state version, append-only events, dependencies, attempts, evidence, and node statuses. Each writer obtains an exclusive sibling lock, checks the state version and file identity, writes a temporary file in the same directory, flushes it, and atomically replaces the state file. A concurrent writer receives a conflict and must reload; it must not overwrite.

Evidence binds an observed command result and artifacts to a node snapshot. The node snapshot includes the plan header, that node's definition, its dependency definitions, and input hashes used by the node and its dependencies. This lets an unchanged independent branch retain current evidence when a different branch's input changes. Evidence records are append-ordered; the latest record is active for acceptance, while older records remain historical. Reports identify stale active evidence separately from superseded stale history. Acceptance and read-only reporting recheck actual input and active artifact hashes, so stale files cannot certify a node before an explicit evidence check. File hashes prove artifact identity only. They do not prove semantic correctness. A changed input marks affected nodes and accepted descendants obsolete and invalidates their active evidence before resume.

## DAG rules

Nodes have `id`, `objective`, `inputs`, `dependencies`, `role`, `profile`, `file_scope`, `risk`, `acceptance_criteria`, `verification`, `status`, `attempts`, `evidence`, and `blocking_reason`. Required dependency IDs must exist. Cycles are errors. A READY node has all dependencies accepted and is emitted in lexical ID order. A deferred obligation is never treated as a satisfied dependency for final certification.

File scopes are project-relative paths, with optional `/**` only to denote a complete directory subtree. Reject absolute paths, parent traversal, symlinks, duplicate scopes, and ancestor/descendant overlaps across simultaneously runnable nodes. These simple rules make ownership conflicts deterministic without pretending to resolve arbitrary glob expressions.

Allowed transitions are:

| From | To |
|---|---|
| planned | ready, blocked, obsolete |
| ready | running, blocked, obsolete |
| running | verifying, fix_required, blocked, obsolete |
| verifying | accepted, fix_required, blocked, obsolete |
| fix_required | ready, blocked, obsolete |
| blocked | ready, obsolete |
| accepted | obsolete |
| obsolete | ready (resume only) |

`ready` requires all dependencies accepted. `accepted` requires a successful verification result and current evidence for the active snapshot. A changed input, artifact, or explicit transition to `obsolete` marks the affected subtree obsolete and queues it for recovery. `resume` recalculates the snapshot and rechecks dependencies before reopening obsolete work. If an affected node has an interrupted attempt, it returns as `fix_required` and must be diagnosed before another attempt begins. Each node allows five attempts, including the initial attempt. An attempt begins with a specific hypothesis and its count is never reset on resume or profile changes. A sixth attempt is rejected. If a session resumes while a node has an unfinished attempt, the attempt is marked `interrupted`, moved to `fix_required`, and must be diagnosed before another attempt begins.

## Capability contracts

- **Orchestrate:** distinguish solo, delegate, audit, and full; decide route, implementer, and concurrency width separately; integrate and maintain state. Simple edits with no dependency or coordination need remain solo.
- **Architecture:** define module boundaries, inputs, outputs, invariants, and only material decisions. Load targeted references instead of all documentation.
- **Verify:** validate public behavior and artifacts against independent expectations. Label static checks, executed checks, self-verification, and independent review accurately.
- **Recover:** inspect the current snapshot, retain counters, and resume only affected nodes. Every retry requires a new hypothesis; stop for missing authorization, unavailable dependencies, or exhausted attempts.

## Security and installation boundary

Never execute commands supplied by a DAG, profile, skill, or evidence record. The CLI stores command text as evidence only. Normalize paths under explicit roots, reject traversal and unsafe symlinks, and use an ORQIVRA-owned manifest to identify installed files. Install is dry-run by default, repeatable, and refuses a collision or modified destination. Uninstall removes only manifest-owned files whose hashes still match. Native clients enforce actual permissions; Markdown instructions cannot grant them.

## MIP adapter boundary

The generic project format contains no MIP-only fields or rules. The optional MIP adapter may record external validation obligations as `DEFERRED_EXTERNAL` during component development. It may resolve them only during the final validation sprint when the named external application or infrastructure was actually exercised. A mock does not satisfy an external obligation.
