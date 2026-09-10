# CLAUDE.md — TTROS repo rules

> Repo root: `/home/liam/agentic-os-live`. This file governs every Claude Code session in this
> repo. Where it conflicts with a step prompt, this file wins; where Liam gives an explicit
> instruction in session, Liam wins.
>
> Derived from `01` (working method), the protected boundaries and design rules in `00`, and the
> constraints in `02`. Those files are the source; this is the working extract.

\---

TTROS PERMISSION HEADER



Reproduce only the four-line PERMISSION MODE block below verbatim at the top of every workbench prompt (Claude Code, Codex, Antigravity). The remaining rules in this section govern the workbench but do not need to be repeated in prompts.



PERMISSION MODE — SCOPED LOCAL TASK APPROVED

Do not ask for permission during this scoped local task. Assume approval for local reads, local edits, file creation, dependency installation, validation commands, local dev-server startup, browser preview, and screenshot capture inside the stated scope.

Do not ask before editing files inside the stated folder. Make the changes, validate, and return the compact closeout.

Stop only for real external/destructive actions.



Scoped local/reversible work is pre-approved. Within the stated task, read/edit/create local files, fix adjacent in-scope defects, run tests/builds/validation, inspect logs/processes, create backups/preimages/artifacts/cards/receipts/indexes, refresh search/Graphify, and run bounded model calls already authorised by the task without asking Liam. If local work fails, diagnose, make the smallest correct repair, validate, and continue. Do not stop merely because the exact file/function was not predicted.



Normal source ingestion is automatic and requires no Liam review: classify → preserve original → semantic extraction → noncanonical source card/evidence receipt → verify → index/search refresh → retrievable by David. Ingestion does not automatically promote semantic claims into canonical Business Brain truth. Business Brain writes still use the existing gated vault-write path; never bypass enforced `.hermes.md` approval.



Stop for Liam only for real external/destructive/sensitive actions, including sends/posts/messages, CRM/customer mutation, calendar booking, public deploy/publish, GitHub push, spending money, destructive deletion outside scope, recurring external jobs, provider-account mutation, live customer changes, credential-store access, or a material change to agreed TTROS architecture.



Credential stores are a hard boundary: never open, read, grep, print, copy, diff or hash auth-secret/credential files. Normal scoped CLI auth/status/login flows are allowed; Liam handles interactive authentication.



`connectors/` including Telegram bridge/startup, and `workspaces/north\_shore\_sales\_coach/`, remain protected unless Liam explicitly scopes them.



Human review is reserved for genuinely consequential canonical promotion, real external/destructive actions, material architecture changes, or explicit runbook operator verification — not routine ingestion, cards, indexing, receipts, local edits, tests or validation.



No GitHub push unless Liam explicitly authorises it.

\---



## Model calls and the budget

The `Bash(hermes \*)` ask rule gates **direct Hermes commands only** — a `hermes …` command run
as a Bash call. It does **not** gate Hermes calls made from inside a Python or shell instrument;
those are subprocess calls the permission layer never sees. Repeated firing of that rule inside a
step therefore means the session is invoking Hermes directly instead of through an instrument,
which is the wrong instrument shape — fix the script, don't remove the rule.

**Because the permission layer cannot enforce a model-call budget, the instrument must.** Any
script that makes model calls:

* counts every call it makes;
* hard-stops at the predeclared maximum and exits with an error rather than exceeding it;
* writes the actual count, alongside the declared maximum, into its transcript.

A budget stated only in a prompt is not a budget. Needing more calls than declared is a finding
to report, never a number to quietly raise mid-run.

## Canonical files — read from disk, never from memory

`docs/ttros/` holds read-only mirrors of the five canonical files:

* `00\_…CURRENT\_STATE…` — what exists and is proven, protected boundaries, open findings.
* `01\_TTROS\_WORKING\_METHOD\_v2026-09-02.md` — method. Changes rarely. **The bare-named
`01\_TTROS\_WORKING\_METHOD.md` in the folder is write-locked and superseded — never read it.**
* `02\_…ACTIVE\_TASK…` — active task and forward sequence. The moving baton.
* `TTROS\_BUILD\_PLAN\_…rev11.md` — **the design of record.** Closed. Do not re-review it, do not
propose a rev 12.
* `TTROS\_CAPABILITY\_HARNESS\_QUESTIONS\_v1\_UPDATED\_2026-09-04.md` — the B7 source. Titled
"# B7 — the bound that can say NO". It defines B7; it does not close F-CAPABILITY-1.

Rules:

* The Windows folder `A-Time to revenue` is authoritative. `docs/ttros/` is a mirror.
**Never edit a mirror**, and never treat one as a second source — if the harness or any
canonical file needs changing, it changes at source and the mirror is refreshed.
* `docs/ttros/SOURCE.sha256` records the SHA-256 of each mirror. **If a mirror's hash does not
match its source, stop and say so.** A divergent mirror is the two-copies collision Step 0
exists to remove.
* **If two revisions of the same canonical file are present in `docs/ttros/`, stop.**
* Read the named section you need. Do not read all five end to end at session start, and do not
restate what you read back to Liam.

## Where Claude Code differs from Claude in the browser

`01` and `02` describe relay mode — Claude has no WSL channel and hands Liam one command at a

time. That does not apply here. This session executes directly. Do not hand Liam commands he

does not need to run. What still applies is evidence discipline, token discipline and reporting.

## Evidence discipline

* **Predict the number before running the check, in writing, where it can be read afterwards.**
A prediction written after the result is not a prediction.
* **A detector must be able to return both answers.** Rehearse the negative case on a
consequential check. A check that can only print PASS proves nothing.
* **Never lower a threshold after seeing a result.** The counts are the evidence; the verdict
line is not.
* **Treat the instrument as the likeliest source of error.** That is where the errors have been.
* **Never gate on a hand-counted literal.** Numeric gates assert their input is a number. Assert
surviving byte counts rather than assuming nothing was dropped.
* **Derive the population in the same run that uses it.** Never compare a `tests/` figure to a
repo-root figure. Suite baseline is **772 passed / 0 failed**; 746 and 760 are stale.
* **Record what was actually established, not what you hoped.** State explicitly what a PASS
licenses and what it does not. Label inference as inference.
* **Reuse the authoritative instrument first.** Amend it when the measurement is wrong. Write a
bounded one-off for a one-off question. Build a new instrument only when it materially improves
repeatability, falsifiability or isolation.
* **Every measurement script tees a `.txt` transcript beside itself and refuses to overwrite**
without an explicit `--overwrite` flag.
* **Disable before deleting.** Prove the replacement path green, then remove the old one.
* **A bare identifier is not a name.** When a detector is created, define it in `00` at that
moment or use a descriptive name until it is. B6 = candidate disposition / declared-input
arrival. B7 = the fixed 25-question capability harness. B8 = cache-and-latency observer.
* **A document's title is an assertion and can be wrong.**

## Standing facts that trip sessions up

* Backend root `/` returns **404 by design**. Health is `/api/health` → 200.
* `hermes-\*.json` in `queue/context\_assemblies` is what the model actually received and is
**authoritative for any context proof**. `ctx-\*.json` describes a context that was never sent —
a proof reading `ctx-\*` proves nothing.
* Patch `tools/context\_assembler.py` **anchor-gated, not hash-gated** (F-ASSEMBLERDRIFT-1).
* `\_ttros\_mirror/` predates the `historical\_source` filter. Architecture shape only, **never
evidence of current code**.
* **B8 is a plugin hook, not a gateway hook** — gateway hooks do not fire in the CLI.
* **State the surface.** Gateway-David and CLI-David may resolve context files differently. Every
measurement names the surface it ran on.
* The frozen v0.18 baseline under `/home/liam/ttros\_baselines/hermes\_v018\_2026-08-13/` **must
survive any cleanup and any upgrade.**
* **SYSTEMD IS THE RUNTIME AUTHORITY.** Anything recurring is a user unit. No cron, no launchers.

## Reporting to Liam

Result in plain English first, then the decisive evidence. **Liam is not reviewing code.** Do not
paste scripts, implementation files, raw transcripts, giant diffs or proof output into the chat
unless he asks or needs them to decide. Write them to disk and name the path.

Do not stop at an intermediate inspection while the step is still incomplete. Diagnose, repair,
re-run the affected validation, and continue to the real completion or the declared boundary.

