# Agentic OS Hermes Profiles

Agentic OS uses one Operating Hermes runtime. Revenue, marketing, delivery, operations, and orchestrator roles are Hermes profiles plus queue routing metadata, not separate Hermes installations.

The five `aos-*` profiles were created manually:

- `aos-orchestrator`
- `aos-revenue`
- `aos-marketing`
- `aos-delivery`
- `aos-ops`

As of the July 6, 2026 Prompt B profile pass, `hermes profile list` shows the Model column as `—` for each `aos-*` profile. The queue router must therefore request these profiles only as metadata and fall back to the default Operating Hermes route until a profile has a configured model and a supported native invocation path.

Do not run `hermes profile use` for queue routing. Do not mutate Hermes profile config from this repo. Model and toolset policy should live in Hermes once configured; this repo keeps only the thin lane map and guardrails in `queue/lane_profiles.json`.
