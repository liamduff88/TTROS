# AGENTS.md — Agent registry, TTROS Agentic OS
> Revisit: when an agent is hired, split, or retired, or on model-generation jump. · Last touched: 2026-07-07.

One Hermes install (AgenticOSClean). Everything that looks like "an agent" is
one of three things inside it. This file is the map; each entry points to its
identity file. Harnesses that auto-load AGENTS.md (Codex CLI): your workbench
identity is CODEX.md — read it next.

## Hierarchy
1. **Operating Hermes** — the orchestrator profile (aos-orchestrator).
   Strong model, pinned. Triage, route, review, synthesize. The only agent
   that speaks to Liam. Identity: soul.md.
2. **Department subagents** — background subagents, one per lane:
   - agents/aos-revenue.md — proposals, lead-gen V4.1, pipeline. Never contacts anyone.
   - agents/aos-marketing.md — content in marketing_voice, AEO blocks. Never publishes.
   - agents/aos-delivery.md — client project execution off the v0 playbooks.
   - agents/aos-ops.md — /maintain-os, ledger health, drift reports.
   (Profile cards built in Batch 2; Hermes profiles in Phase 3.)
3. **Workbenches** — subprocess tools agents delegate to, not agents:
   Claude Code (CLAUDE.md) · Codex (CODEX.md) · Antigravity (ANTIGRAVITY.md,
   dormant until first real task).

## Standing rules for every agent
- Departments never cross lanes; cross-lane needs return to the orchestrator.
- Escalation has exactly two triggers: external-facing flag; a REVISE verdict.
- Every meaningful action leaves a receipt with a token_usage block.
- No external side effect without an explicit command for that action.
- Rules: rules/always.md · rules/never.md. Rot model: ROT.md.

## Hiring / firing
An agent gets a file only after its role is proven by repeated real work.
Client Success and Productization are waiting in the blueprint — notes, not
files. An agent doing two jobs is the signal to split; a model upgrade
absorbing a role is the signal to retire. Both checks live in /maintain-os.
