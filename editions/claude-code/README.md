# Claude Code edition

This edition is distribution-ready at `.claude/skills/<skill-name>/SKILL.md`. Install its four skill directories under the project `.claude/skills/` directory or into a supported personal skills location. With ORQIVRA, pass the exact target to `orqivra install --edition claude-code --target PATH`; review the dry-run and pass `--apply` to write. In an interactive session, inspect available skills with `/skills` and invoke a skill as `/orqivra-orchestrate`, `/orqivra-architecture`, `/orqivra-verify`, or `/orqivra-recover`. Workspace trust and configured settings can affect whether project skills load.

The Claude model profile deliberately contains unresolved user-supplied values and cannot be activated until they are completed. The profile does not change the active Claude Code model. Permission prompts and configured tool rules remain authoritative.

Official client guidance: [Claude Code skills](https://code.claude.com/docs/en/skills).
