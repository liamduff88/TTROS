# AOS-2026-0164 Codex token-usage investigation

> Revisit: if Codex session logging, queue prompt construction, or token-ledger reconciliation changes. · Created: 2026-07-18.

PASS

Scope: read-only investigation of AOS-2026-0164. The only repository change made by this investigation is this report.

## 1. Initial prompt size and construction

### Launch path

The exact launch chain was:

1. The asynchronous runner selected the tagged work item and started the detached queue executor (`tools/aos-orchestration-runner.py:148-180`, `tools/aos-orchestration-runner.py:198-214`).
2. The executor imported the dashboard backend and called `run_queue_item(item_id)` (`tools/aos-orchestration-runner.py:184-195`).
3. `run_queue_item` claimed the item, constructed attempt 1 with `_queue_actual_run_prompt`, and called `_queue_run_worker` (`dashboard/backend/main.py:7432-7487`).
4. The Codex branch called `_run_codex_local` directly (`dashboard/backend/main.py:6908-6923`).
5. `_run_codex_local` launched the command produced by `build_exec_command` and wrote `prompt.encode("utf-8")` once to the child's stdin (`dashboard/backend/main.py:823-890`). The command contract was `/home/liam/.local/npm/bin/codex --sandbox danger-full-access --ask-for-approval never -C /home/liam/agentic-os-live exec --skip-git-repo-check --json --color never -` (`tools/aos_codex_policy.py:82-90`).

The prompt construction functions are `_queue_render_prompt` (`dashboard/backend/main.py:6708-6748`) and `_queue_actual_run_prompt` (`dashboard/backend/main.py:6859-6886`), using `queue/templates/codex_task.prompt.md:1-72` and `_queue_required_receipt_shape` (`dashboard/backend/main.py:6769-6796`).

### Persisted source and exact bytes

- Persisted task source: `queue/work_items.jsonl:164`, field `context`.
- Stored task-body size: **2,398 UTF-8 bytes**.
- Stored task-body SHA-256: `53133f8cacb1d2ee842461c3228ed21b533ba47af837a8da433786309d1179c6`.
- Persisted runner prompt: **none**. The Codex branch bypasses `_write_agent_prompt_file`; that helper is used by the Claude/Hermes branches (`dashboard/backend/main.py:1257-1318`, `dashboard/backend/main.py:6924-6968`). The two files currently under `queue/run_prompts/` belong to other work items; `aos_prompt_k_s3ki7j.md` is the 6,068-byte AOS-2026-0161 prompt, not the 0164 Codex launch prompt.
- Authoritative launch copy: the Codex session's sole `user_message` record, `/home/liam/.codex/sessions/2026/07/18/rollout-2026-07-18T01-35-11-019f72a6-076e-7f61-83b8-81e69438b77b.jsonl:10`.
- Exact initial stdin/launch-prompt size: **5,031 UTF-8 bytes**.
- Exact launch-prompt SHA-256: `c644ecc3c7d955eb547c2209ce160518714528039704f3683af3cda4cd1cba72`.

The current construction function reconstructs 5,155 bytes because the same run added a 124-byte `Summary for operator` row to the receipt shape. The historical session record is therefore the authoritative launch-time value: 5,031 bytes.

The complete 2,398-byte task body was inline, not referenced by path, and appeared **exactly once** in the launch prompt. The 58-byte title appeared three times (work scope, work-item title, and title field), but that is not duplication of the task body.

## 2. Embedded context

The following byte counts are exact section-boundary counts from the 5,031-byte session `user_message`; headings and separating whitespace are included:

| Initial stdin block | Bytes | Evidence/meaning |
|---|---:|---|
| Codex task header plus permission/access/runtime preamble | 847 | `queue/templates/codex_task.prompt.md:1-13` |
| Work scope | 75 | The short title, not the full task |
| Work-item identity | 124 | ID, owner, and title |
| AOS-2026-0164 context | 2,412 | Heading plus the exact 2,398-byte stored task body |
| Source references | 52 | One repository-root reference |
| Allowed actions | 60 | Three list entries |
| Stop conditions | 91 | Three list entries |
| Definition of done | 156 | One 131-byte stored value plus heading/spacing |
| Validation instruction | 99 | Static local-validation sentence |
| Template closeout | 625 | Static Codex closeout contract |
| Current-attempt marker | 22 | `Current attempt: 1/2` |
| Output/receipt shape | 239 | Launch-time receipt template |
| Required artifact path and instruction | 229 | Output path plus one static sentence |
| **Total** | **5,031** | Exact initial stdin |

AOS-2026-0161 and AOS-2026-0162 were mentioned only inside the single 0164 context block. There was no separately embedded 0161/0162 record or prompt. The two context lines containing `AOS-2026-0161` occupied 232 bytes including newlines; the one line containing `AOS-2026-0162` occupied 197 bytes and overlaps one of those lines.

Suspected blocks **not embedded in the initial stdin**:

- queue history;
- receipt history or prior receipts;
- token, run, or goal ledgers;
- orchestration-event history;
- previous prompts, including the 6,068-byte AOS-2026-0161 run prompt;
- source files, diffs, test logs, or browser images;
- the Linux/manual launch-command sections (they were stripped by `_queue_actual_run_prompt` before stdin);
- a second copy or path reference to the full 0164 task body.

Separately from Agentic OS stdin, Codex's own session metadata recorded 17,766 text bytes of CLI base instructions and an initial 2,578-byte serialized world-state object (`...b77b.jsonl:1-2`). These were Codex runtime context, not orchestration duplication, and did not contain another recorded `user_message`. The session contains exactly one `user_message` event.

## 3. Invocation and ledger accounting

### Process and retry evidence

- Codex process invocation count: **1**.
- Codex session/invocation ID: `019f72a6-076e-7f61-83b8-81e69438b77b` (`...b77b.jsonl:1`). A separate supervisor/process invocation ID was not captured.
- Route-diagnostic rows for AOS-2026-0164: **1**, at `logs/local_agent_route.jsonl:13`.
- Route result: return code 0, one 2,462.651-second process, started from `/home/liam/agentic-os-live`, Codex CLI 0.144.1, `danger-full-access`, approval policy `never` (`logs/local_agent_route.jsonl:13`; session metadata at `...b77b.jsonl:1`).
- Queue worker attempts: **1** (`queue/receipts/AOS-2026-0164.md:18`).
- Process retries: **0**. No second route row, session file, worker attempt, or retry event exists for 0164.
- Recorded retry reasons: **none**. The route stderr tail contains one failed `write_stdin` tool call and two failed patch applications; those were in-session tool errors, not Codex-process retries (`logs/local_agent_route.jsonl:13`).

### Filtered ledger rows

`queue/run_ledger.jsonl` contains **one** 0164 row (`queue/run_ledger.jsonl:67`), representing the final done transition.

`queue/token_ledger.jsonl` contains **three** 0164 rows:

| Line | Event/effect | Input | Output | Interpretation |
|---:|---|---:|---:|---|
| 261 | `notification_logged`, originating channel | 0 | 0 | Deterministic notification side effect; explicitly says `no agent invocation` |
| 262 | `notification_logged`, Needs Me rail | 0 | 0 | A different notification side effect; explicitly says `no agent invocation` |
| 266 | final `done` effect | 0 | 0 | Usage unavailable: orchestrator, subagent, and workbench session totals |

The two notification rows are written once per channel by `append_no_agent_token_line` (`tools/aos_orchestration.py:376-405`, invoked at `tools/aos_orchestration.py:825-859`). The done row is written by `finalize_done` (`tools/aos-queue.py:960-1001`, `tools/aos-queue.py:1040-1065`). They are separate effects, not separate Codex invocations or duplicate exact-usage rows. Their `no agent invocation` labels are semantically incomplete for this work item, but their numeric values are zero and do not inflate the Codex total.

The exact cumulative Codex usage appears once in the route diagnostic (`logs/local_agent_route.jsonl:13`) and is echoed in the worker receipt (`queue/receipts/AOS-2026-0164.md:51,73`). It was **not** reconciled into an exact token-ledger row. The direct dashboard route parses and returns usage (`dashboard/backend/main.py:766-809`, `dashboard/backend/main.py:934-978`) but does not call `reconcile_codex_usage`, whose keyed ledger reconciliation lives at `tools/aos-queue.py:766-881`.

Accounting verdict: **no token-ledger double-counting** and no additive double-counting of the reported summary. The same cumulative terminal value is copied into two evidence locations but is not summed. No corrected total is required. The exact arithmetic is:

- input tokens, including cached: **30,931,782**;
- cached input: **30,381,312**;
- fresh input: **550,470** (`30,931,782 - 30,381,312`);
- output: **64,306**, of which reasoning is **22,115**; reasoning is not added again;
- input-plus-output total: **30,996,088**.

## 4. Model-turn and retained-context growth

The session file is 2,583,058 bytes, 1,018 JSONL records, SHA-256 `edbd828104a050e6f0b92afa4f20746f35b330e1c9b3f5afc12de9a0e247db30`.

An explicit model-turn/API-call counter is **not captured by current logging**. The exact recorded proxy is 237 `token_count` events containing 235 distinct cumulative usage vectors. Two events are non-additive repeats: lines 463-464 repeat the same cumulative vector, and line 584 records zero last-turn usage at compaction. This diagnostic repetition does not alter the final cumulative value.

The usage sequence directly proves cumulative session accounting:

- First recorded usage: cumulative/last input 14,608, cached 9,984 (`...b77b.jsonl:16`).
- Before compaction: last input reached 244,732 while cumulative input was 24,126,135 (`...b77b.jsonl:580`).
- One context compaction occurred (`...b77b.jsonl:581-585`), with a 46,927-byte serialized replacement history.
- First usage after compaction: last input 19,231, cached 14,080 (`...b77b.jsonl:591`).
- Final usage: cumulative input 30,931,782/cached 30,381,312, while the final individual usage event was input 116,103/cached 114,432 (`...b77b.jsonl:1017`).

Thus 30,381,312 cached tokens are cumulative repeated processing of the retained session context across many usage-bearing turns, not 30.4 million unique tokens or a 30.4-million-token prompt sent once. Cached input was 98.2204% of cumulative input.

The session retained **234 tool-output records totaling 1,511,725 serialized bytes**: 216 custom-tool outputs totaling 1,481,623 bytes and 18 wait outputs totaling 30,102 bytes. The largest identifiable outputs were:

| Session lines | Bytes | Retained output |
|---|---:|---|
| 677-678 | 237,503 | The same dashboard PNG viewed at `high` detail |
| 664-665 | 177,603 | That dashboard PNG viewed at `original` detail |
| 184-185 | 42,408 | Large selected ranges from `dashboard/backend/test_composio_hermes.py` |
| 74-75 | 42,317 | A multi-file `git diff`; output was explicitly truncated from a larger result |
| multiple early records | about 41,000-42,000 each | Large `rg` and `sed` source/test excerpts |

The two views of one image alone retained 415,106 serialized bytes. Exact token contribution per output is **not captured by current logging**.

Content that entered later session history, but was not in the initial prompt:

- full AOS-2026-0161 and AOS-2026-0162 receipts (1,243 and 3,436 bytes) and the full 6,068-byte 0161 run prompt, returned together in a 12,444-byte tool output;
- selected AOS-2026-0161 through 0164 work-item records in an 18,414-byte tool output;
- test/build command output, including a 4,942-byte frontend test/build result and smaller Python test outputs;
- a 42,317-byte truncated multi-file diff;
- many large source-file ranges and test-file ranges;
- browser-image payloads totaling at least 415,106 serialized bytes.

No complete queue JSONL dump, complete token/run ledger, or complete orchestration-event ledger is directly evidenced as having entered the session. Targeted records, searches, receipts, prompt content, diffs, test output, and source ranges did enter.

## 5. Root-cause verdict

**Confirmed primary cause:** the 30.4-million cached-input figure is the Codex CLI's cumulative cached-input total across a long, tool-heavy single session, not unique context sent once. The session shows one initial 5,031-byte user prompt, one Codex process, one user-message injection, cumulative usage growth across 237 token-count events/235 distinct cumulative usage states, and one context compaction.

**Confirmed contributing causes:** retained context grew through 234 tool outputs totaling 1,511,725 serialized bytes, including two copies/views of a large browser image, large source/test excerpts, a large truncated diff, receipts, a prior prompt, work-item records, and test/build output. This caused a large cached prefix to be processed repeatedly. One compaction reduced context and it then grew again.

**Ruled out:** a very large initial prompt; multiple copies of the full 0164 body in the launch prompt; repeated Agentic OS user-prompt injection; multiple/retried Codex processes; duplicate exact token-ledger rows; additive double-counting of the final cumulative summary; initial embedding of queue, receipt, ledger, previous-prompt, diff, source, test-log, or image history.

**Not recoverable from current logging:** an explicit API-call/model-turn count distinct from the exact token-count-event count; provider-side cache-key/cache-hit internals; exact token contribution of each retained tool output; a separate process invocation ID beyond the Codex session ID; and any history not present in the surviving session JSONL.

**One-paragraph verdict:** The reported number is a combination of cumulative repeated processing across model turns and retained-session growth, with no evidence of duplicated orchestration context or duplicate ledger accounting. AOS supplied one 5,031-byte stdin prompt containing one 2,398-byte task body. During the single 41-minute Codex invocation, tool results accumulated and the cached prefix was repeatedly reused; the CLI summed those per-turn inputs to 30,931,782, of which 30,381,312 were cached and exactly 550,470 were fresh. The route and receipt echoed that one cumulative result, while the token ledger failed to capture it and instead contains three zero/unavailable lifecycle rows.

## Validation and boundaries

- `git diff --check`: **PASS** (exit 0, no output).
- Final Git status comparison: the initial dirty worktree entries are unchanged, with this report as the only additional path.
- Implementation, queue items, receipts, ledgers, prompts, logs, and protected files modified by this investigation: **none**.
- Files changed by this investigation: `workflows/queue_artifacts/AOS-2026-0164_token_evidence.md` only.
- Protected areas were not directly inspected or modified: `workspaces/north_shore_sales_coach/`, `connectors/telegram_bridge/`, protected route/profile JSON files, secrets/authentication material, legacy paths, and Hermes global/default profile.
- AOS-2026-0161, AOS-2026-0162, and AOS-2026-0164 were treated as read-only evidence; no item was reopened, transitioned, redispatched, or mutated.
- AOS-2026-0071, AOS-2026-0073, AOS-2026-0074, and AOS-2026-0075 were not mutated.

## Closeout

PASS

Artifact:
- `workflows/queue_artifacts/AOS-2026-0164_token_evidence.md`

Evidence inspected:
- Filtered 0164 work-item, run-ledger, token-ledger, receipt, route-diagnostic, runner-code, prompt-template, and Codex-session records listed above.

Initial prompt bytes:
- 5,031 exact UTF-8 bytes.

Stored task bytes and copy count:
- 2,398 exact UTF-8 bytes; one full copy in initial stdin.

Codex invocation and retry count:
- One invocation; zero process retries; session ID `019f72a6-076e-7f61-83b8-81e69438b77b`.

Ledger row count and accounting verdict:
- Three token-ledger rows and one run-ledger row; no exact-usage duplicate and no double-counting.

Model-turn/context-growth evidence:
- API-call count: not captured by current logging. Exact proxy: 237 token-count events, 235 distinct cumulative usage states, one compaction, and 1,511,725 bytes of retained tool outputs.

Root-cause verdict:
- Cumulative cached processing of a retained and repeatedly reused single-session context, materially amplified by large tool outputs; not a large or duplicated initial AOS prompt and not duplicate ledger accounting.

Files changed:
- Investigation report only.

Protected areas:
- Not directly inspected or modified.

Blockers:
- None.

Next action:
- Investigation complete; repair scope can now be chosen from proven evidence.

Token usage for this direct investigation:
- fresh input: unavailable from current CLI output
- cached input: unavailable from current CLI output
- output: unavailable from current CLI output
- reasoning: unavailable from current CLI output
