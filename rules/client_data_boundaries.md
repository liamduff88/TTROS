# CLIENT DATA BOUNDARIES
> Revisit: on a new client onboarding pattern or an isolation incident. · Last touched: 2026-07-15.

## The rule
One client, one thread, one folder, one entity page. Absolute — not a
default that yields under time pressure (never.md #9).

## What this means in practice
1. A delivery subagent working client A cannot read client B's folder or
   entity page in the same run, even for "just context."
2. Queue items are single-client. A cross-client comparison or rollup is a
   new queue item the orchestrator explicitly scopes as such — never an
   incidental side effect of a client task.
3. A client note must be declared by its exact canonical
   `business_brain:<relative-path>` pointer. No basename lookup or broad client
   memory fallback is allowed. Until the Block 2 scope registry is accepted,
   unresolved client scope stops before any client Brain content is loaded.
4. Until Block 2 promotion authority is accepted, legacy skill/workflow text
   that says to create or update an entity page means "record a proposed
   update and its exact logical pointer in the receipt"; it does not authorize
   a Business Brain write.
5. North Shore is a separate client system outside this OS entirely — not
   a folder inside it. Never read, write, or reason about it from here
   beyond what's explicitly scoped in that turn (never.md #2, PROTECTED_PATHS.md).
6. Outreach and drafts state their basis per client (CASL block) — never a
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
