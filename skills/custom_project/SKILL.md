---
name: custom_project
description: Delivery playbook for Custom Workflow Agent / AI Employees / larger scoped work — the generic §6.2 skeleton plus a mandatory SCOPE-LOCK stage. v0 (pre-seeded — hardened by first 3 client uses).
when-to-use: A signed custom engagement exists that doesn't map to the four standard builds. Owner: aos-delivery. Trust: v0.
---
# /custom-project
> Revisit: every real use (v0 — first 3 uses ARE the hardening). · Last touched: 2026-07-07
> v0 use log: (none yet — record date + client per use; 3 uses remove the v0 marker)

## Purpose
Deliver custom scoped work with the same discipline as the standard playbooks. The extra risk in custom work is scope drift — this skill exists to kill it early.

## Inputs
- Client entity page + signed scope. Refuse to start without both (Stage 0 rule).
- Client-isolation folder confirmed to exist.

## Stages
0. **INTAKE** — read entity page + signed scope; confirm isolation folder.
0.5 **SCOPE-LOCK (mandatory, custom-only)** — written scope, explicit exclusions, and acceptance criteria approved by Liam before Stage 1. Ambiguous scope = stop and ask (always.md #10).
1. **MAP** — current-state workflow map, one page, client-approved.
2. **DESIGN** — target workflow: handoffs, rules, tools; every human-approval gate explicitly marked. Client sign-off.
3. **BUILD** — implementation steps (may launch Claude Code/Codex). All connector actions read/draft-only unless the item carries approved_external_action.
4. **TEST** — acceptance tests against the Stage 2 design; evidence recorded (screenshots/logs/paths). No "trust me" passes.
5. **HANDOFF** — client docs: what it does, what it never does without approval, how to pause it, who to call.
6. **CLOSE** — update client entity page · receipt with full token block · access closeout checklist (aos-ops reviews).

## Never
- Start without SCOPE-LOCK sign-off.
- Interpret ambiguous scope in the client's or TTR's favour — ask.
- Blend client data across isolation folders.
- Any external side effect without the approved flag.

## Done when
All stages complete, acceptance evidence on file, client entity page updated, receipt with token block written, v0 use log stamped.
