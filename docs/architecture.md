# Architecture and Shared Contracts

## Product boundary

ORQIVRA is a local session framework for provider-independent engineering work. It supplies orchestration, architecture, verification, and recovery capabilities. The public CLI is implemented independently in Python and TypeScript. Python requires 3.11 or newer; the npm edition requires Node.js 24 or newer. Neither implementation invokes the other runtime. ORQIVRA does not schedule work beyond the current session.

The Codex, Claude Code, and Gemini CLI editions share capability sources, schemas, profiles, fixtures, and CLI behavior. A validated adapter describes client discovery, invocation, permissions, and native skill paths. A model profile is configuration, not an agent or skill. Project guidance cannot grant tools or override a client's permission system.

## Implementations and assets

The Python implementation is in `src/orqivra/`; the TypeScript implementation is in `node/src/`. Shared schemas live in `schemas/`, capability contracts in `core/contracts/`, canonical skills in `skills/`, profiles in `profiles/`, client adapters in `editions/`, and parity fixtures in `tests/parity/`. The npm build and Python installer render runtime assets from those sources. The implementations keep language-specific filesystem and state code separate and exchange ordinary JSON files.

The shared JSON contract rejects duplicate keys, fractions, non-finite numbers, integers outside the interoperable safe range `-(2^53 - 1)` through `2^53 - 1`, and strings or object keys containing lone UTF-16 surrogates. Canonical JSON is compact UTF-8 with recursively sorted object keys in Unicode scalar-value order. Arrays retain their order. SHA-256 of those bytes is written as lowercase hexadecimal.

Hypothesis duplicate detection uses ASCII edge trimming, Unicode NFC normalization, locale-independent lowercase, and collapsing runs of ASCII whitespace to one space. This is a shared comparison rule, not a claim of full Unicode case folding.

## Data ownership and snapshots

A state records its plan hash, input snapshot, state version, append-only events, dependencies, attempts, evidence, and statuses. Writers use an exclusive sibling lock, check the state version and file identity, and atomically replace the state file. Python and Node share the lock and state formats.

Evidence binds an observed command result and artifact hashes to a node snapshot. The node snapshot includes its definition, dependency definitions, plan header, and relevant input hashes. Acceptance and reporting recheck current inputs and active artifacts. Reports separate stale active evidence from superseded history. Hashes identify bytes; they do not establish semantic correctness.

Recovery preserves attempt counters across sessions. It marks affected descendants obsolete and reopens only work that depends on changed inputs, definitions, or artifacts. An interrupted attempt requires diagnosis before a new attempt.

## DAG rules

Nodes declare inputs, dependencies, ownership scopes, risk, acceptance criteria, and verification. Dependencies must exist and be acyclic. READY nodes have accepted dependencies and are emitted in lexical ID order. Independent nodes cannot have overlapping file scopes. A trailing `/**` means a directory subtree; other glob expressions are not supported.

Each node allows five attempts. Starting an attempt increments the counter before work begins. A correction uses a distinct testable hypothesis. Resume and model changes do not reset counters.

## Filesystem and installation boundary

Project roots are inspected at their original path before canonical resolution, even when a workflow has no inputs or artifacts. Input and artifact access stays within an explicit root and rejects symlinks and Windows junctions. Existing directories and special files are not regular file inputs. Recovery may omit a genuinely missing input.

Installation requires an explicit target and defaults to dry-run. The ORQIVRA manifest records owned relative paths and SHA-256 values. Install refuses unowned collisions or modified owned files; uninstall removes only unchanged manifest-owned files. Immediate checks before replacement and removal reduce race windows but do not make path operations race-proof against a concurrent filesystem writer.

## Node schema validation

The canonical files use JSON Schema vocabulary. Python validates with Draft 2020-12 support. The Node CLI enforces its documented supported keyword subset and rejects unsupported keywords; that subset is not full Draft 2020-12 validation. See [CLI contract](cli-contract.md) for the exact set.

## Capability contracts

- **Orchestrate:** choose solo, delegate, audit, or full based on actual runtime capacity, explicit authorization, task independence, and ownership. Keep one coordinator for integration and state.
- **Architecture:** define boundaries, inputs, outputs, and invariants before implementation.
- **Verify:** check behavior and artifacts against acceptance criteria. Separate executed checks, self-verification, and independent review.
- **Recover:** inspect the current snapshot, preserve counters, and reopen only affected work.

## Resource reporting

ORQIVRA does not infer provider token usage, billing, quota, or duration from file sizes. The profile and usage schemas can record metrics only when a provider or client reports them. Unavailable values remain unavailable; word counts are not token measurements.

## MIP adapter boundary

The generic project format has no MIP-only fields. The optional Python adapter is a library helper that can record external validation obligations. It is not invoked automatically by the generic CLI, and the Node CLI has no matching MIP helper. A mock does not satisfy an external obligation.
