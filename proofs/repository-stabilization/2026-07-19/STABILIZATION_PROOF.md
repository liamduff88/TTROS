# Repository stabilization proof — 2026-07-19
> Revisit: after Liam reviews the protected-path group or any listed commit group changes. · Last touched: 2026-07-19.

## Result

PASS. Every initial and current dirty path is classified, all accepted work is
preserved, recurrent local output is ignored or redirected, and the four
explicitly authorized protected modifications are understood, reconciled,
repaired where necessary, and green against their live callers and tests. The
five proposed path-limited commit groups are exact and disjoint. No staging,
commit, push, stash, broad restore, clean, connector send, or model call was
performed.

## Initial Git state

- HEAD: `0d88f9cf57f0d40f739bb7781a5e975912ef6afe`
- `main`: same object.
- `origin/main`: same object.
- Branch: `main`.
- Dirty entries: 110 total — 43 tracked modifications, 1 tracked deletion,
  and 66 untracked files.
- Initial category counts: A 48, B 0, C 0, D 1, E 2, F 2, G 32, H 21,
  I 4, J 0.
- Ignored baseline: 75,386 files, overwhelmingly existing logs,
  `node_modules`, dashboard build output, queue runtime, capture runtime,
  results, and caches. Relevant ignore rules and top-level counts were checked
  without opening protected interiors.

The exhaustive per-path evidence and disposition is in
`proofs/repository-stabilization/2026-07-19/path_manifest.tsv`. It contains 110
initial paths exactly once plus five paths created or newly modified by this
stabilization.

## Authorized protected reconciliation

Exact content was inspected only for the four paths Liam authorized. Git blob
IDs identify the complete current file content; patch SHA-256 values identify
the exact unstaged `HEAD`-to-worktree diff without copying connector or account
data into this proof.

| Path | HEAD blob | Current blob | Diff | Patch SHA-256 |
|---|---|---|---:|---|
| `connectors/telegram_bridge/telegram_bridge.py` | `9e124d22b264809061c01a17ebd2ab0f306f49be` | `4103619822141c7c1c5762b450b4a0d26543aa04` | +307/-16 | `bd90a100873efa8b25cbf1d9557287e4c7f0833e097c44c98b05bdc5cf3a157b` |
| `queue/command_routes.json` | `67c74f0efdcad629550f92cdf6503dfe61070a39` | `5944654291c0af2d15324393fce198ad89708da1` | +10/-3 | `d3f282bc7a0d1b67ec4db9f4bfbf403305a04889c8ed75c65f632a42bb9c7e21` |
| `queue/model_routes.json` | `d991c54ceb0cec04f239f443ce8164207d58e0ef` | `806c0d83076fa4ea16cdef513038e89f918ae247` | +14/-5 | `4c9a2062d7f43c399201d7f3cc112ece8b1b82dd755230bcaa4a16ad7496df29` |
| `queue/lane_profiles.json` | `19b75d79f7d2820184a2976c76f6560bfa1f7454` | `154341df00e3bed62c21a530fd0a4336de4dc7ac` | +16/-5 | `e0d51a1967d2dd5c15d30204f770f0f599021e0270b9ff119563a6baedc28ca5` |

### Origin, purpose, and finding

- `telegram_bridge.py` is a cumulative accepted repair: AOS-2026-0147 added
  completion-document delivery, AOS-2026-0152 established the existing queued
  intake route, AOS-2026-0160 proved canonical Claude/attachment delivery, and
  the AOS-2026-0161/0162 outcome recovered by AOS-2026-0164/0165 supplied the
  Linux root, composite status, title-first closeout, and split-intake contract.
  AOS-2026-0168 then established the final deterministic-vs-Hermes routing
  boundary. The implementation is required. Reconciliation fixed two defects:
  completion documents now remain inside their resolved allowlisted directory
  even through symlinks, and quick Codex/Claude acknowledgements no longer
  impose their 20-second ceiling on native Hermes or coordinated Codex review.
- `command_routes.json` was introduced by the accepted AOS-2026-0168 routing
  repair as the static statement of the live intent boundary. Its direct and
  fallback route labels did not exactly match backend `selected_route` values;
  they now use `direct_codex`, `direct_claude`, and `hermes_coordinator`.
  Fourteen route IDs, workflows, and patterns are unique; no later route is
  shadowed by an earlier substring match.
- `model_routes.json` was changed by AOS-2026-0168 so missing/unknown judgment
  routes bind `aos-orchestrator` per invocation without changing the sticky
  default. It is complete and required. Reconciliation added the accepted
  `ops` alias so model metadata matches `lane_profiles.json`; Codex and Claude
  remain the only intentional workbench-only model routes.
- `lane_profiles.json` was changed by AOS-2026-0168 so coordinator/reviewer
  lanes fail clearly instead of substituting a workbench or sticky default.
  It is complete and required. Reconciliation added the `unassigned` fallback
  lane, aligning `tools/aos-queue.py` owner resolution with the model-route
  fallback while retaining `fallback_profile: none` for coordinator startup
  failure.

No unrelated, obsolete, malformed, duplicate, unreachable, conflicting, or
unsafe change remains in the four files.

## Runtime writers observed

- Dashboard backend and frontend were live under the canonical repository and
  had only ignored log files open for writing.
- The orchestration runner was live under the canonical repository through an
  external relay and had ignored runtime logs open. The old launcher status
  missed it because `runner.pid` was absent.
- The Telegram bridge process was live under its protected directory and used
  ignored logs. Only the authorized source file was opened; bridge
  configuration, allowlists, chat values, credentials, and message content were
  not opened.
- Hermes dashboard/helper processes were live and used ignored logs.
- No active process had a non-protected tracked file open for writing.

## Runtime/generated-state repairs

1. Root `.vite/` is now ignored. Its two 23-byte dependency-cache manifests
   were removed after reference search, file-type/size checks, and proof that
   the frontend build regenerates successfully without them.
2. `queue/run_prompts/` is now ignored. Both existing prompts were retained in
   place because queue items can reference them.
3. Routine `workflows/queue_artifacts/AOS-2026-*.md` output and JSON receipts
   are ignored by default. Twenty-one routine/private/smoke artifacts were
   preserved locally; reviewed durable proofs have narrow negations and remain
   visible for a deliberate commit.
4. Live capture no longer mutates tracked `queue/rollups/`. Ordinary capture
   metrics now use the established ignored `capture/runtime/rollups/` store.
   The queue rollup directory is documented as explicit, intentionally
   versioned snapshot output.
5. Runtime status now recognizes exactly one canonical externally supervised
   root-relative orchestration runner and refuses ambiguous duplicates. The
   live runner was neither stopped nor restarted.
6. `workflows/queue_artifacts/direct_token_repair_clean_split.md` was restored
   byte-identical to HEAD; its deletion would have discarded accepted durable
   evidence.

## Mixed-file preservation

No Category C file remained after evidence review: large files contain several
completed, accepted tasks rather than completed plus in-progress hunks. The
shared dashboard backend is therefore kept in the single orchestration/runtime
group instead of being destructively split. No hunk was discarded. The only
overlap edited during stabilization was additive: existing user changes in
`.gitignore`, `tools/aos-linux-runtime.sh`,
`tests/test_aos_dashboard_cleanup.py`, and
`tests/test_aos_orchestration.py` were preserved and extended. This protected
reconciliation also made bounded additions to already-modified
`tests/test_aos_queue.py`, `tests/test_telegram_bridge_formatting.py`, and
`dashboard/backend/test_composio_hermes.py`; all prior hunks remain intact.

## Future commit groups

These groups are disjoint, cover all 89 visible paths exactly once, and are in
dependency-safe commit order. No staging or commit was performed.

1. `chore(runtime): stabilize generated-state boundaries` — 8 paths:

```text
.gitignore
proofs/repository-stabilization/2026-07-19/STABILIZATION_PROOF.md
proofs/repository-stabilization/2026-07-19/path_manifest.tsv
queue/README.md
queue/receipts/AOS-2026-0125-phase-6b-capture-live.json
queue/rollups/week-2026-W29.json
tests/test_aos_capture_live.py
tools/aos_capture_live.py
```

2. `feat(gmail): add draft-only prospecting capability` — 12 paths:

```text
connectors/CONNECTORS.md
connectors/NATURAL_LANGUAGE_CONNECTOR_PROMPT.md
connectors/composio_access_adapter.py
connectors/composio_access_spine.md
connectors/composio_tool_registry.json
connectors/gmail_draft_adapter.py
connectors/gmail_draft_policy.py
queue/receipts/gmail-draft-eaf7ea6500a619a6e2c05220.json
skills/prospecting_daily_run/SKILL.md
tests/test_gmail_draft_capability.py
tools/aos_indexer.py
workflows/prospecting_daily_run/workflow.md
```

3. `fix(routing): reconcile Telegram queue and Hermes orchestration` — 29
   paths, including all four authorized protected files:

```text
connectors/telegram_bridge/telegram_bridge.py
context/ACCESS_MODEL.md
context/OPERATING_BASELINE.md
context/RUNTIME_STATUS.md
dashboard/backend/main.py
dashboard/backend/test_composio_hermes.py
decisions/DECISIONS.md
queue/command_routes.json
queue/lane_profiles.json
queue/model_routes.json
tests/test_aos_codex_policy.py
tests/test_aos_dashboard_cleanup.py
tests/test_aos_orchestration.py
tests/test_aos_queue.py
tests/test_telegram_bridge_formatting.py
tools/aos-hermes-coordinator.sh
tools/aos-linux-runtime.sh
tools/aos-orchestration-runner.py
tools/aos-queue.py
tools/aos_orchestration.py
workflows/queue_artifacts/AOS-2026-0134_approval_routing_self_test_closeout.md
workflows/queue_artifacts/AOS-2026-0152_route_repair_codex_pass.md
workflows/queue_artifacts/AOS-2026-0157_work_claude_BOUNDED_CANONICAL_CLAUDE_PRODUCTION.md
workflows/queue_artifacts/AOS-2026-0158_work_claude_FINAL_BOUNDED_CANONICAL_CLAUDE_PRODU.md
workflows/queue_artifacts/AOS-2026-0159_work_claude_FINAL_GREEN_CANONICAL_CLAUDE_PROOF_W.md
workflows/queue_artifacts/AOS-2026-0160_work_claude_CANONICAL_CLAUDE_AND_TELEGRAM_ATTACH.md
workflows/queue_artifacts/AOS-2026-0164_token_evidence.md
workflows/queue_artifacts/AOS-2026-0164_work_codex_PERMISSION_MODE_SCOPED_LOCAL_TASK_APP.md
workflows/queue_artifacts/AOS-2026-0165_Recover_AOS-2026-0161_dashboard_and_Telegram_UX.md
```

4. `feat(dashboard): add lane workspace and explicit review UX` — 38 paths:

```text
dashboard/frontend/src/App.jsx
dashboard/frontend/src/api.js
dashboard/frontend/src/components/DashboardKit.jsx
dashboard/frontend/src/components/HumanReviewCard.jsx
dashboard/frontend/src/laneWorkspaceActions.js
dashboard/frontend/src/laneWorkspaceState.js
dashboard/frontend/src/queueState.js
dashboard/frontend/src/reviewCardState.js
dashboard/frontend/src/shellState.js
dashboard/frontend/src/views/DashboardV1.jsx
dashboard/frontend/src/views/LaneWorkspace.jsx
dashboard/frontend/src/views/Queue.jsx
dashboard/frontend/tests/laneWorkspaceActions.test.js
dashboard/frontend/tests/laneWorkspaceComponent.test.js
dashboard/frontend/tests/laneWorkspaceState.test.js
dashboard/frontend/tests/queueState.test.js
dashboard/frontend/tests/reviewCard.test.js
dashboard/frontend/tests/shellState.test.js
scripts/aos_0164_browser_proof.py
scripts/aos_0168_contract_repair_browser_proof.py
scripts/aos_0173_browser_proof.py
workflows/queue_artifacts/AOS-2026-0164-browser-proof/browser-proof.json
workflows/queue_artifacts/AOS-2026-0164-browser-proof/dashboard-1440x1000.png
workflows/queue_artifacts/AOS-2026-0168_contract_repair_browser_proof/browser-proof.json
workflows/queue_artifacts/AOS-2026-0168_contract_repair_browser_proof/review-card-actual-receipt.png
workflows/queue_artifacts/AOS-2026-0168_contract_repair_browser_proof/review-card-after-explicit-approve.png
workflows/queue_artifacts/AOS-2026-0168_work_hermes_PERMISSION_MODE_SCOPED_LOCAL_TASK_AP.md
workflows/queue_artifacts/AOS-2026-0170_lane_route_receipt.md
workflows/queue_artifacts/AOS-2026-0171_lane_workspace_receipt.md
workflows/queue_artifacts/AOS-2026-0172_correction_1.md
workflows/queue_artifacts/AOS-2026-0172_lane_actions_receipt.md
workflows/queue_artifacts/AOS-2026-0173_browser_proof/browser-proof.json
workflows/queue_artifacts/AOS-2026-0173_browser_proof/desktop-cockpit-1440x1000.png
workflows/queue_artifacts/AOS-2026-0173_browser_proof/desktop-lane-blocked-1440x1000.png
workflows/queue_artifacts/AOS-2026-0173_browser_proof/desktop-lane-needs-me-1440x1000.png
workflows/queue_artifacts/AOS-2026-0173_browser_proof/desktop-lane-ready-1440x1000.png
workflows/queue_artifacts/AOS-2026-0173_browser_proof/narrow-lane-needs-me-390x844.png
workflows/queue_artifacts/AOS-2026-0173_validation_browser_receipt.md
```

5. `fix(memory): classify global technical context` — 2 paths:

```text
tests/test_business_brain_context.py
tools/business_brain_context.py
```

## Validation

- Post-repair protected focus: 69 Telegram/queue tests and four exact routing
  backend tests passed.
- System-Python focused acceptance: 150 tests passed across queue lifecycle,
  route/profile resolution, Linux paths, orchestration/title notifications,
  launcher cleanup/status, workflow shell, Codex policy, Telegram formatting,
  capture, protected schemas, and prospecting route contracts.
- Canonical backend virtual environment: 193 tests passed across the complete
  dashboard backend and Codex retained-context repair suite. This includes
  inline status, why/receipt reads, bounded Telegram approval behavior,
  `/work codex`, `/work claude`, `/work hermes`, natural-language workbench
  delegation, native-Hermes fallback, and three-attempt Hermes review.
- Frontend: 39 tests passed; Vite production build completed (1,652 modules).
- Protected JSON structural contracts: PASS. Fourteen command routes have 14
  unique IDs, 14 unique workflows, zero exact duplicate patterns, zero
  earlier-route shadow conflicts, and route labels equal live backend labels.
  Lane/model coverage has no unexplained gap; only Codex and Claude are
  intentionally model-only workbench routes.
- `git diff --check`: PASS.
- Python compilation: PASS for all 23 changed/new Python files, including the
  authorized Telegram bridge.
- Shell syntax: PASS for both changed shell scripts.
- JSON parsing and schema-shape validation: PASS for all three authorized route
  JSON files; relevant queue/run/token schemas and current queue parse tests
  passed. The authorized Python file compiled.
- Browser evidence: the newest review-card proof shows substantive receipt,
  consolidated artifact, non-closing note save, and explicit approve/change/
  block actions; lane/cockpit evidence was also visually checked.
- Read-only live checks: backend and frontend ready; exactly one canonical
  external runner recognized; backend health `ok`; composite WSL status
  healthy; bridge running; queue healthy with 173 parse-valid items and zero
  invalid records; runner on-demand idle; Codex, Hermes, and local-agent route
  ready; capture status healthy at the metadata-only boundary.
- Ordinary permitted status activity left the Git-status fingerprint unchanged
  and did not recreate root `.vite/`.
- Telegram validation was local/mocked only. No live message, document, model,
  connector, approval, or queue mutation was performed.

## Final intentional dirty state

Final state: 89 visible paths — 46 tracked modifications and 43 untracked
files. Categories are A 51, D 1, G 33, and I 4.
The 23 initial E/H runtime paths are preserved but ignored; the two F cache
files are removed; the one deleted G proof is restored clean. There are no B,
C, or J paths.

The visible set is irreducible without committing accepted source/proof work.
The manifest has zero unknown current paths, and the five groups cover all 89
visible paths once. No file is staged.

## Protected boundary

- Only the four explicitly authorized protected source/config paths were
  opened and, where necessary, repaired.
- Immutable AOS-2026-0071, AOS-2026-0073, AOS-2026-0074, and AOS-2026-0075
  were not modified; dirty-path metadata contained no matching item.
- No `.env`, allowlist, secret, account content, message, chat ID, credential,
  token, authentication state, North Shore content, legacy runtime, global or
  default Hermes profile, or other protected interior was inspected or changed.

## Blocker and next action

Blocker: none. Next action: Liam may authorize five exact path-limited commits
in the listed order. The current authorization ends before staging or commit;
the first new approval boundary is staging only the eight group-1 paths and
committing them with `chore(runtime): stabilize generated-state boundaries`.
Push remains a separate explicit approval boundary.

## Token usage

Token usage: unavailable from current CLI output.
