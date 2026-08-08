# Agentic OS Hermes Profiles
> Revisit: when profile configuration, authentication, or queue routing changes. · Last touched: 2026-08-01.

Agentic OS uses one Operating Hermes runtime. Revenue, marketing, delivery, operations, and orchestrator roles are Hermes profiles plus queue routing metadata, not separate Hermes installations.

The five `aos-*` profiles were created manually:

- `aos-orchestrator`
- `aos-revenue`
- `aos-marketing`
- `aos-delivery`
- `aos-ops`

All five `aos-*` profiles now have a configured `openai-codex/gpt-5.5`
model. `tools/aos-hermes-coordinator.sh --profile <name>` and the dashboard
queue runner bind the routed profile with Hermes' native `-p` selector for
that invocation only.

All five `aos-*` profiles passed live, per-invocation dashboard consultations
on 2026-08-01 with their requested profile reported as the actual profile and
no fallback. Credential/auth files remained protected and were not changed.

Do not run `hermes profile use` for queue routing. Never mutate the Hermes
global/default profile. Model and toolset policy lives in each named Hermes
profile; this repo keeps only the thin lane map, validated launcher, and
guardrails. Never silently substitute `default` after a named-profile failure.
