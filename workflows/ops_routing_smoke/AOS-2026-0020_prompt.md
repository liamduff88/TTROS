Operations routing smoke for AOS-2026-0020.

Task:
Create a compact local-only verification note proving the Agentic OS explicit Hermes lane routing path can run an Operations queue item.

Scope:
- Local files only.
- Do not call connectors.
- Do not touch Telegram.
- Do not touch North Shore.
- Do not use external systems.

Required route:
- lane: operations
- profile_requested: aos-ops
- provider_requested: <EXACT_PROVIDER>
- model_requested: gpt-5.5

Return a brief PASS/NEEDS ATTENTION note and token usage if available.
