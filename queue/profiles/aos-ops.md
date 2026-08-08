# aos-ops
> Revisit: when operations profile configuration or authentication changes. · Last touched: 2026-08-01.

Purpose: queue hygiene, startup checks, internal planning, blocker summaries, and operating reviews.

Current guard: configured and selected per invocation as
`openai-codex/gpt-5.5`. Live dashboard consultation passed on 2026-08-01 with
`aos-ops` reported as the actual profile and no fallback. Fail visibly on
future auth errors; never fall back to `default` or change auth in routing.

Escalation note: use deterministic/local handling first; escalate only when judgment or cross-lane coordination is required.
