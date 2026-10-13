# Maintaining ORQIVRA

This guide describes where shared behavior lives, how to evolve it, and what local and external evidence is needed before release. Keep authored project content in English and preserve the MIT license and its references in `LICENSE`, package metadata, and generated distributions.

## Canonical sources and runtime boundaries

- `docs/cli-contract.md` and `schemas/` define the public commands, data formats, and validation interfaces. Update them alongside any change to public behavior.
- `core/contracts/` defines shared capability requirements. `skills/` contains the canonical skill bodies; `defaults/` holds the default project configuration; `models/catalog.json` records dated model documentation and qualification; `profiles/` holds approved role and edition mappings; `editions/` contains client-specific adapters.
- `src/orqivra/` and `node/src/` are separate implementations. The Python CLI supports Python 3.11 or newer and declares `jsonschema` and `PyYAML` dependencies. The npm CLI supports Node.js 24 or newer, has no production dependencies, and uses TypeScript and Node type definitions only for development/build work. Neither CLI invokes or requires the other runtime.
- `tests/parity/` contains shared fixtures and cross-runtime checks. Runtime-specific tests live with their respective implementations.

Keep shared contracts provider-neutral. Put client discovery and skill-path details in edition adapters, and model identifiers in edition profiles. Python validates schemas with Draft 2020-12 support; Node implements only the documented keyword subset in the CLI contract and rejects unsupported keywords. Preserve this boundary or update the public documentation and both implementations together.

## Generated assets and skills

Edit canonical inputs, then use the supported generators. The CLI command `orqivra build --edition codex|claude-code|gemini-cli|all --output DIR` renders a selected client bundle from shared skills, adapters, profiles, schemas, defaults, and model catalog. `orqivra install` renders skills to an explicit target; its default is a dry run, and writes/removals are limited to files recorded by its ORQIVRA manifest. Review the dry-run paths before applying an install.

The npm package build runs from `node/` with `npm ci` and `npm run build`. It compiles `node/src/` and generates assets from canonical repository sources into `node/dist/`. The Node build output is ignored and required when packaging the npm tarball. Python distributions include the canonical schemas, skills, profiles, adapters, and contracts through `pyproject.toml`.

Do not hand-maintain generated client skill trees or copy canonical shared skill bodies into edition directories. The `docs/online-llm-context.md` portable method export is generated from the marked section in `skills/orqivra-orchestrate/SKILL.md`; run `node tools/generate-online-context.mjs` after editing that section, then use `node tools/generate-online-context.mjs --check` and `python -m unittest tests.test_online_context -v` to check consistency. To add a skill, add its canonical source under `skills/`, update shared contracts or schemas only when the interface requires it, and extend render/validation and test expectations. To add a client edition, add its adapter/profile and rendering support in both implementations, preserve the common skill body, then cover the native layout and behavior in tests. Validate real client discovery and activation separately; generated files alone do not qualify a client.

Keep build output, package artifacts, local plans and state, qualification output, reports, and preserved session history under ignored `scratch/` where practical. Do not commit `scratch/`, credentials, `.env` files, virtual environments, caches, `node_modules/`, generated `node/dist/`, package archives, or generated client skill copies. Check `.gitignore` before creating local output.

## Evolving commands, schemas, and adapters

For a public command or data-format change, update `docs/cli-contract.md`, the relevant schemas, defaults/catalog/profile data as applicable, Python and Node behavior, their help or diagnostics, examples, and affected tests. Keep public names, inputs, outputs, error behavior, and exit codes aligned. For schema changes, account for the Node-supported keyword subset as well as Python's validator; do not silently rely on keywords Node does not implement. Configuration changes must preserve absent-discovered versus explicitly missing file behavior, and must reject reasoning that would silently carry over incompatibly after a model change.

Update shared parity fixtures and `tests/parity/` checks for behavior both runtimes must share, and add implementation-specific tests where behavior differs intentionally. Run the required Python suite and help command, npm suite, and shared parity/interoperability checks affected by a behavior change. Report skipped, unavailable, and not-run checks with their actual status.

Optional adapters must remain outside the generic contract unless shared behavior explicitly changes. The generic adapter has no MIP-only policy. MIP is a Python-only library helper that records external validation obligations; it is not invoked by the generic CLI and has no Node counterpart. Test optional adapter behavior in its implementation-specific tests, and keep obligations unresolved until the external system has actually been observed. A mock does not satisfy an external obligation.

## Local release and external gates

Use the procedure in [the release checklist](docs/releasing.md). At minimum, run `python -m unittest discover -s tests -v`, `python -m orqivra.cli --help`, and `npm.cmd test --prefix node` on the declared runtimes. Run shared parity and affected cross-runtime interoperability checks after behavior changes. Build the Python wheel/source distribution with Python and the npm tarball with Node/npm independently. Inspect package inventories and hashes, then install and exercise each local artifact outside the checkout with the other runtime unavailable. Keep generated packages and inventories in `scratch/`.

Local checks do not establish Python 3.11 compatibility unless exercised on Python 3.11, client activation, a GitHub Actions result, registry package-name ownership, publisher access, or external service validation. Qualify each client by observed discovery and activation; observe an actual Actions run; verify registry and account eligibility; and verify the public repository's private vulnerability-reporting route or an approved verified private contact before asserting one exists. Keep these external gates unresolved until observed. Publication requires a separate explicit authorization; local preparation does not publish packages or modify production or repository settings.

## References

See [architecture](docs/architecture.md) for boundaries, [compatibility](docs/compatibility.md) for declared support and observed qualification, [installation](docs/installation.md) for asset and artifact workflows, and [releasing](docs/releasing.md) for the current release gates. ORQIVRA is MIT-licensed; retain the existing license and do not add third-party material without reviewing its license.
