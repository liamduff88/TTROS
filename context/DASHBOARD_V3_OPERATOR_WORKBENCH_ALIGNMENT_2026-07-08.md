
## WP2 / Phase A0 — Headless Hermes proof

Status: WORKING

Operator verification:
- PowerShell → AgenticOSClean live runtime confirmed.
- DISTRO=AgenticOSClean.
- Hermes executable: /home/liam/.local/bin/hermes.
- Hermes version: v0.18.0.
- Hermes profile log path writable in real shell: yes.
- Dashboard endpoint POST /api/hermes/message returned ALIVE.
- Token totals were available from the endpoint.

A0 endpoint result:
- success: true
- reply: ALIVE
- total_tokens: 13611
- model: gpt-5.5
- provider: openai-codex

Note: Codex sandbox could not complete the ALIVE proof because it could not write to /home/liam/.hermes/profiles/aos-orchestrator/logs/agent.log. The live operator shell proved this was a sandbox limitation, not a live-runtime failure.
