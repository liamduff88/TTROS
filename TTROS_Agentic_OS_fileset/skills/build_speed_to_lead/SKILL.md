---
name: build_speed_to_lead
description: "v0 (pre-seeded — hardened by first 3 client uses). Deliver the Speed-to-Lead System build (from CA$1,000) — the commercial wedge."
when-to-use: A Speed-to-Lead build is signed and scoped. Owner: aos-delivery. Trust: v0 pre-seeded.
---
# /build-speed-to-lead — v0 (pre-seeded — hardened by first 3 client uses)
> Revisit: after each of the first 3 client uses; demotion candidate if unused 90 days. · Last touched: 2026-07-07

## Purpose
Standard delivery playbook for the front-door offer: capture → route → respond → follow-up on inbound leads, with response-time targets.

## Playbook (common skeleton, Blueprint V2 §6.2)
- **Stage 0 INTAKE** — read client entity page + signed scope; refuse without both; confirm client-isolation folder.
- **Stage 1 MAP** — map every inbound path: website forms, phone/missed calls, DMs, directories, marketplaces, referrals, ad leads. Where each lands today, who responds, how fast, what falls through. Output: one-page map, client-approved.
- **Stage 2 DESIGN** — target workflow: capture → route → respond → follow-up, with explicit response-time targets per path, CRM handoff rules, and every human-approval gate marked. Client sign-off required.
- **Stage 3 BUILD** — implement (may launch Claude Code/Codex for config/scripts; GHL/Zapier/Make/CRM workflows as scoped). All connector actions read/draft-only unless the item carries approved_external_action.
- **Stage 4 TEST** — acceptance: a test lead traverses the full path within the target response time, on every inbound path in scope. Evidence recorded (screenshots/logs/paths) — no "trust me" passes.
- **Stage 5 HANDOFF** — client docs: what it does, what it never does without approval, how to pause it, who to call.
- **Stage 6 CLOSE** — entity page update · receipt with full token breakdown · access closeout checklist (aos-ops reviews).

## Never
- Skip Stage 0 inputs or the Stage 2 client sign-off.
- Auto-send anything to real leads during build/test without the external-action flag.
- Declare done without recorded acceptance evidence per inbound path.
- Leave client credentials/access open after Stage 6.

## Done when
All 7 stages complete with evidence; test lead met response targets on every scoped path; handoff doc delivered; closeout checklist passed; receipt written. v0 marker removal tracked in queue/skill_trust.jsonl after 3 real uses.
