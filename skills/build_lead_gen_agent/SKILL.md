---
name: build_lead_gen_agent
description: "v0 (pre-seeded — hardened by first 3 client uses). Deliver the Lead Generation Agent (scoped after Fit Call) — the V4.1 pipeline productized for a client."
when-to-use: A Lead Gen Agent build is signed after a Fit Call and scoped. Owner: aos-delivery (pipeline logic with aos-revenue). Trust: v0 pre-seeded.
---
# /build-lead-gen-agent — v0 (pre-seeded — hardened by first 3 client uses)
> Revisit: after each of the first 3 client uses; demotion candidate if unused 90 days. · Last touched: 2026-07-07

## Purpose
Productize the internal V4.1 staged pipeline for a client: their ICP calibration, their CASL posture, their CRM handoff. Inherits every V4.1 hard gate.

## Playbook (common skeleton, Blueprint V2 §6.2)
- **Stage 0 INTAKE** — entity page + signed scope; isolation folder; plus: client ICP definition, CASL/consent posture and sender identity, CRM system of record.
- **Stage 1 MAP** — current lead-gen reality: sources, list quality, who researches/qualifies/contacts, where the CRM handoff breaks. One-page map, client-approved.
- **Stage 2 DESIGN** — the client's pipeline mirroring V4.1 stages: calibration → discovery → evidence verify → contact verify → scoring → outreach drafting → QA → report → memory write. Binding QA checklist; forced downgrades on weak evidence; CASL rules encoded; **per-message client approval before any send** marked as a hard gate. Client sign-off.
- **Stage 3 BUILD** — implement stages and CRM handoff; connector actions read/draft-only; the agent never contacts anyone.
- **Stage 4 TEST** — acceptance on a sample run: evidence-verified prospects, scoring matches calibration, drafts pass QA, CRM records land correctly, zero sends occurred. Evidence recorded.
- **Stage 5 HANDOFF** — docs: how to run it, the approval gate, CASL posture, what it never does (no autonomous outreach), pause procedure.
- **Stage 6 CLOSE** — entity page · receipt with token breakdown · access closeout.

## Never
- Send, connect, or message anyone — ever — without per-message client approval; no exception in test.
- Invent prospect facts, urgency, budget, or intent; weak evidence is downgraded, not dressed up.
- Skip the QA checklist or the CASL posture encoding.
- Mutate the client CRM outside the designed, approved handoff.

## Done when
All stages complete; sample run passed acceptance with zero sends; per-message approval gate demonstrated; handoff doc delivered; closeout passed; receipt written. v0 tracking in queue/skill_trust.jsonl.
