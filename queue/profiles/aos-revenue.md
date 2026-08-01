# aos-revenue
> Revisit: when revenue profile configuration or authentication changes. · Last touched: 2026-07-31.

Purpose: prospect research, outreach drafts, sales prep, and CRM-ready summaries.

Current guard: configured and selected per invocation as
`openai-codex/gpt-5.5`. Identity/model/tool prompt loading passes offline;
live inference is blocked by HTTP 401 from stale profile-scoped credentials.
Fail visibly; never fall back to `default` or change auth inside queue routing.

Escalation note: escalate direct prospect-facing copy, pricing/scope decisions, unsupported claims, or repeated revision to Operating Hermes.
