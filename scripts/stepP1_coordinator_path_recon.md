# STEP P1 — Coordinator path recon: is `-p`/`--profile` broken?

> Read-only. Zero model calls made (declared max = 0; actual = 0). Zero changes made.
> Surface: this WSL Linux host, installed Hermes v0.21.1 at `/home/liam/.local/bin/hermes`
> (`/home/liam/.hermes/hermes-agent`, upstream `05d705dd`, local `b2aa855b`) — the same binary
> STEP U upgraded to and the same one T7/T8-BCD tested against. All commands below were parse-only
> or `--version`/`--help` (no prompt, no path to a model call) or read-only inspection.

## Verdict, plain English, first

**The coordinator is live and its `-p`/`--profile` invocation shape is NOT broken.** T7's and
T8-BCD's claim ("this build has no `-p`/`--profile` flag") is the wrong instrument. STEP U's
smoke test was right. `-p`/`--profile` is a real, working, pre-argparse mechanism in this exact
installed build — it is deliberately absent from `hermes --help` because it is stripped out of
`sys.argv` by `hermes_cli/main.py::_apply_profile_override()` *before* argparse ever runs. T7's own
failure was caused by a **different, genuinely-nonexistent flag it combined with `-p` in the same
test — `--max-turns`**, which does not exist on the top-level `hermes -z/--oneshot` shape at all
(only under `hermes chat`, which lacks `--usage-file`). Stripping `-p david` from T7's argv still
leaves `--max-turns 6` for argparse, and unconsumed `--max-turns 6` is exactly what produces T7's
quoted error, `argument command: invalid choice: '6'` — reproduced byte-for-byte below with the
real, installed argparse object, zero model calls. The coordinator script never uses
`--max-turns` (checked: not present anywhere in `tools/aos-hermes-coordinator.sh`), so it never
hits this defect.

**Separately, and unrelated to `-p`, there is a real live failure worth flagging**: today's
(2026-09-10 08:00:47 PDT) `aos-morning-brief.service` run failed (systemd exit code 1) with a
Hermes session that opened and closed in 0.064s with **zero messages** — the same
zero-message/near-instant signature also seen on both of `aos-orchestrator`'s two invocations since
2026-09-08. This is 3 failures out of 49 coordinator-path sessions across profiles since
2026-09-08 (46/47 david sessions completed normally with real turns). Exact stderr/traceback for
these three could **not** be recovered: `journalctl --user` in this session can only read the
live in-memory ring buffer (which mis-tags everything under `user@1002.service`/hostname
`VRS-GLOBAL`, not per-unit) — the persisted system journal at `/var/log/journal/<machine-id>/`
requires `systemd-journal` group membership this account does not have
(`journalctl` itself prints "some journal files were not opened due to insufficient
permissions"). This is a declared evidence gap, not glossed over. The timing of the david failure
(08:00 PDT today) is consistent with — but not proven caused by — the previously-reported
`hooks/context_assembler_hook.py` executable-bit outage (lost +x sometime before 2026-09-09
23:43 PDT per T4's transcript; the file is executable again now, but **uncommitted** — `git
status` shows it still `M`, and its current mtime, 2026-09-10 17:29 PDT, is *after* today's 08:00
failure, meaning the hook was still broken at the moment of that failure). The two
`aos-orchestrator` failures (2026-09-09 at 00:43 and 13:54 local) predate the reported 23:43
outage start and are **not** explained by it — their cause is unidentified with the evidence
available in this step.

**Which instrument was wrong:** T7/T8-BCD, for the reason above. STEP U's `smoke_test.py` (its
exact argv — `hermes -p david -z <prompt> --usage-file <path>`, no `--max-turns` — reproduced
below as PARSE OK against the real, installed parser) was correct, and its PONG/HANDOFF_OK
results are trustworthy evidence that the coordinator's invocation *shape* works.

---

## Q1 — Profile flag: argv, source, reconciliation

**Prediction (written before reading further evidence below):** `-p PROFILE` will resolve via a
pre-argparse mechanism not visible in `--help`, because a flag load-bearing enough to be the
coordinator's whole design ("Profile flag" is literally this step's opening question) surviving
undetected through a major version bump (v0.18 → v0.21.1) across STEP U's own pre/post smoke
tests is more consistent with "hidden from --help" than "silently removed, then silently still
worked twice." The other, falsifiable answer this check could have returned: `-p` truly gone,
STEP U's PONG a fluke of stale PATH/cache, T7/T8-BCD correct. Both outcomes were live going in.

**Source read** (`hermes_cli/_parser.py:9-14`):
```
# `--profile` / `-p` is consumed by ``main._apply_profile_override`` before argparse runs
# (it sets ``HERMES_HOME`` and strips itself from ``sys.argv``), so it isn't on the parser.
PRE_ARGPARSE_INHERITED_FLAGS: list[tuple[str, bool]] = [("--profile", True), ("-p", True)]
```
`hermes_cli/main.py::_apply_profile_override()` (line 495) runs at import time (line 546, before
argparse is ever built), scans `sys.argv[1:]` via `_scan_profile_flag()` (line 414) for
`-p`/`--profile`/`--profile=`, resolves the named profile's `HERMES_HOME` via
`hermes_cli.profiles.resolve_profile_env`, sets `os.environ["HERMES_HOME"]`, then **strips the
two consumed tokens from `sys.argv`** so argparse never sees them. `_PROFILE_NAME_RE =
r"^[a-z0-9][a-z0-9_-]{0,63}$"` accepts every coordinator profile name (`aos-orchestrator`,
`aos-revenue`, `aos-marketing`, `aos-delivery`, `aos-ops`, `david`).

**In-process parse (zero model calls — no `hermes` process was executed; only its own argparse
module and pre-argparse scanner functions were imported and called directly)**, using the
coordinator's exact non-provider argv:
```
argv = ['-p', 'aos-orchestrator', '--usage-file', '/tmp/x.json', '--oneshot', 'hello world']
_scan_profile_flag(argv) -> ('aos-orchestrator', 2, 0)   # cleanly consumed
remaining after strip:    ['--usage-file', '/tmp/x.json', '--oneshot', 'hello world']
build_top_level_parser().parse_known_args(remaining):
  -> PARSE OK. command=None extras=[] oneshot='hello world' usage_file='/tmp/x.json'
```
Same result for the provider/model branch (`--provider ... --model ... --usage-file ...
--oneshot ...`) and for STEP U's exact smoke-test argv (`-z <prompt> --usage-file <path>` after
`-p david` is stripped). **All three parse cleanly against the real, installed
`build_top_level_parser()` object.**

**T7's failing argv, same technique:**
```
argv = ['-p', 'david', '-z', 'prompt text', '--max-turns', '6']
_scan_profile_flag(argv) -> ('david', 2, 0)
remaining after strip: ['-z', 'prompt text', '--max-turns', '6']
'--max-turns' in top_level_value_flag_sets() -> False   # confirmed not a top-level flag
build_top_level_parser().parse_known_args(remaining):
  -> hermes: error: argument command: invalid choice: '6' (choose from 'chat')
     SystemExit code=2
```
This is the **exact error text T7 quoted**, reproduced with zero model calls, and it reproduces
identically whether or not `-p david` is present — because `-p` was never the problem;
`--max-turns` on the top-level oneshot parser is. `hermes --help` vs `hermes chat --help`
confirms `--max-turns` exists only under `chat`, which has no `--usage-file`; T7's own report
reaches this same conclusion once it drops `-p` and still fails identically — the report already
contains its own refutation of the "no `-p` flag" framing but states the framing anyway.

**Answer:** the flag exists and works. Proven in-process from source with zero model calls, not
inferred.

## Q2 — Callers

Grepped the full repo (protected paths per header rule 1 excluded), `~/.config/systemd/user/`,
and `crontab -l`.

- **No crontab** (`crontab -l` → "no crontab for liam").
- **No systemd unit references `aos-hermes-coordinator.sh` by name.** The nine user units present
  (`aos-backend`, `aos-bridge`, `aos-cloudflared`, `aos-frontend`, `aos-gmail-capture` (+timer),
  `aos-morning-brief` (+timer), `aos-nightly-hygiene` (+timer), `aos-north-shore`, `aos-runner`)
  invoke Python entry points, not the shell script directly.
- **The one live code caller is `dashboard/backend/main.py`** (the FastAPI backend process run by
  `aos-backend.service`, `WantedBy=default.target`, confirmed active). It defines
  `HERMES_COORDINATOR = BASE_DIR / "tools" / "aos-hermes-coordinator.sh"` (line 758) and shells
  out to it via `_run_wsl_supervised()` (a plain `bash -lc` subprocess despite the "WSL" naming —
  confirmed by reading the function; no actual WSL/cross-OS boundary crossed on this host) from
  two call sites: `_run_hermes_message()` (line 3927, invoked from `_queue_run_worker()` at line
  8999 and from `_execute_named_profile_consultation()` at line 4272). It always passes
  `--profile <name>` (long form) into the `.sh`, which the `.sh` itself then re-emits as `hermes
  -p "$profile"` (short form) to the real binary — both forms are accepted, per Q1.
- `tools/aos-orchestration-runner.py` (run by the separate, also-live `aos-runner.service`) was
  checked and does **not** call the coordinator directly or import `dashboard.backend.main`; it
  imports only `aos_orchestration`/`aos_paths`/`aos_queue_storage`, none of which reference the
  coordinator. It is a queue-watcher, not a direct caller.
- `tools/aos_morning_brief.py` (run by `aos-morning-brief.service`/`.timer`) also does not call
  the coordinator directly — it calls the backend over `urllib.request` (an HTTP endpoint), which
  is what actually reaches `_run_hermes_message` → the coordinator.
- Every other repo hit (`tests/test_aos_executive_brief.py`, `tools/verify_step6.py`, various
  `queue/receipts/*.md`, `scripts/stepT*.md`, `proofs/**`, `decisions/DECISIONS.md`) is either a
  test/verification script asserting the coordinator's *existence* or a historical prose report
  mentioning it — not a live runtime caller.
- Profiles the live caller (`dashboard/backend/main.py`) can address, per its own profile
  whitelist mirrored in the `.sh`: `aos-orchestrator` (default), `aos-revenue`, `aos-marketing`,
  `aos-delivery`, `aos-ops`, `david`.

## Q3 — Actual use since 2026-09-08

`journalctl --user` in this session cannot see per-unit history (see Verdict section) — it is not
a usable surface for this question here, so evidence below comes from `state.db` (read-only,
per-profile, epoch-based query) and from the queue's own receipt/log files, both explicitly
authorized read-only surfaces.

| Profile | Sessions since 2026-09-08 | Zero-message / near-instant-close (failure signature) |
|---|---|---|
| david | 47 | 1 (2026-09-10 08:00:45 local, 0.064s, 0 messages) |
| aos-orchestrator | 2 | 2 (2026-09-09 00:43:50 and 13:54:49 local, both < 0.3s, 0 messages) |
| aos-revenue / aos-marketing / aos-delivery / aos-ops | 0 each | n/a |

- **Last unambiguous success**: `queue/receipts/david-morning-brief-2026-09-09.md` — PASS, `api_calls: 1`,
  `provider: openai-codex`, `model: gpt-5.5`, sent via email + Telegram, at 2026-09-09T16:46:26Z
  (09:46 PDT). This ran through the exact coordinator/`-p` shape proven working in Q1.
- **Last failure**: today, `aos-morning-brief.service` — `systemctl --user status` shows `Active:
  failed (Result: exit-code)` at 2026-09-10 08:00:47 PDT, `status=1/FAILURE`. No entry was written
  to `logs/david_morning_brief_delivery.jsonl` for 2026-09-10 (log stops at 09-09), meaning the
  failure happened **before** the delivery/send stage — consistent with, but not proof of, a
  failure during the Hermes call itself. The matching `state.db` session
  (`20260910_080045_c17556`) opened and closed in 0.064s with `message_count: 0` — no LLM turn
  ever completed, argparse must have already succeeded (a session row was created at all) so this
  is not an argv-rejection akin to T7's, it is a failure inside Hermes's own startup/first-turn
  path.
- **Exact error text: unavailable.** `journalctl --user -u aos-morning-brief.service` and
  `journalctl --user _PID=108209` both return "-- No entries --"; the broader `journalctl --user`
  stream only carries `aos-orchestration-runner.py`'s own dispatch-loop JSON (tagged
  `user@1002.service`/host `VRS-GLOBAL`, not the failing unit), and `journalctl` itself warns
  "some journal files were not opened due to insufficient permissions" — this account lacks
  `systemd-journal` group membership needed to read `/var/log/journal/<machine-id>/`. Escalating
  that (sudo, group change) was judged outside this step's read-only authorization and was not
  attempted.
- **Distinguishing the hook +x outage from a `-p` failure**: `hooks/context_assembler_hook.py`
  is `-rwxr-xr-x` now (checked: `stat` shows mode 0755), but `git status` shows it `M`
  (uncommitted) and its mtime is 2026-09-10 17:29:28 PDT — **after** today's 08:00:47 failure.
  `stepT4_post_t3_closeout.transcript.txt:92` captured the file at `-rw-r--r--` (0644, no
  executable bit) with mtime `Sep 9 23:43`, matching the outage window this step's prompt cites.
  So at the moment of today's 08:00 failure the hook was still broken; the chmod (and an apparent
  content edit — file grew 11160→12335 bytes) happened only later the same day, and is not yet
  committed. This is consistent with the hook outage explaining today's david failure. It does
  **not** explain the two `aos-orchestrator` failures on 2026-09-09 at 00:43 and 13:54 local —
  both predate the reported 23:43 PDT outage start by hours. Their cause is **not established**
  by evidence available in this step. None of the three failures shows any signature of the `-p`
  defect T7/T8-BCD alleged (that defect, per Q1, is not real for this argv shape in the first
  place, and would in any case fail at argparse before a session row could ever be created —
  these three sessions all got past that point).

## Q4 — Only if 1–3 show a live, failing path

They do (the zero-message pattern above), but it is not the `-p`/`--profile` path — that path is
proven sound in Q1. So there is nothing to "repair" on the `-p` question, and no plan is written
against it (writing one would be repairing something that is not broken, which this step's own
framing warns against).

For the actual zero-message failures: `queue/work_items.jsonl` (790 items total) currently shows
only **4** items in a `blocked`/`pending`/`queued`/`in_progress` state
(`AOS-2026-0020`, `AOS-2026-0485`, `AOS-2026-0521`, `AOS-2026-0522`), and all four were last
updated between 2026-07-06 and 2026-08-13 — **before** STEP U's upgrade and unrelated to it (they
read as held for other reasons: an explicit no-send scope hold and an operator-contract drafting
task, not a Hermes-invocation failure). **No queued item is currently stuck on the coordinator
path as a result of anything found in this step.** A "repair" would therefore release nothing
today; the three zero-message sessions were retried automatically the next day (david) or not
retried at all yet (aos-orchestrator, no session since 09-09), not stuck behind a lock.

Recommended next step (not authorized to apply here): get read access to the persisted systemd
journal (join `systemd-journal` group, or have Liam run `journalctl` and hand over output) to
capture the exact stderr for a reproduction of the zero-message failure, since three occurrences
with identical signature and no visible cause is itself a finding worth a dedicated, narrowly
scoped follow-up step — separate from, and not blocking, the `-p`/`--profile` question this step
was asked to settle.

## Q5 — max_iterations / --max-turns, recorded only

- `hermes --help` (top-level, the shape the coordinator uses) has **no `--max-turns`.**
  `hermes chat --help` has it (`--max-turns N`, "default: 500, or agent.max_turns in config"), but
  `chat` has no `--usage-file`, and the coordinator never invokes `chat`. **`--max-turns` cannot
  be passed on the coordinator's invocation shape.**
- Resolved `max_iterations` is therefore whatever each profile's `config.yaml` declares:
  `aos-orchestrator` → `agent.max_turns: 150`; `david` → `agent.max_turns: 150`; `aos-revenue`,
  `aos-marketing`, `aos-delivery`, `aos-ops` → no `max_turns` key present, so each falls back to
  Hermes's own built-in default of **500**.

---

## Proposed wording for `00` (no existing bullet found to replace)

Grepped both `00_TTROS_CURRENT_STATE_v2026-09-08_rev7.md` and
`02_TTROS_ACTIVE_TASK_2026-09-08_rev7.md` for `CONTESTED`, `-p/--profile`, and `--profile`: **no
hits in either file.** Both mirrors' SHA-256 match `SOURCE.sha256` (no mirror divergence). The
claim this step was asked to settle ("no `-p`/`--profile` flag exists on this build") currently
lives only in `scripts/stepT8BCD_live_cap_and_bounded_passage.md` (item 5) and
`scripts/stepT7_test_isolation_and_bounded_retrieval.md` — it was never promoted into `00` as a
bullet. There is therefore nothing to replace; the proposal below is for a bullet to **add**, so
the wrong claim does not get copied into `00` later from those step reports:

> **`-p`/`--profile` on the installed Hermes CLI (v0.21.1) works and is not the coordinator's
> defect.** It is a pre-argparse mechanism (`hermes_cli/main.py::_apply_profile_override`) that
> sets `HERMES_HOME` and strips itself from argv before argparse runs, which is why it is absent
> from `hermes --help` — that absence is by design, not evidence of removal. T7/T8-BCD's finding
> ("no `-p`/`--profile` flag exists") was an instrument error: their test combined `-p` with
> `--max-turns`, a flag that genuinely does not exist on the top-level `-z`/`--oneshot` shape
> (only under `hermes chat`, which lacks `--usage-file`); the resulting argparse failure
> (`invalid choice: '6'`) was `--max-turns`'s fault, misattributed to `-p`. `tools/aos-hermes-
> coordinator.sh` never passes `--max-turns` and its exact invocation shape parses and runs
> correctly (STEP U's `pre_smoke.json`/`post_smoke.json`, and `queue/receipts/david-morning-
> brief-2026-09-09.md`, are the trustworthy evidence; T7/T8-BCD's contrary claim should not be
> treated as authoritative). Proven 2026-09-10, STEP P1 (`scripts/stepP1_coordinator_path_recon.md`).

## What this licenses, and what it does not

**Licenses:**
- Treating the coordinator's `-p "$profile" --usage-file ... --oneshot "$prompt"` invocation
  shape (and the `--provider`/`--model` variant) as sound and not requiring any repair.
- Treating STEP U's smoke-test results as trustworthy and T7/T8-BCD's "-p/--profile does not
  exist" claim as refuted and safe to correct in `00`/`02` wherever it appears or might get
  copied forward.
- Treating the queued-item backlog as currently unaffected by anything found in this step (4
  old, unrelated blocked items; nothing newly stuck since 2026-09-08).

**Does not license:**
- Concluding the coordinator path is currently 100% healthy. Three real, unexplained
  zero-message failures exist since 2026-09-08 (2 `aos-orchestrator`, 1 `david`/today's morning
  brief) with a shared, distinctive signature and no confirmed root cause — the hook +x outage is
  a plausible but only partially-fitting explanation (fits today's david failure by timing, does
  not fit the two earlier `aos-orchestrator` failures).
- Any claim about the exact stderr/traceback of those three failures — that evidence was not
  obtainable in this session (journal permission gap, stated above, not worked around).
- Any repair action — none was authorized or attempted; Q4's plan was explicitly not written
  because the path this step was asked to investigate (`-p`/`--profile`) is not broken, and the
  path that IS showing failures is not yet diagnosed enough to propose a minimal repair.
- Any statement about `connectors/` or `workspaces/north_shore_sales_coach/` — both remained
  unread throughout, per header rule 1 (one combined grep that accidentally included a
  `connectors/` path was refused by the permission layer and not retried).

Stopping here, as instructed.
