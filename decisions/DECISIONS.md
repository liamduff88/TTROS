# DECISIONS.md — log of decisions that change system behavior
> One entry per behavior-affecting change. Newest first.

## 2026-07-12 — Cockpit commands are deterministic local queue intake

Cockpit plain-language commands reuse command-route matching, owner inference,
and the existing queue creator. A submission creates one local `agent_todo`
item and never invokes a model or connector; unmatched commands route to the
explicitly named owner when present and otherwise to Hermes for later triage.
Selecting a Work Queue item collapses the list to a compact rail so the item
detail becomes the primary workspace, with an explicit expand control.

## 2026-07-12 — Dashboard shell uses ephemeral IDE sessions and a recoverable focus rail

Dashboard destinations now live in one grouped, collapsible sidebar while the
top bar is utility-only. Session tabs remain React view state: Cockpit is
pinned first, one preview is reused until pinned, and eight tabs is the cap.
Queue focus mode collapses non-selected tasks into an ID/color/state rail, and
Needs Me collapses to a visible amber count strip. No tab, focus, or rail state
is written to the backend, queue, filesystem, or browser durable storage.

## 2026-07-12 — Unavailable token usage is never rendered as exact zero

Dashboard token summaries treat an all-zero usage block with a non-empty
`unavailable` list as unavailable, not known zero. Ledger rows say
`unavailable`; periods containing both exact usage and missing components say
`known + gaps`; periods with no known usage say `unavailable`. This preserves
the schema's structural zeros without presenting them as reported model usage.

## 2026-07-12 — Buildout uses one final integrated human review

Definition `linux-authority-r3` removes the obsolete routine Pass 2 operator
checkpoint. Pass 2 performs its automated/build/browser/screenshot/visual proof
inside its implementation session, closes `done`, and unlocks Pass 3 through
the existing dependency runner. Normal Passes 1–9 continue sequentially; the
non-executable parent enters the one planned integrated `human_review` only
after all normal children have done evidence. Existing exceptional safety
states and the one bounded consolidated correction cycle remain unchanged.

## 2026-07-11 — Workflow aggregates and one bounded correction cycle

`owner_type=workflow` now marks a queue record as a non-executable aggregate;
all starter-agent `next` and direct claim paths reject it regardless of display
owner/status. Dependency advancement routes generic children to executable
`agent_todo` before any review gate, while the tagged historical acceptance
fixture retains its established behavior. When all package-identity children
are done with done receipts, deterministic orchestration moves the parent to
`human_review`. The existing review-close endpoint permits one consolidated
Needs changes note, creates one Codex `pass:correction-1` child, holds the
parent in non-actionable `inbox`, then returns it to review after correction;
a second request for that definition version is rejected.
Final workflow approval writes one idempotent `final-closeout` review receipt,
distinct from the earlier Needs-changes receipt even when both actions occur
within the same timestamp second.

## 2026-07-11 — Lock release is bound to exact owner identity and durable namespaces
Queue and package directory locks now capture protocol/package identity, token,
host, runtime, PID, process-start identity, and acquisition timestamp, and
release only when the complete validated owner record is unchanged. Candidate,
publication, quarantine, restoration, release, and deletion transitions fsync
their containing directory; a publication-sync failure removes the canonical
entry and retains noncanonical evidence. Empty orchestration ticks no longer
rewrite queue or persistent tick-lock metadata. The existing Hermes launcher
uses a typechecked production dist from the current install via the CLI's
supported `HERMES_WEB_DIST`/`--skip-build` contract and PID guards duplicates.

## 2026-07-11 — Linux-native storage is the sole Agentic OS authority
The canonical live root is `/home/liam/agentic-os-live`, configurable through
`AOS_ROOT` for ordinary Linux VMs and containers. Queue, package, ledger,
receipt, dashboard, runner, and orchestration mutations fail closed on native
Windows and Windows-backed mounts. POSIX durability is same-directory temp,
flush, file fsync, atomic replace, and containing-directory fsync. Windows is
only an optional WSL/browser adapter; the old `/mnt/c` repository is a frozen
rollback snapshot and native-Windows mutation proofs are superseded.

## 2026-07-08 — Dashboard v1 ACCEPTED: startup + close-hook closeout
Run 4 closed Dashboard v1 acceptance with startup hardening and live
close-hook validation.

PID misattribution note from AOS-2026-0049: uvicorn reload on Windows can
orphan a multiprocessing child serving stale code. Windows' TCP table can
attribute the `:8010` listener to a dead parent PID, making it look
unkillable. Diagnosis: find the real child via parent_pid lookup. Prevention:
the hardened launcher now does evidence-based cleanup with
`Stop-StaleAgenticOSBackend.ps1` before every start.

Startup/jsonschema root cause and fix: the launcher previously used plain
`python`, which allowed mixed interpreters and no provisioning, so backend
dependency state drifted from `dashboard/backend/.venv`. Fixed:
`Start-AgenticOS-Backend-Auto.ps1` now pins
`.venv\Scripts\python.exe`, creates the venv if missing, import-checks
`jsonschema`, installs `requirements.txt` only on failure, launches uvicorn
persistently, logs to `logs/backend-auto-stdout.log` and
`logs/backend-auto-stderr.log`, and health-checks `/api/queue/summary`.
Validated live, including across a full Windows reboot on 2026-07-08.

Queue guardrail worth knowing: `POST /api/queue/items/{id}/review-close` only
accepts items in `human_review` status; move items there first via `/status`.
This was hit during live testing.

Telegram close-hook was live-validated end to end on 2026-07-08: API
review-close on test item AOS-2026-0047 (`source: telegram`) ->
`_telegram_reply_on_close` -> bridge send -> message received on Liam's phone.
Dashboard v1 is ACCEPTED as of this date.

## 2026-07-11 — Buildout read-only gates suppress subprocess bytecode
The buildout loader's shared subprocess wrapper sets
`PYTHONDONTWRITEBYTECODE=1`. This keeps real `inspect`, `validate`, and
`status` validation paths read-only when they invoke the existing queue CLI
help contract, while leaving write-command behavior and the queue contract
unchanged. The same gate verifies locked-baseline ancestry but deliberately
does not require a clean worktree, because reconciliation repairs are reviewed
and validated while intentionally uncommitted.

## 2026-07-12 — Direct Codex usage reconciles only after process exit
The existing `tools/aos-queue.py` coordinator now owns the Direct Codex
launch boundary. `codex-run` requires an explicit work-item ID, uses the
installed CLI's supported noninteractive JSONL mode, captures combined output,
waits for exit, and replaces that completed item's existing receipt sidecar,
receipt block, and single token-ledger row from the terminal usage event.
`codex-reconcile` applies the identical in-place path to authoritative pasted
post-exit evidence. Neither path selects the newest item, appends a correction
row, invents a model identity, or creates a second runner/ledger/store.
Cached-input and reasoning-output counts remain capture-evidence metadata while
the standard input/output totals retain their existing schema meaning.

## 2026-07-12 — Codex invocation usage is independent of queue status
Codex reconciliation now keys exact persistence by work-item ID + session ID
and runs at supervised process exit for every honest queue state, including
`human_review`. Structured `turn.completed` usage outranks the same supervisor's
terminal summary; controlled operator evidence is the recovery fallback.
Unavailable may reconcile to exact, exact may not downgrade, conflicting exact
replays fail closed, and separate sessions remain separate token-ledger rows.
The existing item-level sidecar and one replaceable receipt block remain the
canonical dashboard surfaces; no second token store or queue was introduced.

## 2026-07-12 — Pass 2 rails and selection use canonical live identity
The existing Cockpit response now returns its complete derived
`human_review`/`needs_input`/`blocked` set instead of truncating the payload to
eight. The rail refreshes from the existing lightweight canonical queue-summary
endpoint, so unrelated Cockpit token/backup aggregation cannot hide operator
gates; a failed refresh retains the last good rail state. Queue selection records selection revisions
and request sequence so an older refresh cannot reapply its preferred item
after a newer click. No queue state, endpoint family, store, or lifecycle
semantics were added.

## 2026-07-12 — Dashboard Passes 3–9 remain projections over existing evidence
Lane cards, activity, schedule, artifact, pipeline, launcher, approval, and
handoff surfaces are projections over the existing queue, receipts, artifacts,
run/token ledgers, workflow contracts, and local status endpoints. No second
store, scheduler, queue, workflow builder, or approval layer was introduced.
Unknown cadence/token/status fields remain unavailable; Graphify Brain data is
not probed; and third-party output is explicitly manual/dry-run. The last child
uses generic orchestration to place the existing non-executable workflow parent
in `human_review`, preserving the one-note bounded correction contract.

## 2026-07-12 — Final Pass 2 selection, token provenance, and safe workflow editing
Queue selection now persists its canonical ID through the existing session-tab
parameters and validated browser session snapshot, preserving the prior
request-sequencing race guard. Token display sorts normalized authoritative
event timestamps newest-first and labels an invocation source only from explicit
persisted invocation evidence; owner, lane, profile, classification, and model
do not imply source. Workflow Bench uses one backend naming fallback and an
ID-only, stale-checked, atomic editor limited to canonical workflow definitions
plus the dedicated dashboard test-fixture root. Saving never executes. These
are Item 1's original Pass 2 defect repair and Liam-authorized Items 2–3 only;
no Pass 3–9 surface was added.

## 2026-07-08 — Token metering hardening (fix pass on commit 315a3a9)
Codex audit of the token-metering back end (commit 315a3a9) found four
issues; resolved as follows in `tools/aos-queue.py` and
`scripts/token_rollup.py`:

1. **Done-transition strictness.** Chose option (a): all three paths that can
   reach `done` (`status`, `receipt --status done`, `done`) now hard-refuse
   identically. `finalize_done()` builds the `token_usage` block and
   schema-validates both ledger lines *before* the item's status/receipt is
   persisted; on failure it raises and nothing is written or saved. Previously
   `status`/`receipt` soft-failed (status saved, error only on stderr) while
   `done` raised — but even `done` saved status=done before calling
   `finalize_done()`, so a "done" item could end up with no ledger entry.
   Chose strict refusal over documenting the soft-fail because the entire
   point of TOKEN_POLICY.md is visibility on every completed item; silent
   gaps defeat that.
2. **Schema validation enforced.** A run/token ledger line that fails
   `queue/run_ledger_schema.json` / `queue/token_ledger_schema.json`
   validation now raises (hard block) instead of being appended with a
   collected warning.
3. **est_cost_usd always deterministic.** Removed the caller-supplied cost
   override (`token_usage_json.est_cost_usd`, `usage_file.estimated_cost_usd`).
   Also started pricing the orchestrator component (previously excluded from
   cost entirely) at the run's confirmed model — matching the attribution
   `scripts/token_rollup.py`'s `by_model` breakdown already used — so the
   ledger's stored `est_cost_usd` and the rollup's recomputed total agree.
4. **Rollup dimensions + reconciliation.** `scripts/token_rollup.py` now rolls
   up by lane, profile, workbench, model, and budget class (was missing
   profile and workbench). It also no longer trusts a ledger line's stored
   `est_cost_usd` for any aggregate (totals, by_lane, by_budget, top_items) —
   every figure is recomputed from that line's own components on every run.
   This self-corrects historical data: regenerating `week-2026-W28.json`
   fixed the `total est_cost_usd 0.0` vs `by_model.claude-sonnet-5 0.1491`
   inconsistency to `0.1491` across every dimension, without editing the
   ledger itself.

Files touched: `tools/aos-queue.py`, `scripts/token_rollup.py`,
`queue/rollups/week-2026-W28.json` (regenerated), `context/TOKEN_POLICY.md`,
`hooks/token_budget_check.md`.

Tests: `tests.test_aos_queue`, `tests.test_aos_paths`,
`dashboard.backend.test_composio_hermes` — 69/69 pass. Manually verified in a
sandbox that a schema-invalid done-transition on all three paths (`status`,
`receipt`, `done`) leaves the item's status/receipts unchanged and appends
nothing to either ledger.

## 2026-07-07 — Created delivery_ops_documents skill
Created `skills/delivery_ops_documents` — closes AOS-2026-0042 gap, approved by
Liam directly, overrides default 3-repeat rule.

Files touched: `skills/delivery_ops_documents/SKILL.md`,
`workflows/delivery_ops_documents/workflow.md`, `decisions/DECISIONS.md`.
