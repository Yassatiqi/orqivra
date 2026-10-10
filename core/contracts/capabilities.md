# Capability Acceptance Contracts

These contracts apply to all editions. Client-specific invocation and permission behavior is documented in each edition.

## `orqivra-orchestrate`

Trigger when work has dependent tasks, parallelizable scopes, a need for review, significant uncertainty, or recovery state to manage. Choose `solo`, `delegate`, `audit`, or `full` based on risk and coordination need. Make separate decisions for route, implementer, and concurrency width. Do not force delegation for a simple local edit. Keep one coordinator for shared state, integrate all work, and stop when a blocker or attempt limit is reached.

## `orqivra-architecture`

Trigger before consequential multi-file work, interface changes, cross-edition behavior, or material ambiguity. Define inputs, outputs, ownership, and invariants before implementation. Resolve routine choices with judgment. Record an ADR only when later maintainers need the reasoning. Load only references needed for the current decision.

## `orqivra-verify`

Trigger before acceptance, release, or a claim that work is complete. Validate the active snapshot, schema, acceptance criteria, and independent public behavior. Distinguish static inspection, executed checks, self-verification, and independent review. Hashes establish identity only. A skipped external check remains `DEFERRED_EXTERNAL` or `NOT_RUN` and blocks certification when required.

## `orqivra-recover`

Trigger after interruption, failed verification, changed input, or a blocked node. Inspect current state and artifacts first. Recalculate stale evidence, invalidate only affected descendants, and resume only nodes whose prerequisites are accepted. Preserve attempt counters. Begin every correction with a new hypothesis. Stop after five attempts for a node, when authorization is missing, or when a required external dependency is unavailable. Never weaken acceptance criteria or create replacement nodes to evade limits.

## Shared execution invariants

- The schema version and input snapshot are explicit.
- Dependencies must exist and the graph must be acyclic.
- Ready nodes are deterministic and have accepted dependencies.
- A node is accepted only after a successful verification result and current evidence.
- State changes are atomic and reject concurrent version conflicts.
- Skills carry the required contracts and local references so use does not require access to the repository root.
- Model profiles resolve logical roles but do not change the parent model.
- Client permission settings override promises in skill text.
