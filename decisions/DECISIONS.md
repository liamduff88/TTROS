# DECISIONS.md — log of decisions that change system behavior
> One entry per behavior-affecting change. Newest first.

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
