# Codex edition

The directory `.agents/skills/` mirrors the Codex repository-skill discovery layout. Copy the four skill directories into an explicit Codex repository target under `.agents/skills/`, or use `orqivra install --edition codex --target PATH` with that exact target. Install defaults to dry-run; use `--apply` only after reviewing the planned file changes. The install tool must preserve its owned manifest and refuse a modified collision. List skills with `/skills`; invoke one explicitly with its `$orqivra-*` name. This package does not include `agents/openai.yaml`.

The `profiles/codex.json` file provides the Astra Advisor role configuration with requested model IDs and effort values. It remains non-activatable until each value is verified in the target runtime. A profile is not a model switch or a runtime compatibility claim. Codex sandbox and approval controls determine actual actions.

Official client guidance: [Codex skills](https://developers.openai.com/codex/skills).
