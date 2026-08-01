# aos-delivery
> Revisit: when delivery profile configuration or authentication changes. · Last touched: 2026-07-31.

Purpose: client workflow maps, SOPs, implementation plans, QA, and acceptance criteria.

Current guard: configured and selected per invocation as
`openai-codex/gpt-5.5`. Identity/model/tool prompt loading passes offline;
live inference is blocked by HTTP 401 from stale profile-scoped credentials.
Fail visibly; never fall back to `default` or change auth inside queue routing.

Escalation note: escalate ambiguous client scope, client-facing deliverables, and acceptance-risk decisions to Operating Hermes.
