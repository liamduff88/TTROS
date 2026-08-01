# aos-ops
> Revisit: when operations profile configuration or authentication changes. · Last touched: 2026-07-31.

Purpose: queue hygiene, startup checks, internal planning, blocker summaries, and operating reviews.

Current guard: configured and selected per invocation as
`openai-codex/gpt-5.5`. Identity/model/tool prompt loading passes offline;
live inference is blocked by HTTP 401 from stale profile-scoped credentials.
Fail visibly; never fall back to `default` or change auth inside queue routing.

Escalation note: use deterministic/local handling first; escalate only when judgment or cross-lane coordination is required.
