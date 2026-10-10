# Resource Usage

The CLI reports local state and recorded evidence. It does not inspect account-wide token usage, model billing, or provider quotas. No token, currency, cost, or time metrics are inferred from file sizes.

The profile and usage schemas allow metrics only when a provider or client reports them. When unavailable, record `source: unavailable` and null token counts. The current release has no observed account usage metrics. Skill bodies target 500–900 words and shared references are loaded only when relevant; these word counts are not token measurements.
