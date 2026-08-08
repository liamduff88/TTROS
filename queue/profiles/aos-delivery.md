# aos-delivery
> Revisit: when delivery profile configuration or authentication changes. · Last touched: 2026-08-01.

Purpose: client workflow maps, SOPs, implementation plans, QA, and acceptance criteria.

Current guard: configured and selected per invocation as
`openai-codex/gpt-5.5`. Live dashboard consultation passed on 2026-08-01 with
`aos-delivery` reported as the actual profile and no fallback. Fail visibly on
future auth errors; never fall back to `default` or change auth in routing.

Escalation note: escalate ambiguous client scope, client-facing deliverables, and acceptance-risk decisions to Operating Hermes.
