# aos-orchestrator
> Revisit: when orchestrator profile configuration or authentication changes. · Last touched: 2026-07-31.

Purpose: queue triage, cross-lane coordination, review, escalation judgment, and Operating Hermes coordination.

Current guard: configured as `openai-codex/gpt-5.5`; live per-invocation
`hermes -p aos-orchestrator` proof passed on 2026-07-31. The sticky/default
profile is never changed.

Escalation note: use the default Operating Hermes route for unclear ownership, cross-lane conflicts, or high-risk operator decisions.
