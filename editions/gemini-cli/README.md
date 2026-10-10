# Gemini CLI edition

This edition is distribution-ready at `.gemini/skills/<skill-name>/SKILL.md`. Install its four skill directories under a trusted workspace `.gemini/skills/` directory or into a supported user skills location. With ORQIVRA, pass the exact target to `orqivra install --edition gemini-cli --target PATH`; review the dry-run and pass `--apply` to write. Inspect discovery with `/skills list` and refresh with `/skills reload`. Ask for a capability by name or describe a matching task; Gemini CLI activates the skill and requests activation consent.

The Gemini model profile deliberately contains unresolved user-supplied values and cannot be activated until they are completed. It specifies no reasoning-effort equivalent and does not change the active Gemini CLI model. Workspace trust, activation consent, policy, and tool confirmations determine access.

Official client guidance: [Gemini CLI skills](https://geminicli.com/docs/cli/tutorials/skills-getting-started/), [Managing Agent Skills](https://geminicli.com/docs/cli/using-agent-skills/).
