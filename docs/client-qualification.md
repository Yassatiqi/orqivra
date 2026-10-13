# Client Qualification

Static adapter validation, generated files, client discovery, skill activation, model routing, and permission behavior are separate results. A package build or an installed skill file does not prove that a client activated the skill.

## Safe procedure

1. Record the client name, client version, operating system, ORQIVRA package version, and package SHA-256.
2. Use a disposable project and an explicit repository skill target. Record the exact target and the installed manifest.
3. Verify the selected files with `orqivra verify-install --target PATH`.
4. Use the client's documented discovery command or UI and record the exact discovered skill names.
5. Exercise a positive trigger, a simple task that should remain solo, and recovery after a failed or interrupted attempt. Record observed activation separately from model-profile selection.
6. Observe permissions and tool access without changing global settings or bypassing consent. Stop if the client requests an unavailable account, permission, or tool.
7. Record the exact commands, outputs, limitations, and artifact hashes under local ignored `scratch/`.

Do not use production data or install into a user-wide skills directory for qualification. Do not enter credentials into evidence files.

## Current status

For this release, static format checks and asset rendering are recorded separately from actual client activation. Codex, Claude Code, and Gemini CLI remain `NOT_RUN` until a real discovery and activation session is recorded. Local availability of a client executable is not activation evidence. The GitHub Actions result is `NOT_OBSERVED`: the source push succeeded, but the available GitHub interfaces did not expose a run status. A configured or queued workflow is not a pass.
