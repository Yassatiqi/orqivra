# Client Compatibility and Research Notes

Retrieved 2026-10-10. These findings describe documented formats, not runtime qualification of ORQIVRA.

| Source | Verified capability | Limitation for this release |
|---|---|---|
| [Codex skill authoring](https://learn.chatgpt.com/docs/build-skills) | Skills use `SKILL.md` with `name` and `description`, optional references/scripts, progressive disclosure, explicit or description-based activation, and `.agents/skills` repository discovery. | The local Codex command is present, but this session did not invoke a built edition through Codex skill discovery. App and CLI behavior may vary by release. |
| [Codex subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents) | Current Codex supports parallel subagents; custom agents may configure model, reasoning, and sandbox controls. | Local model routing and exact runtime exposure were not inspected. This documents authoring possibilities only. |
| [Codex AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md) | Project instructions layer from the repository root and can use nested overrides. | ORQIVRA does not write global guidance during installation. |
| [Claude Code skills](https://code.claude.com/docs/en/skills) | Project skills live under `.claude/skills/<skill>/SKILL.md`; descriptions activate skills, and explicit slash invocation is supported. | `claude` is unavailable in this environment; runtime behavior and permissions are NOT_RUN. |
| [Gemini CLI skills](https://geminicli.com/docs/cli/skills/) | Workspace skills use `.gemini/skills/` or the `.agents/skills/` alias, support progressive disclosure, and can be listed or installed with CLI commands. | `gemini` is unavailable in this environment; runtime behavior and permissions are NOT_RUN. |
| [Agent Skills specification](https://agentskills.io/specification) | Shared metadata includes required `name` and `description`; names, descriptions, optional fields, scripts, and references have documented constraints. | Optional fields and tool permissions vary by host. Edition metadata is restricted to documented client support. |

Codex uses `.agents/skills/` repository discovery. Claude Code uses its own `.claude/skills/` path. Gemini supports `.agents/skills/` as an alias and `.gemini/skills/` as a native path. ORQIVRA therefore provides separate target paths while keeping the shared skill content aligned. Runtime qualification is reported separately from static format validation.

## Inspiration references

- [sol-advisor](https://github.com/DannyMac180/sol-advisor): selective route choice, parent accountability, and fresh review as design ideas. No source text or code is copied.
- [mattpocock/skills](https://github.com/mattpocock/skills): focused composable skills, functional slices, targeted context, shared vocabulary, public-interface checks, and careful distribution as design ideas. No source text or code is copied.
