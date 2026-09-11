# STEP T9 — eager `brain` MCP for David, cap proven at ceiling first

Declared model calls: 2 (Part 0b: 1, Part C: 1). Transcript(s) beside this report:
`scripts/stepT9_live_capped_turn_part0b.txt`.

## Verdict, plain English

**No lever exists to apply.** Hermes v0.21.1 has no per-MCP-server control that keeps one
server's tools eagerly visible while `tools.tool_search.enabled` stays `auto` for the rest — only
a single global tri-state (`auto`/`on`/`off`) governs deferral, and it applies to every
`mcp-*`-prefixed toolset uniformly. The step's own Part A rule ("If no per-server control exists,
stop and report; that is a result") therefore applies: **stopped after Part A.** `config.yaml` was
never touched — Part B (apply) and Part C (live turn with the lever) did not run. Part 0's two
checks (free + 1 model call) ran as declared and both matched prediction.

**Model calls used: 1 of 2 declared** (Part 0b only; Part C not run because there is nothing to
test — no lever was applied).

## Part 0a — is the production coordinator turn capped at all? (free, read-only)

Target: `queue/receipts/david-morning-brief-2026-09-09.md`, delivery receipt created
`2026-09-09T16:46:26Z`, `invocation_id=hermes-c467dd56b61841f18c75a3c9cacccc46`,
`session_id=20260909_094653_e13ecd`.

Matched (by `started_at`, not "latest row") to `state.db` session `20260909_094653_e13ecd` in
`/home/liam/.hermes/profiles/david/state.db`: `started_at=1788972415.89499` →
`2026-09-09T16:46:55.894990Z`, ~29s after the receipt's `created_at` — the only session in that
database with this exact id, so the id match alone would suffice; the timestamp is confirmatory.

**Prediction (written before query):** Claude's: `sys.maxsize`, ~0.6 confidence. Alternative:
config's stated `150`.

**Result:** `model_config.max_iterations = 9223372036854775807` (= `sys.maxsize`, 2**63-1).
`api_call_count = 1`, `tool_call_count = 0`.

**Verdict:** matches Claude's prediction, not the static `150` read from config. The production
coordinator turn that actually executed was recorded with an effectively unbounded per-session
iteration cap. Record only, per the step's own instruction — not re-litigated in Part 0b/C, which
use `--max-turns` explicitly instead of relying on whatever the coordinator's own launch path sets.

## Part 0b — GVR question, `--max-turns 1`, current config (no lever yet)

**Prediction (written before running):** Claude's: `api_call_count = 1`. Two possible if Hermes
makes a budget-exhausted summary call after the turn cap bites.
**Stop rule:** `api_call_count > 2` ⇒ the cap does not bind as the code reading says; stop, no
lever, Part C not run.

**Instrument:** `scripts/stepT9_live_capped_turn.py` (a parameterised copy of
`scripts/stepT8BCD_live_capped_passage_turn.py`'s invocation/budget/session-lookup shape — reused
per the step's instruction rather than a fresh instrument), invoked as:
`python3 scripts/stepT9_live_capped_turn.py --max-turns 1 --label part0b`.
`HERMES_HOME=/home/liam/.hermes/profiles/david`, `TTROS_DAVID_TEST_TURN=1`, invocation budget
hard-capped at 1 by the instrument, 180s wall-clock kill (actual: 18.8s, no timeout).

**Result:** new session `20260911_000551_4b41e7`. `api_call_count = 1`, `tool_call_count = 1`,
`model_config.max_iterations = 1` (confirms `--max-turns 1` binds directly to
`model_config.max_iterations` — the cap mechanism reads through as documented). Tool sequence:
`['tool_describe']` (David inspected `mcp__brain__open_note`'s schema, then the iteration budget
was exhausted before any `open_note` call; Hermes injected "You've reached the maximum number of
tool-calling iterations... provide a final response" and David answered from the card alone,
correctly stating it did not have the exact quote). Vault sentinels unchanged before/after.

**Verdict:** matches the primary prediction exactly (`api_call_count = 1`, no budget-exhausted
extra API call). `1 ≤ 2` — below the stop threshold. Proceed to Part A.

## Part A — recon: does a per-server eager-MCP control exist in v0.21.1?

**Surface searched:** installed Hermes source at `/home/liam/.hermes/hermes-agent` (confirmed
live version via `hermes --version`: `Hermes Agent v0.21.1 (2026.9.7) · upstream bffa5f75 · local
b2aa855b`) — specifically:
- `tools/tool_search.py` (`ToolSearchConfig.from_raw`, `is_deferrable_tool_name`,
  `classify_tools`, `assemble_tool_defs`, `should_activate`)
- `tools/mcp_tool_registration.py` (`_select_utility_schemas`, `_make_tool_filter`) — the only
  per-server `tools.*` keys read anywhere are `resources`, `prompts`, `include`, `exclude`
- `tools/delegate_tool_toolsets.py`, `tools/registry.py` — toolset registration; no per-server
  search/eager flag
- `hermes_cli/mcp_config.py`, `hermes_cli/tools_config_mcp.py` — MCP server config loaders; no
  `tool_search` key read at server scope anywhere
- `website/docs/user-guide/features/tool-search.md` (the shipped documentation of this exact
  feature)

**Finding, confirmed in source:**
`is_deferrable_tool_name()` (`tools/tool_search.py:135-147`) classifies a tool as deferrable if
its registered toolset name starts with `mcp-` — true for every MCP server unconditionally, with
no config-level exemption:
```
toolset = _registry_toolset(name)
return toolset is not None and (toolset.startswith("mcp-") or toolset not in _DIRECT_SURFACE_TOOLSETS)
```
The `defer` config key (`ToolSearchConfig.defer_tools`) is additive-only — it can mark extra
*core* tool names as deferrable, but it has no negative form and never exempts an MCP toolset,
which is already unconditionally `True` via the `mcp-` prefix branch above.

`assemble_tool_defs()` (`tools/tool_search.py:304-`) takes exactly one `ToolSearchConfig` (loaded
once, globally, via `load_config()`) — no `server_name` or per-server config is threaded into
classification anywhere in the call chain. `_select_utility_schemas` and `_make_tool_filter`
(`tools/mcp_tool_registration.py:72-129`) are the only functions that read `mcp_servers.<name>
.tools.*`, and they only gate resources/prompts utility schemas and include/exclude tool-name
filtering — neither affects tool_search deferral eligibility.

The shipped docs are explicit and confirm the negative: "If you want the old always-eager
behavior for a small toolset, set `enabled: off`" (`website/docs/user-guide/features/tool-
search.md`) — the documented lever is **global**, not per-server. There is no third value, no
per-server override block, and no undocumented key found by exhaustive grep for
`always_direct|sticky|force_visible|force_eager|never_defer|no_defer|exempt`-style names across
the whole source tree.

**Conclusion: no per-server eager-MCP control exists in Hermes v0.21.1.** The only lever that
makes `brain`'s tools always-visible is `tools.tool_search.enabled: off`, global — which this
step's own Part A explicitly rules out as unacceptable (T6's finding: it re-exposes
`session_search` and `todo_list`). Per the step's stop rule, this is where the step ends: no
change was made to `/home/liam/.hermes/profiles/david/config.yaml`, and none is proposed.

**Exact change considered and its rollback:** none applied. No preimage was taken because no edit
was made — there is nothing to roll back. If a future step wants the old blanket-eager behavior
regardless of the `session_search`/`todo_list` re-exposure cost, the single-line change is
`tools.tool_search.enabled: off` at the top level of `config.yaml`, reverted by restoring the key
to `auto` (or removing it) from a preimage taken first.

## Live effect (answered from source; no restart performed)

MCP servers are connected once at gateway process start, not per session: `gateway/run.py`'s
`_discover_gateway_mcp_tools()` calls `discover_mcp_tools()` at boot, which reads `mcp_servers`
from `get_hermes_home()`'s config a single time per served profile (per-profile under multiplex,
via `_profile_runtime_scope`); `hermes_cli/mcp_startup.py` guards this with a
process-lifetime `_mcp_discovery_started` flag, not a per-turn one. So even had the `brain` entry
been edited, a **running** Telegram gateway process would keep serving the connection/tool
schemas it discovered at its own last start — the edit would not reach production traffic until
that gateway process restarts. (`tools.tool_search.enabled` itself, by contrast, is re-read via
`load_config()` on every `assemble_tool_defs()` call — that part of the pipeline is per-turn, but
it is moot here since no config value was changed.) This is inferred from Hermes' own gateway
source only; `connectors/telegram_bridge/` (TTROS's own bridge to that gateway) is protected and
was not opened.

## Part B / Part C

Not run. Part B calibrates and measures the tool array *after applying the lever*; Part C spends
the second declared model call testing behavior *under the lever*. Since Part A found no lever to
apply, both are out of scope per the step's own gating rule — running them against the unmodified
config would not test anything this step asked for, and spending the second model call would not
be licensed by any predicate the step defined.

## Model calls: 1 used / 2 declared

Part 0b: 1 (used). Part C: 1 (declared, not spent — Part A stopped the step first).

## What this licenses

- The production coordinator's last successful run had an effectively unbounded per-turn
  iteration cap in its recorded `model_config`, not the `150` visible in static config (Part 0a).
- `--max-turns N` passed to `hermes chat --oneshot` does bind directly to
  `model_config.max_iterations` for that session, confirmed live at N=1 (Part 0b).
- Hermes v0.21.1 has no config surface for a per-MCP-server eager/always-visible exemption from
  tool_search deferral — confirmed by source across every file that reads `tool_search` or
  per-server `tools.*` config, and by the feature's own documentation.

## What this does NOT license

- No live change to David's profile — `config.yaml` is exactly as it was before this session.
- No conclusion about whether going globally eager (`tools.tool_search.enabled: off`) is worth its
  known cost (`session_search`/`todo_list` re-exposure, per T6) — that tradeoff was already
  adjudicated in T4 Item 4 ("still leave `auto`") and is not reopened here.
- No live-turn evidence for this step's Part C acceptance criteria (`tool_describe` count under a
  lever, `api_calls ≤ 3`, provenance, vault-unchanged) — none of that was tested, because there was
  no lever to test it under.

Stopping here per the step's own instruction.
