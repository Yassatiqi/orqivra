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

For the v0.3.0 candidate, static format checks, model catalog review, and asset rendering remain separate from client execution. Codex, Claude Code, and Gemini CLI activation are `NOT_RUN` until actual discovery and activation sessions are recorded. Approved profile values do not establish availability or switch a client's active model. The Gemini `auto` route leaves model choice to the client; `gemini-3.1-pro-preview` requires eligible-account access, and Gemini CLI may route or fall back natively. Claude Code may also use its own fallback for certain flagged requests. These behaviors are client-owned and cannot be disabled by ORQIVRA's `fallback.policy: none`.

The latest main CI run, [Actions run 38479211635](https://github.com/Yassatiqi/orqivra/actions/runs/38479211635), completed successfully across all 10 jobs for commit `fd64f52b1baa3cbe23f87291748086d2747690f3`. This includes the Python 3.11 Windows regression suite and its required junction qualification step. It records CI for that commit; it does not qualify client activation. The v0.2.0 Actions status was `NOT_OBSERVED` and does not qualify this candidate. Registry ownership, publisher access, and the repository's private vulnerability-reporting setting remain unresolved until verified.
