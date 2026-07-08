# CLIENT DATA BOUNDARIES
> Revisit: on a new client onboarding pattern or an isolation incident. · Last touched: 2026-07-07.

## The rule
One client, one thread, one folder, one entity page. Absolute — not a
default that yields under time pressure (never.md #9).

## What this means in practice
1. A delivery subagent working client A cannot read client B's folder or
   entity page in the same run, even for "just context."
2. Queue items are single-client. A cross-client comparison or rollup is a
   new queue item the orchestrator explicitly scopes as such — never an
   incidental side effect of a client task.
3. Entity pages (`_substrate.wiki/entities/client-*.md`) are the only
   canonical source of a client's tools, CRM, lead sources, and approval
   contacts. Playbooks (Stage 0 INTAKE) refuse to start without the right
   one loaded and the wrong ones absent from context.
4. North Shore is a separate client system outside this OS entirely — not
   a folder inside it. Never read, write, or reason about it from here
   beyond what's explicitly scoped in that turn (never.md #2, PROTECTED_PATHS.md).
5. Outreach and drafts state their basis per client (CASL block) — never a
   templated claim that could apply to more than one client's facts.

## Failure mode this prevents
Blended data isn't just messy — it's a client seeing another client's
information, a scope commitment made on the wrong facts, or an outreach
draft carrying the wrong CASL basis. Treat any blend as a stop condition,
not a merge point.

## Enforcement
Hook: client_isolation_check.md — fires before any read spanning more than
one client folder in a single run, blocks and surfaces the match in the
receipt. Mirrored in never.md #9, Blueprint V2 §3.4 non-collision rule 4,
OPERATOR_CONTRACT.md.
