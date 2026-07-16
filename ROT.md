# ROT.md — how this OS decays, and the cadence that fights it
> Revisit: when a layer's real-world change rate shifts (new vendor, law change, faster-moving client). · Last touched: 2026-07-15.

Different layers rot at different rates, like a building. The foundation holds
for years; the food in the fridge is gone by the weekend. You do not maintain
them on the same schedule, and you do not panic when the fast layer moves —
it is supposed to. Rot is fought with conventions + a register + three cadences
+ Hermes-native self-improvement, not vigilance.

## The rot table (binding for this system)

| Layer | Rots in | Trigger to revisit |
|---|---|---|
| Identity (soul.md, CLAUDE.md, AGENTS.md, CODEX.md, agents/) | Months–year | Offer architecture change, ICP change, model-generation jump |
| Rules & Hooks | Weeks | New boundary incident, contradicting rules, compliance change |
| Skills | Days–weeks | Edge case found on contact; V4.1 spec change; model upgrade making instructions bloated |
| Agents/profiles | Days | Agent doing two jobs; model upgrade absorbing a role; Hermes release changing profile capabilities |
| Tools/MCP/CLI | Hours | Connector expiry, API change, Composio toolkit change. Expect breakage. Wrap, never marry. |
| Pre-seeded (v0) playbooks | First client contact | Every real use is a mandatory revisit — the first three uses ARE the hardening |
| model_prices.json | Weeks | Any provider pricing change; checked monthly |
| Token metering wiring | Per Hermes release | Usage-metadata fields can change shape — re-verify in the monthly `hermes update` step |
| Substrate (wiki) | Grows, doesn't rot | Only failure mode: a page stale vs. its source. Caught by Revisit lines + expiry.md. Re-ingest, don't rebuild. |

## Models getting smarter is rot too
A prompt written for an older model looks bloated to a newer one. As models
improve you write less to get the same result, so skills and agents trend
leaner over time. A skill untouched for months may just be carrying
instructions the current model no longer needs. That is drift; the maintenance
loop catches it.

## The per-file convention
Every layer/substrate file that can go stale carries:
`> Revisit: <when or under what condition> · Last touched: <YYYY-MM-DD>`
Point-in-time docs use `Expires:` instead (superseded, not refreshed).
The live register is the per-file Revisit/Expires metadata audited by
`/maintain-os`; there is no separate stale wiki registry to consult.

## The three cadences (upkeep happens TO Liam)
1. **Monthly, automatic.** A Hermes scheduled task runs /maintain-os in
   interview mode: walks every Revisit date, finds what's past due, asks
   multiple-choice refresh questions over Telegram. Five minutes of tapping.
2. **Weekly, light.** /maintain-os in scan mode: audits all five layers + wiki
   against os-blueprint.md and reports drift — unused skills, contradicting
   rules, hooks not firing, stale wiki pages, profile config drifted from
   lane_profiles.json, v0-skill usage, promotion/demotion math,
   model_prices.json freshness, ledger `unavailable`-rate. One verifier
   subagent per rule + a skeptic subagent to filter noise. Reports and
   recommends only — never deletes without Liam's okay (never.md #12).
3. **On contact, always.** In a skill and spot a missing edge case? Fix it
   then. The fast layers get maintained by use.

Plus Hermes-native: memory loop, Curator, /learn, /goal contracts, monthly
`hermes update` (capabilities re-verified into context/HERMES_CAPABILITIES.md).

A system that provokes you survives. One that waits for you to remember is one
you find rotted in a month.
