# TTROS_BRAIN_RECONCILIATION_RUNBOOK
> Layer: operating_context · Owner: Liam · Status: **adopted implementation authority** — adopted by Liam on 2026-07-15 together with the dated packaging amendment to the locked design
> Revisit: after each block closeout, and at activation · Last touched: 2026-07-15

Scope: Business Brain reconciliation + capture layer. Grounded in `TTROS_BRAIN_RECONCILIATION_LOCKED_DESIGN_2026-07-15.md` (+ its 2026-07-15 packaging amendment) reconciled against `TTROS_SYSTEM_READOUT_2026-07-15.md` (HEAD 8b26010). Blueprint V2 remains the master OS design; nothing here reopens WP0–WP12 or Dashboard Passes 0–10. Where the readout contradicts a stale implementation assumption, the readout wins; locked-design decisions stand.

End state: agents read the Brain before knowledge-sensitive work via scoped pointers → Graphify targets → search → direct file (token-cheap, no whole-vault reads); completed work promotes durable knowledge back with authority tiers and provenance; Gmail capture ingests, triages, and proposes work through the existing queue; client isolation is enforced structurally. Everything auto-proposes; nothing auto-acts. Brain retrieval, promotion, and Graphify-assisted selection are already operational at Stage A completion — Phase 6B activates only live capture and recurring read-only polling.

## Execution model

- **Three implementation blocks, two inter-block checkpoints, one Phase 6B activation gate.** Block 1 closeout acceptance authorizes Block 2. Block 2 closeout acceptance authorizes Block 3. Block 3 produces the completed Stage A evidence package and stops at the Phase 6B activation gate — it does not create a separate Stage A approval followed by another activation approval.
- Within a block: full repair loops (inspect → repair → test → diagnose → repair → rerun) until green, a genuine protected/external boundary, or genuinely unavailable infrastructure. No per-phase queue items, no stop-and-ask, no failure-count thresholds, no operator-relayed subtasks.
- Intended cadence (non-contractual): blocks run back-to-back; if closeouts are clean, the Stage A package can be presented at the activation gate the same day.
- The live queue is used only where the queue itself is under test (promotion proposals, capture dry-run) — never as block management structure.
- Liam is required only for: the two inter-block checkpoints, the single Phase 6B activation decision, substantive review-tier promotions, external mutations (sends/replies/bookings), credentials, destructive cleanup, Git commit/push, and merging decision text into the already-dirty `decisions/DECISIONS.md`.

## Global rules (all blocks)

- Client isolation is absolute. Structured `client_scope` must gate every content load and result — search rows, Graphify targets, thread context, Brain notes, evidence — before anything reaches a model. Unresolved scope fails closed. Readout §12: currently convention-only; treat as **not enforced** until Block 2's enforcement layer and Block 3's test suite are green.
- No agent writes the Brain outside the promotion writer. Review-tier promotion routes `human_review`; `needs_liam` does not exist and is never created. Deterministic-automatic maintenance (allowlisted classes only) executes with receipt + provenance and does **not** create a queue item to auto-accept.
- Nothing external goes live inside Stage A. All connector work is fixture-based until activation.
- Preserve the four pre-existing uncommitted Git changes (`decisions/DECISIONS.md`, `tests/test_aos_orchestration.py`, `tools/aos-linux-runtime.sh`, `tests/test_aos_dashboard_cleanup.py`). Keep the two merge-ready decision entries as separate files; merging into `DECISIONS.md` is a Liam action.
- Protected boundaries verbatim from the readout prompt: North Shore workspace, telegram bridge, route/lane JSONs, `.env`/secrets, legacy paths, Hermes global/default profiles.
- Snapshot the vault (dated SHA-256 content manifest, readout §15 method) before any vault-mutating step; never write into `_backups/`.
- Schema changes additive-only against readout §6 contracts. No new queue statuses, no second store. `memory_promotion` run-ledger array holds durable **references** (proposal item ref, promotion receipt path, write-record ID) — no invented state enum; outcome state lives in the referenced promotion receipt.
- **Raw capture records, bodies, thread text, attachments, and sensitive excerpts never enter Git, search, Graphify, promoted knowledge, previews, receipts, or broad artifacts. Only the typed, allowlisted metadata projection defined in 3.6 may enter search or Graphify.**

---

## BLOCK 1 — Knowledge plane: repair and prove
*(canonical structure and derived-output changes; no substantive knowledge promotion or runtime action)*

### 1.1 Embedded preflight (no gate)
- Revalidate HEAD 8b26010 (record and assess any delta), worktree state, live paths: repo `/home/liam/agentic-os-live`, vault `/mnt/c/Users/Admin/Documents/A-Time to revenue/TTROS Business Brain`, Graphify root `/home/liam/graphify-brain`.
- Inspect queue claims/processes/timestamps. Preserve all unrelated items untouched; block only on a **proven active writer** overlapping a surface this work changes. Stale nonterminal records are not blockers.
- Record the five `~/.composio/tool_definitions/*.json` files as known benign capability-schema cache created during the readout, now part of the current baseline. No cleanup, no dedicated phase.
- Before-state manifests for vault, Graphify root, and every file this block will touch.

### 1.2 Active-consumer inventory and disposition
Enumerate and disposition (repair or explicitly retire) **every** live Brain consumer:
- `tools/aos_indexer.py` BUSINESS_BRAIN_ROOT → resolves the live `/mnt/c` vault through the shared runtime resolver below.
- **Logical pointer convention:** convert documentation and pointer files (`context/MEMORY_ROOT.md`, `memory_index`, and any others found) to canonical logical `business_brain:<relative-path>` references. One shared runtime resolver maps those references to the live `/mnt/c` vault. No consumer keeps its own root constant or performs filename-only resolution.
- `CODEX.md` / `CLAUDE.md` stale references (`graph-imports/aos-repo`, `_substrate.wiki`) → corrected or removed.
- `/api/dashboard/memory` → repaired to read the live vault and real promotion state, **or** explicitly retired as a misleading surface; may not remain unaddressed. Same disposition for the dashboard's inferred "promotion queue."
- `_backups/` excluded by rule from search, Graphify, pointer resolution, and all consumers.

### 1.3 Vault structuring (19 current notes; first-time structuring, not decay repair)
- Minimal frontmatter **where useful**, per locked design §4: stable `id` on canonical retrieval targets; `type` where operationally useful; `status` only where lifecycle means something; `last_touched` only on machine-maintained notes; `source_receipts` only on notes/sections participating in promotion provenance. No blank uniformity fields; README/inbox/index notes carry less than decision/client notes.
- Wiki-link pass: README + MEMORY_INDEX become real navigation roots; every canonical note reachable ≤2 hops; topical cross-links only where content already implies them.
- Tests: unique IDs (excl. `_backups/`), zero broken links, manifest diff shows only frontmatter/link additions.
- **Obsidian usability proof:** vault opens, root navigation works, wiki links resolve, backlinks/graph view behave, no backup notes surface as canonical.
- Content is not rewritten in this block.

### 1.4 Graphify Markdown proof and repair
- Fixture first: `graphify extract` (documents mode) against a synthetic `/tmp` vault, assessed against the **six-point** minimum contract (locked design §5): representative Markdown ingestion; stable note identity + source path; useful metadata + explicit wiki links; explicit-vs-derived edge distinction where available; ranked file-target results (paths + scores, never bodies); freshness manifest with rebuild/fallback.
- Repairs land in the **TTROS wrapper/service**, not the pipx package, unless inspection proves no maintainable wrapper-level path exists.
- **Namespace and trust boundary:** publish the Business Brain graph under a dedicated discovered namespace inside `/home/liam/graphify-brain`. Do not overwrite or repurpose `repo_graphs/`, Pass 10 outputs, receipts, or history. Block 1 may prove client-target filtering with fixtures, but no live client-sensitive Graphify target is trusted or exposed to a model until Block 2's common isolation layer is green.
- Live read-only extraction of the post-1.3 vault into that namespace — authorized by this block, no separate go. Prove: source vault unchanged (manifest); idempotent rebuild (identical hashes on unchanged input); stale detection; failed rebuild retains previous published graph; stale graph falls back to search/pointers.

**Block 1 closeout → checkpoint 1:** consumer disposition table, vault usability proof, Graphify contract results, manifests proving nothing else touched. Liam's accept authorizes Block 2.

---

## BLOCK 2 — Write machinery: scoped retrieval, isolation, promotion (first real Brain write)

### 2.1 Client-scope authority and enforcement layer (before any live client-sensitive retrieval or write)
- **Canonical client-scope identity registry:** select and implement the durable registry used by every retrieval boundary. It lives in an existing authoritative Brain or OS configuration contract — never transient capture storage.
- One shared enforcement mechanism covering: scoped pointer resolution; direct Brain-note loading; search filtering in SQL/API **before** result construction; Graphify target filtering before paths return; thread/evidence loading; receipt validation. Unresolved scope fails closed. Two-client fixture negative tests green before anything downstream runs.

### 2.2 Scoped loader + actual-read provenance + fail-closed classification
- Retrieval hierarchy per locked design §2: explicit pointers → Graphify ranked targets (unclear/cross-cutting only) → search → direct file. Graphify consulted, never authoritative; smallest relevant context, never whole-vault.
- The loader **emits** `brain_context_used` from actual successful reads — note `id`, canonical relative path, `client_scope` where applicable, retrieval route, optional content hash. Never inferred from declared work-item `sources`. Projected into the receipt via the smallest compatible existing structure.
- Technical-only is an affirmative classification, never the default. Declared Brain pointers, business-facing skills, client scopes, business outputs, or promotion candidacy ⇒ knowledge-sensitive. **Ambiguous or unclassified work is knowledge-sensitive and stops to `needs_input`.** `degraded_context` may proceed only where an explicit contract declares that the specific work can safely continue without the missing source, records the missing context and fallback used, and cannot expose client-sensitive content. Degradation is never the default alternative to failed classification or unresolved client scope. Explicit technical-only records `not_applicable`.

### 2.3 Authority tiers (before the writer runs)
- `context/MEMORY_PROMOTION_POLICY.md` is amended directly with the three authority tiers mapped to concrete note types and change classes. The two new decision entries remain separate merge-ready files until Liam deliberately merges them into `decisions/DECISIONS.md`.
- **Deterministic-automatic:** starts with the smallest proven subset of the six locked-design classes (`last_touched` stamps; provenance/source-receipt links; index entries and backlinks; stable-path corrections; outcome-index additions; generated content strictly inside explicit markers) — each enabled class named in policy with its passing test cited; exact-rule match; touches only its authorized field/machine-owned marker; idempotent; receipt + provenance; no queue item.
- **Review-tier:** positioning, pricing/offers, client commitments (incl. comms-derived facts), strategy, legal/financial, architecture/protected boundaries, new policies, conflicts, deletion/supersession → `human_review`.
- **Never-promote:** locked design §3 list; records refusal reason, generates no writable candidate.
- Tests: one per tier + fail-closed (unclassifiable ⇒ review-tier).

### 2.4 Atomic promotion writer + rollback contract
Reuse `durable_replace_text` pattern: path containment inside the vault; target-hash check; atomic replacement; preimage retained; machine-section markers with a merge guard refusing text outside markers; provenance (receipt → diff → path → post-write hash); `memory_promotion` reference appended.
**Recovery contract:** the canonical mutation, post-write validation, and provenance linkage form one recoverable transaction. If validation or provenance linkage fails after mutation, restore the verified preimage atomically and record the failed attempt. Preimages and write records use existing receipt/artifact mechanisms; no new rollback or promotion-state store.
Idempotency/recovery tests: duplicate approval/review-close; repeated evaluation; repeated writer invocation; stale target hash; partial write failure; failed post-write validation; provenance-write failure after mutation. Failed reindex retains the previous usable index.

### 2.5 End-to-end proofs (order fixed: loader → tiers → writer → write)
1. Review-tier path: real proposal lands in `human_review` with candidate diff + provenance, **no write occurs** pre-accept. Any proof item left in `human_review` is a genuine normal review item, **not a prerequisite for Block 3**; otherwise use and close a disposable proof item through the existing review path.
2. Never-promote path: rejection with reason, no candidate.
3. **One deterministic-safe real write** — e.g. outcome-index addition or generated-marker section — snapshot-backed, atomic, hash-checked, idempotent, human-sections proven protected. No mid-session approval; authorized by this block.
4. Reindex → **a fresh execution context created, executed, and closed within Block 2** (not a Liam-dispatched task or operator relay) retrieves the promoted content by pointer **and** by search, with `brain_context_used` evidence.
5. Fixture version of the full loop added to the test suite.

### 2.6 Graph-assisted selector
Wired into the loader for unclear/cross-cutting discovery only; returns scoped paths, never content; stale graph ⇒ explicit degraded record + fallback, never silently trusted; one acceptance run showing the receipt attributes each source to its hierarchy step. If Graphify closed Block 1 with material deferrals, this shrinks to pointers + search and records that as standing state.

**Block 2 closeout → checkpoint 2:** isolation tests, provenance samples, the real-write diff + snapshot, later-retrieval receipt, recovery test results. Liam's accept authorizes Block 3. At this closeout the Brain is an operational read/write knowledge plane independent of capture.

---

## BLOCK 3 — Capture, built dark (fixtures and stubs only; produces the Stage A evidence package)

**Stage A boundary, explicit:** all Gmail responses, bodies, and threads in this block are fixtures. The ambiguous classifier is a stub/fake exercising the production interface — no live model is invoked. The stub exercises the production accounting path and writes an honest token-ledger line using the stable Stage 2 event value, explicitly recording no agent/model invocation and zero measured token usage; it must not insert estimated, synthetic, or representative token counts. "Bodies only at Stage 3" means fixture bodies during Block 3. Live body or thread retrieval, live polling, and live model calls are Phase 6B activity after explicit approval.

### 3.1 Storage contract first (readout §11: no safe home exists)
One runtime location proven by negative tests: Git-ignored; outside dashboard preview roots; outside search watch roots by default; client-scoped subpaths; restrictive permissions; durable append-only writers; defined retention boundary; covered by backup machinery. Candidate: ignored `capture/` runtime root beside `dashboard/data`-style state; final path validated against live `.gitignore`, preview routes, watch config. Three negative tests: not tracked, not previewable, not indexed after a reindex.

### 3.2 Contact mapping extends the Block 2 registry
Extend the Block 2 client-scope registry with contact/sender/thread-to-client mapping contracts. Use synthetic mappings for Stage A fixtures. Do not infer or populate live durable client facts from communications without the applicable review or activation approval. The capture root holds only raw records, cursor/idempotency state, and derived runtime evidence — never durable identity.

### 3.3 Stage 1 — deterministic capture (dark)
Composio read-only Gmail adapter, smallest delta contract (readout §10): `GMAIL_GET_PROFILE` historyId checkpoint + `GMAIL_LIST_HISTORY(start_history_id)`; timestamp-bounded `GMAIL_FETCH_EMAILS(include_payload=false)` fallback. Metadata-only sweep. Zero model tokens. Fixture responses only.
**Raw records are immutable and append-only.** Triage decisions and proposals are separate derived records referencing raw IDs — nothing moves or rewrites raw evidence.
**Cursor transaction order:** read delta → deduplicate → durably append raw → durably record processing state → only then advance cursor. Crash at any point replays safely without duplicate raws or proposals.

### 3.4 Stage 2 — rules-first triage
Deterministic routing (client / internal / discard) via the mapping contracts, before any classifier involvement. Only genuinely ambiguous survivors reach the stubbed yes/no classifier interface, sized to the single item's metadata — no Brain context, no cross-client context. Each stubbed call writes its own honest token-ledger line with a stable `event` value, explicitly recording no agent/model invocation and zero measured token usage.

### 3.5 Stage 3 — scoped understanding (proposer, dark)
Fail-closed order in code: resolve `client_scope` → load only that client's thread context, Brain pointers, search, Graphify targets through the Block 2 enforcement layer → unresolved scope stops to `needs_input`, loads nothing. Output: a `proposed_from_capture` work item in `human_review` — **a validated source/tag convention, not a new queue status or parallel item type** — with evidence references (paths + IDs, never bodies). Comms are evidence of approval, not approval. Never sends, replies, books, edits, acts.

### 3.6 Capture metadata projection (structural, not conventional)
Exactly which fields may enter search and Graphify: path, permitted subject, `client_scope`, linked item, timestamp. Bodies, thread text, attachments, sensitive excerpts are **structurally impossible** to serialize into index rows or graph nodes (typed serializer; negative test proving no body text in index or `graph.json`).

### 3.7 Whitelist governance (no empty file)
Auto-continue graduation criteria recorded in the promotion/capture policy (≥2 weeks observation, sample size, zero false-positive approvals for the exact rule, thread/identity binding, unambiguous payload, idempotency, kill switch, receipts, one Liam decision per entry, forbidden categories never eligible). A runtime whitelist representation is created only when machinery genuinely requires one — and stays empty.

### 3.8 Proofs and integrated Stage A closeout
- Isolation suite (cross-client search / graph / thread-load / unresolved-scope all fail closed **before content load** — general enforcement, not North-Shore-specific).
- Full fixture dry-run: fixture inbox → capture → triage (incl. one ambiguous item through the stubbed classifier) → proposal in `human_review` → review-close — receipts and per-stage ledger lines throughout; zero live connector content calls anywhere.
- Integrated closeout: affected unit + regression suites; real local search and Graphify proof; the Block 2 promotion/later-retrieval evidence; capture dry-run; before/after protected-boundary manifests; one `PASS` or genuine blocker.

**Block 3 closeout = the Stage A evidence package, presented at the single Phase 6B activation gate below. No separate Stage A approval.**

---

## PHASE 6B — Activation gate (the one external boundary)

Phase 6B activates only live capture and recurring read-only polling; retrieval, promotion, and Graphify-assisted selection are already operational. The observation window gates only the **auto-continue whitelist** — narrowly defined rules that may treat specified inbound evidence as approval to continue the exact identity- and thread-bound work item. It does not grant general authority to act on email, and it does not delay live use: from activation day one, capture ingests, triages, and proposes into your queue, and you approve.

1. Verify live Composio Gmail connection at toolkit level (readout-safe method, no content read).
2. One-screen activation plan presented with the Stage A evidence package: mailbox/labels, delta mechanism, schedule, storage paths, mapping source, model stages + budget class, kill-switch location.
3. Liam's single explicit activation approval, recorded as a decision entry.
4. Activate recurring read-only polling via existing scheduler machinery (per `context/ACCESS_MODEL.md`; never touching protected Hermes global/default profiles). First live cycle watched end-to-end and receipted.
5. Ongoing observation while the system is in use (weekly rollup into `queue/rollups/`): false positives/negatives, token spend per stage, isolation incidents (target zero).
6. Whitelist entries considered only after the observation window, one Liam decision each, under the 3.7 graduation contract.

Kill switch halts polling immediately; any isolation incident suspends the job pending Liam review; the observation clock restarts after routing-affecting rule or mapping changes.

---

## Dependency map

```
Block 1 (preflight → consumers/resolver → vault → Graphify namespace proof)
   → checkpoint 1
Block 2 (client registry + isolation → loader/provenance/classification → tiers → writer/rollback → real write + fresh-context retrieval → graph selector)
   → checkpoint 2
Block 3 (storage → mapping extension → capture/triage/proposer dark → projection → isolation suite → dry-run → Stage A evidence package)
   → Phase 6B activation gate (single approval)
   → live polling + full system use → rolling observation → whitelist entries later, individually
```
