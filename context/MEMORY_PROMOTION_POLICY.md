# MEMORY_PROMOTION_POLICY.md — what earns a place in the Business Brain
> Revisit: when a new memory area is added or a promotion causes contamination. · Last touched: 2026-11-06.

## The flow
```
TTROS Business Brain (durable, stable)
        ↓ pointers, not copies
Operating Hermes reads only the files the lane/task needs
        ↓
Queue item references the specific source, not the whole vault
        ↓
Agent/workbench executes scoped work
        ↓
Receipt captures what changed
        ↓
Liam-reviewed results get promoted back
```
Memory is read by reference, never dumped wholesale into a task.

## What lanes read (scoped, not the whole Brain)
- **Revenue** — company, positioning, ideal_clients, offers, sales_and_revenue,
  marketing_voice.
- **Marketing** — company, positioning, offers, website/content, marketing_voice.
- **Delivery** — delivery_model, active_projects, protected_paths, relevant
  scope notes.
- **Ops** — current_priorities, active_projects, decisions, protected_paths.

## Executable authority tiers

Every candidate is classified by `tools/business_brain_promotion.py` after its
exact `client_scope` and canonical target pass the shared registry and its
provenance passes the rule below. An unclassifiable candidate fails closed to Liam review.

### Deterministic automatic

Two rules are enabled. Each rule names the one writer allowed to apply it, and no
other candidate automatic class is enabled.

- **`generated_marker_section`**. It may update exactly
  `business_brain:index/MEMORY_INDEX.md`, inside the exact
  `block-2-outcome-index` machine marker. The promotion writer refuses every
  other target, marker, or byte outside that boundary. The rule is
  deterministic, idempotent, receipt-backed, and requires no queue item.
- **`generated_navigation`** (Liam decision D1, 2026-11-06). It covers navigation
  link lists only:
  - the generated section of `index/MEMORY_INDEX.md`;
  - folder `INDEX.md` link lists (`sources/*/INDEX.md`);
  - hub-page link lists (`people/*.md`).

  The content lives inside the `TTROS:HERMES:generated-navigation` managed
  section. It is written only through `brain_memory.managed_section` plus
  `brain_memory.write_transaction` (commit, push, search and entity refresh),
  never through the promotion writer, which refuses it. The rule renders links
  only. Any change to what a note *says*, including a hub page's prose, stays
  Liam-review tier.

Provenance for any candidate must be either a registered evidence identity in
the scope registry, or an indexed global Brain pointer. The second is the same
check `shared_brain_submit` uses (Liam decision D2, 2026-11-06).

### Liam review required

Positioning; pricing and offers; client commitments; communications-derived
durable facts; strategy; legal or financial conclusions; architecture or
authority changes; protected-boundary changes; new policies; conflicts;
deletion; and supersession always route to the existing `human_review` status.
The proposal must contain canonical target, target preimage hash, candidate
diff, source/provenance references, `client_scope`, and the review-tier reason.
It cannot write before an accepted review reference exists.

### Never promote

Secrets, credentials, authentication material, raw queue/runtime/PID/service
state, transient logs, full receipt or artifact trees, speculation presented as
fact, source trees or clones, raw Graphify output, raw communications, and
protected information outside task scope are refused. Refusals contain a safe
reason, no writable candidate diff, no successful promotion reference, and no
queue proposal unless a separate existing policy explicitly requires one.

## What never gets promoted
- Drafts, raw transcripts, failed runs.
- Old vault content, ZPC material, any legacy_harvest artifact.
- Secrets, connector account metadata, credentials, OAuth state.
- Speculative claims, unverified numbers, anything without a source.
- Anything from one client's context into another's (client isolation is
  absolute — never.md #9).

## The missing-contract gap this file closes
Queue workers know their memory pointers but historically had no explicit
convention for what to read and what to propose back. This file is that
contract: read only the scoped files above; propose promotions explicitly in
the receipt (`memory_promotion` field) rather than writing to the Brain
directly. A promotion is a proposal until Liam accepts it — mirrors the
`memory_promotion` prompt template in `queue/templates/`.

## Gate and transaction

The real write gate is `brain_memory.write_transaction`. It is the one path that
commits to the Business Brain: it takes the Brain lock, checks expected hashes,
runs `git diff --check` and an optional post-write validator, commits, pushes
when `TTROS_BRAIN_AUTOPUSH` is on, and refreshes search and the entity index.
The importer, submit, confirm, source intake, nightly hygiene and
generated_navigation all write through it. The promotion writer is a separate,
narrower path. It applies only `generated_marker_section` (and accepted
review-tier proposals), replaces the file directly, and does **not** commit.
Review-tier work uses the normal `human_review` ACCEPT/REVISE gate;
deterministic automatic work uses only the allowlisted rules above. The
promotion writer validates vault containment, `_backups` exclusion, scope ownership,
preimage hash, tier and marker; writes through same-directory atomic replace;
validates the postimage; creates a provenance receipt; and records refresh
state. If validation or provenance/linkage fails after mutation it atomically
restores and verifies the exact preimage, records the failed attempt, and
leaves no successful reference.

## Submit records and the semantic route (decisions D3, D4)

These are policy only. The implementation comes in a later phase.

- **D3.** Hub pages cite `inbox/distilled_packets/` submit records as plain
  pointers, never wiki-links. The vault validator treats links into `inbox/` as
  broken. Confirming a submit creates a review-tier proposal to add it to a
  `decisions/` managed section. Confirmation alone never writes canonical memory.
- **D4.** `source_intake_semantic` shares field names only with the ChatGPT
  ingest-note schema. It stays optional and operator-run, and its historical
  INDEX regex is fixed separately. Filing (identity resolution, navigation,
  proposals, checks) stays model-free.

Approval for D1–D5: Liam, 2026-11-06,
`business_brain:inbox/distilled_packets/shared-submit-9ee2033508c914546d5426dcff7e857c.md`.

## Enforcement

`context/client_scope_registry.json`, `tools/business_brain_scope.py`,
`tools/business_brain_context.py`, and `tools/business_brain_promotion.py` are
the executable contract. `memory_promotion` in the existing run ledger holds
durable references only; outcome state stays in the referenced promotion
receipt. Historical heterogeneous rows remain readable.

## Communications capture and future auto-continue governance

Raw capture records, message or thread text, attachments, sender details, and
capture-runtime state are never promotion inputs. A communications-derived
durable fact is always review-tier and cannot be written automatically.

No auto-continue rule is active. Before Liam can enable one exact rule it must
have at least two weeks of live observations, a representative sample, zero
known false-positive approvals for that exact rule, exact identity plus
thread/work-item binding, an unambiguous phrase and payload contract,
idempotency, a kill switch, receipt evidence, and one separate Liam decision
for that rule. Pricing or scope changes, legal or financial commitments,
contracts, payment instructions, security or credential changes, new
recipients, and ambiguous or conditional language are never eligible.
