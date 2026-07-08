---
name: build_voice_agent
description: "v0 (pre-seeded — hardened by first 3 client uses). Deliver Voice Agent Setup (from CA$1,000 + platform/usage) — missed-call, voicemail, after-hours capture."
when-to-use: A Voice Agent Setup is signed and scoped. Owner: aos-delivery. Trust: v0 pre-seeded.
---
# /build-voice-agent — v0 (pre-seeded — hardened by first 3 client uses)
> Revisit: after each of the first 3 client uses; demotion candidate if unused 90 days. · Last touched: 2026-07-07

## Purpose
Standard delivery playbook for inbound voice: missed-call / voicemail / after-hours capture, call summaries, and booking handoff.

## Playbook (common skeleton, Blueprint V2 §6.2)
- **Stage 0 INTAKE** — client entity page + signed scope; client-isolation folder confirmed. Also capture: phone platform, call volume, hours, booking system, and platform/usage cost expectations (priced separately from the build).
- **Stage 1 MAP** — current call flow: business hours vs after-hours, missed-call rate, voicemail handling, who calls back and when, where bookings land. One-page map, client-approved.
- **Stage 2 DESIGN** — target flow: what the agent answers, captures, summarizes, and hands off to booking; escalation to a human; **an explicit list of what the agent may never say or promise** (pricing, guarantees, regulated claims per client industry). Every approval gate marked. Client sign-off.
- **Stage 3 BUILD** — platform config, greeting/scripts, capture fields, summary delivery, booking handoff. Read/draft-only connector posture unless approved_external_action.
- **Stage 4 TEST** — scripted test calls: missed call, voicemail, after-hours, booking request, and at least one attempt to elicit a forbidden promise. Evidence recorded per call.
- **Stage 5 HANDOFF** — client docs incl. the never-say list, pause procedure, usage-cost expectations, who to call.
- **Stage 6 CLOSE** — entity page · receipt with token breakdown · access closeout (aos-ops reviews).

## Never
- Deploy without the client-approved never-say/never-promise list.
- Let the agent quote prices, guarantees, or regulated claims not in the approved script.
- Skip scripted test calls or their recorded evidence.
- Hide platform/usage costs from the handoff doc.

## Done when
All stages complete; scripted test calls passed including the forbidden-promise probe; handoff doc with never-say list delivered; closeout passed; receipt written. v0 tracking in queue/skill_trust.jsonl.
