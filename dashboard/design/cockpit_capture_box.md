# Cockpit Capture Box — implemented contract
> Revisit: if the canonical inbox or dashboard write path changes. · Last touched: 2026-07-19

## Purpose and placement

The existing dashboard shell exposes one persistent, expanding capture field on
every view. `Ctrl+Enter` or **Capture** submits deliberate raw input to the
Business Brain intake; the existing Cockpit command and Message Board flows
continue to create and route work separately.

## Write contract

- Endpoint: `POST /api/dashboard/capture` with `text` and a client-generated
  replay-safe `capture_id`.
- Shared writer: `tools/business_brain_inbox.py`.
- Target: `business_brain:inbox/source_notes/capture_<UTC timestamp>_<capture hash>.md`.
- Notes carry a stable ID, `type: intake`, `source: cockpit_capture`, capture
  timestamp/identity, and payload hash. Unicode and multiline body bytes are
  retained; publication is append-only and atomic.
- The canonical inbox is resolved through
  `business_brain:inbox/README.md`; unsafe names, traversal, escapes, and
  conflicting replay IDs fail closed.

## Boundaries

Capture performs no model call, cleanup, indexing, promotion, queue creation,
or external action. Raw intake stays excluded from local search and Graphify;
the existing reviewed memory-promotion contract remains the only path to
durable knowledge.
