# Operator-Lean On-Demand Business Brain Focused Proof
> Expires: never; point-in-time live-path evidence captured 2026-07-28.

## Result

PASS.

The live `wsl_hermes` path used one operator-lean Hermes call per message. The
two durable-business questions received only three scoped Business Brain notes;
generic conversation received none. The execution request called the existing
`create_task` tool and created exactly one item. The downstream worker launch
was suppressed during that proof so prospect research did not start.

## Live proofs

| Message | Brain sources | Observed queue delta | Result |
|---|---:|---:|---|
| `How much insight do you have on Time to Revenue which is my business?` | 3 | 0 | Substantive TTR identity, positioning, offers, constraints |
| `What should I focus on next to start getting clients?` | 3 | 0 | Contextual warm-network, daily prospecting, website-support advice |
| `What makes a conversation feel genuinely useful?` | 0 | 0 | Normal lean answer |
| `Create a task to research 5 prospects` | 0 | +1 | `AOS-2026-0188`, owner `revenue`, state `agent_todo`, size `small` |

### TTR sources actually retrieved

- `business_brain:memory/company.md`
- `business_brain:memory/offers.md`
- `business_brain:memory/positioning.md`

The TTR dynamic context was 3,113 bytes. Retrieval route was `pointer` for all
three sources.

### Client-acquisition sources actually retrieved

- `business_brain:operating_context/current_priorities.md`
- `business_brain:memory/sales_and_revenue.md`
- `business_brain:memory/prospecting_rotation_plan.md`

The client-acquisition dynamic context was 4,159 bytes. Retrieval route was
`pointer` for all three sources.

## Fixed preamble

Measured from the live operator-lean profile after synchronous MCP discovery,
using `o200k_base`:

- System prompt: 721 tokens
- Six tool schemas: 459 tokens
- Complete fixed preamble: 1,180 tokens

## Focused tests

`python -m unittest tests.test_telegram_conversational_routing`

Result: 15 tests passed.

## Token usage

```yaml
token_usage:
  ttr_live:
    model: gpt-5.5
    provider: openai-codex
    input: 2077
    cached_input: 0
    fresh_input: 2077
    output: 349
    reasoning: 19
    total: 2426
    api_calls: 1
  client_focus_live:
    model: gpt-5.5
    provider: openai-codex
    input: 2385
    cached_input: 0
    fresh_input: 2385
    output: 288
    reasoning: 19
    total: 2673
    api_calls: 1
  generic_live:
    model: gpt-5.5
    provider: openai-codex
    input: 1432
    cached_input: 0
    fresh_input: 1432
    output: 112
    reasoning: 0
    total: 1544
    api_calls: 1
  execution_live:
    model: gpt-5.5
    provider: openai-codex
    input: 3195
    cached_input: 0
    fresh_input: 3195
    output: 73
    reasoning: 0
    total: 3268
    api_calls: 2
  codex_workbench:
    exact: unavailable
```

An initial no-mutation execution probe exposed that the existing `worker`
parameter schema advertised an unconstrained string even though runtime
validation already allowed only six worker names. The schema was constrained
to those same existing names, the fixed preamble was remeasured, and the fresh
live proof above then created exactly one item.
