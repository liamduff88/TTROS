---
name: submit-confirm
description: Confirm one existing Shared Brain submit record (shared-submit-<32 hex>) from unconfirmed to confirmed through the TTROS confirmation path. Use when asked to confirm a submitted record, milestone, decision, fact or deliverable.
---

# Submit Confirm

> Revisit: when the submit review tier or confirmation contract changes. · Last touched: 2026-10-04.

This is the existing TTROS confirmation path for Shared Brain submit records.

## Confirm

Run exactly one command with the record ID:

```bash
python3 tools/shared_brain_confirm.py shared-submit-<32 hex>
```

It prints one JSON line. Report `record_id`, `reference`, `previous_status`, `status`, `already_confirmed`, `commit` and `sync_status` from it.

- `previous_status: unconfirmed`, `status: confirmed`: confirmation succeeded.
- `already_confirmed: true`: nothing changed; the record was already confirmed. Repeating the command is safe.
- `success: false`: nothing changed. Report the `error` as the blocker. Do not retry another way.

## Boundaries

- Never edit, rewrite or restore the record file yourself, and never run `git` on it. The command is the only confirmation path.
- The commit, push and upstream check happen inside the command. They are TTROS's automatic Git closure for durable records, not a worker Git commit or push, and the Agentic OS repository is not touched.
- The command changes only the record's status from unconfirmed to confirmed. It creates no submission, checkpoint, queue item or external action.
- Unknown, uncommitted, hand-edited or non-submit records are refused with nothing changed.
- Cite the record by its `reference`, not as an artifact path.

## Complete

The receipt quotes the command's JSON result: `status: confirmed`, the commit, and `sync_status: synced`.
