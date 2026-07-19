# Codex Workflow Runner Prompt Template
> Revisit: when the Agentic OS Codex invocation contract changes. · Last touched: 2026-07-19.

Use this template after a prepared local run folder has been created with:

```bash
python3 tools/aos-workflow.py prepare <workflow_id>
```

Canonical supervised Codex launch command (pass the bounded prompt below on
standard input):

```bash
cd "/home/liam/agentic-os-live" && /home/liam/.local/bin/aos-codex <<'AOS_CODEX_TASK'
<PASTE THE BOUNDED PROMPT BELOW>
AOS_CODEX_TASK
```

## Prompt

PERMISSION MODE — SCOPED LOCAL TASK APPROVED

Do not ask for permission during this scoped local task. Assume approval for local reads, local edits, local file creation, dependency installation, validation commands, local dev-server startup, browser preview, and screenshot capture inside the stated scope.

Do not ask before editing files inside the stated folder. Make the changes, validate, and return the compact closeout.

Stop only for real external/destructive actions.

Work only in this prepared run folder:

```text
<prepared_run_folder>
```

Do not edit outside the prepared run folder unless Liam explicitly expands scope.

Task:

Run the prepared local workflow packet using only files inside the prepared run folder and the source workflow folder referenced by `run_packet.md`.

Required local files:

- `run_packet.md`
- `intake_template.md` or completed intake file
- `output_placeholder.md`
- `receipt_placeholder.md`
- source workflow folder referenced in `run_packet.md`

Rules:

- Local-only file work.
- This is a fresh ephemeral session. Never use `resume`, `--last`, or a prior transcript.
- Before 50% context, write a compact receipt/handoff and end; any continuation starts fresh from that artifact.
- Read files by relevant line range whenever possible.
- For passing tests, retain only the tail summary; preserve detailed output only while investigating a failure.
- Never dump `work_items.jsonl`, ledgers, receipt directories, complete queue history, or similarly large runtime collections into the model session.
- Do not send, publish, upload, mutate CRM records, contact clients, call connectors, or perform external actions.
- Do not launch other agents or recursively call Codex, Claude, Hermes, connectors, dashboards, Telegram, browsers, or external APIs.
- If intake is incomplete, mark the run `NEEDS ATTENTION` and list missing fields.
- Write workflow output only into the prepared run folder.
- Write receipt or closeout notes only into the prepared run folder.
- Human review is required before any external/client-facing use.
- No external send, publish, CRM update, client delivery, or connector action is allowed without explicit human approval.

Return only:

```text
PASS/NEEDS ATTENTION

Files touched:

* ...

Validation:

* ...

Blockers:

* ...

Next action:

* ...
```
