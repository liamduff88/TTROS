## WP2 / Phase A0 — Headless Hermes proof

Status: WORKING

Operator verification:

* PowerShell → AgenticOSClean live runtime confirmed.
* DISTRO=AgenticOSClean.
* Hermes executable: /home/liam/.local/bin/hermes.
* Hermes version: v0.18.0.
* Hermes profile log path writable in real shell: yes.
* Dashboard endpoint POST /api/hermes/message returned ALIVE.
* Token totals were available from the endpoint.

A0 endpoint result:

* success: true
* reply: ALIVE
* total\_tokens: 13611
* model: gpt-5.5
* provider: openai-codex

Note: Codex sandbox could not complete the ALIVE proof because it could not write to /home/liam/.hermes/profiles/aos-orchestrator/logs/agent.log. The live operator shell proved this was a sandbox limitation, not a live-runtime failure.



\## Update 2026-07-09 — WP4 Phase A audit



WP4 Phase A audit completed in fresh Codex session.



Result:

\- AUDIT CLEAN



Phase A operator click-path was already verified.

Token ledger exact-only fallback issue was fixed before this audit:

\- exact token parsing preserved

\- invented fallback removed

\- unavailable fallback active

\- no-agent-invocation state preserved

\- no NaN/fake token display

\- no forbidden paths touched



Status:

\- WP4 clean.

\- Ready for WP5 pre-flight after repo is clean/pushed and notification allowlist is filled.

