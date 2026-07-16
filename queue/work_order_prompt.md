# queue/templates/work_order.prompt.md
> Template only — does not launch agents or change queue state. Filled by
> Operating Hermes at fan-out; not wired to a live runner.

## Purpose
Turn a queue item into the work order a department subagent runs against.
Agents talk in work orders: `done_when` = spec + stop condition + future
invariant (LOOP_POLICY.md).

---

**Work order — {item_id}**

Lane: {lane} · Profile: {profile} · Budget class: {budget_class}
Escalated: {escalated}
Client scope: {client_scope}
Context classification: {context_classification}

### Task
{task_description}

### Context (read-only pointers, not pasted content)
- {memory_pointer_1}
- {memory_pointer_2}
- Client entity page (delivery lane only): `business_brain:{canonical_client_relative_path}`

### Allowed actions
{allowed_actions}

### Stop conditions
- {stop_condition_1}
- Ambiguous scope → stop and ask, don't guess (always.md).
- Any external action beyond `approved_external_action` on this item.

### Definition of done
{definition_of_done}

### Never
- Blend another client's data into this task.
- Claim done without evidence — every claim needs an artifact or a receipt line.
- Invent a number, secret, or convention not present in the pointers above.

### On completion
Write a receipt at `queue/receipts/{item_id}.md` including the `token_usage`
block (TOKEN_POLICY.md §8.1) and an explicit `memory_promotion` field (empty
array if nothing to promote). Record `brain_context_used` only from actual
successful scoped reads; technical-only work explicitly records
`brain_context_status: not_applicable`. Ambiguous or missing mandatory context
stops to `needs_input`. Report PASS or NEEDS ATTENTION — never a vibe.
