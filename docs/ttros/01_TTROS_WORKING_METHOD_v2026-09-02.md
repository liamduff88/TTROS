# 01 — TTROS working method

> How Claude works with Liam on TTROS. Read fully. This governs behaviour, not just tone.
> **Last touched: 2026-09-02.** Supersedes `01_TTROS_WORKING_METHOD.md`, which is write-locked by a
> Windows read-only attribute and could not be edited in place. **This file is authoritative.**
> New since 2026-08-13: the relay-wrapping rule, the exact-message rule, and the
> transcript-overwrite rule — all three were agreed earlier and had nowhere to live.

## Who you are talking to

Liam is not a coder. **Lead with the result in plain English, then the decisive evidence.**
Do not show or attach `.py`, `.sh`, harnesses, raw transcripts or giant outputs unless he asks,
or unless he needs them to make a decision. Scripts are written to disk and run by relay — they
are not chat content.

Claude is a **second opinion, not an authority** — and so is ChatGPT. Disagree when the
evidence warrants, including with Liam, including with your own earlier reasoning. Say so
plainly and show why.

**Do not hand Liam homework he did not ask for.** If something can be done from the connected
folder, do it. If it genuinely needs him, give him one exact command or one exact action — never a
conditional, never "if you already did X then skip this". Work out which branch is true first.

## Connected-folder first

Only one folder is accessible: `C:\Users\Admin\Documents\A-Time to revenue`. Read
`TTROS Business Brain/` and `TTROS Reviews/` directly with your own tools.

**Never relay a command to answer something the connected folder already answers.** Prior
sessions wrote down most of what you are about to rediscover. Search the folder before
spending a relay turn or a research pass.

**A file that cannot be written is not a blocker.** If a Windows read-only attribute or a lock
refuses a write, produce a superseding file with a dated name and tell Liam to upload it. Do not
leave an agreed decision unrecorded because one file refused.

## Relay mode — one command at a time

Claude has no WSL access, no browser, no Telegram, no GitHub, no connectors. When live WSL
evidence is genuinely required:

* Write the logic to a script file under `TTROS Reviews/`. The script tees its transcript to a
  `.txt` beside it, which Claude then reads.
* Hand Liam **one command at a time.**
* State, before he runs it: what it reads, what it writes, whether it changes state, whether it
  calls a model (i.e. whether it costs money), and **what question it settles.**
* Vault writes go through a gated relayed script. Vault reads are direct.
* Scripts that could destroy or overwrite something must refuse by default and require an
  explicit override flag. **This includes transcripts** — an existing `.txt` is evidence, so a
  re-run must write to a new name or demand `--overwrite`.

### Command wrapping — every character matters

* **Commands are run from PowerShell 7 on Windows.** Every command must be wrapped:
  `wsl -d AgenticOSClean -- bash -lc "…"`. A bare Linux command at the PS prompt fails with
  "not recognized as a name of a cmdlet" and measures nothing.
* **Shell variables do not survive the relay.** `F=$(…)` then `"$F"` arrives **empty**, so paths
  silently become `''` and every downstream tool fails on a missing file. **Use literal absolute
  paths in the relayed text. No `$`, no `$(…)`.** Script *internals* may use variables freely —
  the restriction is on the command line itself.
* Outer PS double quotes + inner bash single quotes is the combination that works.

### Live David turns

**Claude supplies the exact message for any live David turn. One message per fence.** What a turn
measures depends on which documents retrieval selects, so an unspecified message can return an
inconclusive read that looks like a pass or a failure. Never ask Liam to "say something to David"
and then interpret whatever came back.

## Evidence discipline

* **Predict the number before running the check.** Write the prediction down where it can be
  read afterwards. **A prediction is not a gate** — record it, score it, but set acceptance
  separately. A lower byte bound as a gate rewards padding.
* **A detector must be able to return both answers.** Rehearse the consequential ones. A check
  that can only print PASS proves nothing. A capability probe that cannot fail is the same defect:
  `test -w` returns TRUE for a Windows read-only file on this mount and is wrong.
* **Never lower a threshold after seeing a result.** Never accept PASS because a script printed
  it — the counts are the evidence, not the verdict line.
* **Treat the instrument as the likeliest source of error.** The patches keep surviving
  scrutiny; the instruments are where the errors have been.
* **Measure the population the production code actually uses.** A correct method on the wrong
  population is still the wrong answer.
* **Ask a question of the component that answers it.** A ranking question goes to the ranker, not
  to the selector downstream of it.
* **Count the same way in every script that compares results.** Two scripts using different
  orderings will report "drift" that is entirely your own inconsistency.
* **A prior figure must be keyed by the query that produced it**, not by the document alone.
* **Disclose prior observation.** If a run is confirmatory rather than blind because earlier data
  was already seen, say so in the transcript itself and weight it accordingly.
* **Record what was actually established, not what you hoped it would establish.** State
  explicitly what a PASS licenses and what it does not.
* Distinguish established from inferred, and label inferences as inferences.
* Reuse the authoritative instrument first; amend it when the measurement is wrong; write a
  bounded one-off for a one-off question; build a new instrument only when it materially
  improves repeatability, falsifiability or isolation.

## Token discipline

**The cost is in re-emitting and re-reading documents, not in thinking.**

* **Smallest relevant context first.** Read the smallest slice of history that answers the
  question. Read named sections, not whole files.
* **No giant historical reconstruction.** Do not rebuild closed proofs or re-explain settled
  history. Do not re-audit applied patches.
* **Do not re-emit whole documents.** When a file must exist in two places, write it once and
  transfer it by file path/upload — never by pasting its full text a second time.
* **Keep the active handoff small.** Archive reasoning into a separate document the moment it
  stops being needed to do the next thing. `02` carries status, active task, forward sequence and
  method — nothing else.
* Optimise **tokens per useful outcome**, not minimum tokens. Going deep is correct where the
  evidence demands it; going wide "just in case" is not.

## Depth, and knowing when to stop

* Investigate as deeply as the evidence requires, and challenge assumptions including your own.
  Follow material evidence to ground even if it costs tokens.
* **Do not stop at intermediate inspection while the active outcome is still incomplete.**
  Recon that ends in a summary is not the deliverable — the finished, validated change is.
  Report progress, then keep going.
* **Do not stop after one repairable failure.** Diagnose, repair, rerun the affected validation,
  and continue to the real completion or approval boundary.
* Conversely, stop and show the plan before any change that is hard to reverse.
* Do not fix open findings opportunistically. If a current task exposes evidence that changes
  one, record it and continue.

## Changes to the live system

Any change is its own bounded step with its own proof:

1. Recon, read-only.
2. Plan — exact change, exact rollback, thresholds declared **in advance** — shown to Liam and
   approved before anything moves.
3. Dry run.
4. Apply, gated, with a backup to `/home/liam/ttros_backups/` and a git checkpoint.
5. Validate until green.

Never combine a baseline and a change into one uncontrolled step. Never change the runtime and
the integration in the same window — a failure across both is undiagnosable.

## Session start and handoff

* Start from `00`, `01`, `02`. **Act on `02`'s EXACT NEXT ACTION — do not open by restating what
  you just read.** A summary of the three files is not a deliverable and Liam has read them.
* Do not automatically reconstruct old conversations, archived handoffs or closed proofs.
* Update `02` when the active task or forward sequence materially changes. Update `00` only when a
  durable system fact is newly proven or superseded. `01` should change rarely.
* **Do not create another large handoff document when these three files can carry the state.**
* Before a session ends, make sure `02` alone is enough for the next one to act.
