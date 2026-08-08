# Revenue Gate — Loretta Davis / Evan Thompson

> Revisit: before Step 4 or if AOS-2026-0174, AOS-2026-0175, or AOS-2026-0482 changes. · Last touched: 2026-08-04.

Verdict: **PASS** for Steps 0–3 and the Revenue Gate. Do not infer approval for outreach.

## Ten required outcomes

1. **Restarted Hermes remembers both people — PASS.** The backend was restarted four times; the final PID is 11458. A same-key prompt that named neither person returned Loretta Davis/Talent Harbour and Evan Thompson/Highway 99 with AOS-0174/0175 and 2026-07-23 activity. Queue delta: 0.
2. **Canonical notes and recent activity load automatically — PASS.** The final native manifest `hermes-20260804_031105_61e369-...json` resolved the indirect phrase “the two prospects we discussed” through the latest durable turn, then selected both canonical prospect notes, `queue/work_items.jsonl#AOS-2026-0174`, `#AOS-2026-0175`, and all four matching notification receipts. It had 111,285 bytes / 23,702 estimated tokens and no truncation warning.
3. **Staleness and owed follow-up identified — PASS.** Hermes found twelve days of stale internal review as of 2026-08-04 and distinguished owed internal checks from prospect follow-up: role/relevance and prior-contact/platform checks for Loretta; draft/CASL/role and prior-contact checks for Evan; no prospect follow-up owed because nothing was sent.
4. **Knowledge states separated — PASS.** The live response separated verified facts, interpretations, hypotheses, and uncertainties. Evan's ICP-A MSP/technology-services value is canonical/operator-corrected; older ICP-B/partner-adjacent wording remains an unreconciled interpretation.
5. **Multi-turn discussion creates no queue item — PASS.** Initial discussion, restart recall, correction discussion, execution-definition discussion, activity read, and both final restart reads each reported `queue_delta: 0`. One deterministic clarification response also created none.
6. **Correction reaches durable Brain and vault Git — PASS.** The `remember_brain_knowledge` tool updated only Evan's canonical note with provenance and `knowledge_state: operator_correction`. Vault commit `f7c4044e2a443bbfb32c792d96e04459d2fd6abc` contains exactly that path. Post-turn journaling then committed the sticky session separately.
7. **Proceed creates exactly the right work — PASS.** The exact message `Proceed` reported `created:true`, `queue_delta:1`, and produced only AOS-2026-0482 for the defined combined local no-send package. The immediately captured queue count moved 473 → 474. Historical AOS-0174/0175 were unchanged. AOS-0483 was independently created twenty seconds later by the already-scheduled bounded Gmail capture (`source: capture/gmail-live-read-only-digest`), not by Proceed.
8. **Worker gets substantive context — PASS.** `context/packs/AOS-2026-0482_pack.md` is 44,570 bytes / 576 lines, carries `TTROS_ASSEMBLED_CONTEXT_V1`, both prospect notes, AOS-0174/0175, current queue/outcome evidence, priorities, executive view, open loops, workflows, boundaries, and provenance. It declares a fresh task-scoped session and `Hermes transcript included wholesale: no`.
9. **Useful output produced — PASS.** Revenue completed one attempt and produced `workflows/queue_artifacts/AOS-2026-0482_Create_one_combined_local_no-send_follow-up_pack.md` (13,606 bytes / 208 lines; SHA-256 `411b0a9838b00f89db86fbdd04a90cb3eb554d4da341eb8bff11d9865276a1c5`). It contains separate account recaps, stale checks, call plans, draft-only wording, and per-channel approval checklists.
10. **No external mutation — PASS.** The artifact and work item prohibit send/connect/message/post/book/CRM/Gmail/Calendar/Drive mutation. The synthetic Telegram escalation was blocked as `recipient_not_allowlisted:revenue-gate-20260804`; notification effects were logged locally only. Gmail remains draft-only. No email, LinkedIn, calendar, CRM, Drive, publish, booking, or other external action occurred.

## One Brain and sticky-session evidence

- Migration commit: `6ce8e608094dfc960277de001d53fd723f9f7cd8`, exact eight meaning-based paths, author `Hermes <hermes@local.ttros>`.
- Correction commit: `f7c4044e2a443bbfb32c792d96e04459d2fd6abc`, exact Evan note only.
- Sticky session: `sessions/2026-08-04_hermes-cli_2b590acc5677.md`; session-key digest `ffd8051c6cbc0c586b55f692`. Every completed live turn produced its own Hermes-authored vault commit.
- All six AOS configs report native `memory_enabled:false` and `user_profile_enabled:false`, the assembler pre/post hooks, and the Brain MCP. No native profile memory files exist.
- Seven migrated/current Brain files passed the adapter Markdown validator; vault `git fsck --full` returned clean; only the same pre-existing human/untracked changes remain dirty.

## Enforcement and failure recovery

- Dashboard Codex, Claude, and Hermes runners call `require_assembled_context`; raw strings raise before a model call.
- Queue workers build the context pack before a fresh lane session.
- Native Hermes `agent/turn_context.py` blocks every AOS profile if the pre-LLM hook did not provide `TTROS_ASSEMBLED_CONTEXT_V1`, and it exempts validated TTROS context from hook-output spilling.
- First real operator calls intentionally proved fail-closed (`mandatory assembled context is absent`). The operator oneshot was found to bypass CLI hook registration; hook registration was added, and the same live call then succeeded.
- The first correction tool attempt exposed that the oneshot passed only the operator toolset. It was repaired to require and pass both exact toolsets; the retry produced the vault correction commit.
- Atomic-writer tests prove invalid candidates never replace source, stale expected hashes preserve concurrent edits, and managed updates preserve human content/frontmatter while committing only the target.

## Regression and protected-path evidence

- Consolidated affected Python suite: 499 tests, zero observed failures/errors. The final focused One Brain suite, including sticky-anaphora source reselection, is 8/8. Telegram conversational routing: 15/15.
- Frontend: 52/52 tests; production Vite build passed (only the existing >500 kB chunk advisory).
- Bounded capture fixture: PASS; replay added zero raw records, no live provider/model calls, zero external actions, scoped Brain retrieval only, unresolved content unopened. Its stale assertion was repaired to accept all three existing Needs Me states (`human_review`, `needs_input`, `blocked`).
- Graphify rebuilt after the Evan correction: success receipt `20260804T015346697513Z-build-success.json`, 34 sources, zero model tokens, bodies excluded. Status is `fresh`/trusted; the global Loretta/Evan query returned exactly their two canonical notes.
- Protected item content hashes match the pre-Proceed baseline exactly: AOS-0071 `44d1d9dd…`, 0073 `b734109d…`, 0074 `4325bbc…`, 0075 `3b88d3be…`, 0174 `2df5abf…`, 0175 `e92ff399…`.
- `git diff --check`, Python compilation, shell syntax, runtime health, vault validation, and vault Git fsck passed. Agentic OS HEAD remains the 2026-08-01 commit `1ec13b608fdcd66ed62052d28fe3b908d1ddfc97`; no Agentic OS commit or push occurred.
- No files under `connectors/telegram_bridge/`, no routing JSON, no credentials/authentication material, and no North Shore files were changed.

## Gate disposition

Steps 0–3 are green. The next authorized architecture stage is Step 4; Steps 4–8 were deliberately not implemented in this session.
