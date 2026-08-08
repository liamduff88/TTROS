# David Business Brain integration boundary

> Expires: when David's native profile, Hermes plugin contract, Context Assembler, or Brain write/promotion boundary changes. · Captured: 2026-08-05.

## Result

PASS. David retains native personal conversational continuity while receiving
authoritative organisational knowledge through the repository-controlled
Context Assembler and existing Brain MCP. No second context, memory, plugin,
promotion, or write framework was created.

## Registration and native boundary

- Pre-install `hermes -p david plugins list --user --json`: `[]`.
- Post-install plugin: `ttros-context-assembler`, version `1.0.0`, enabled,
  source `user`.
- Installer and drift audits cover seven profiles and explicitly report
  `global_default_profile_inspected: false`.
- David config keeps `memory_enabled: true` and `user_profile_enabled: true`,
  has the existing Brain MCP, and has zero shell `context_assembler_hook.py`
  declarations. The native plugin is therefore his one assembler path.
- Installed Hermes `turn_context.py` includes David in the same missing-marker
  fail-closed boundary as the six AOS profiles.
- First live installer repair: Hermes MCP discovery returned exit `0` after an
  interactive `Cancelled.` response, so no MCP was saved. The installer now
  answers the tool-selection prompt explicitly and treats `Cancelled.` as
  failure. The repaired rerun passed.

## Native identity, continuity, and authoritative reads

Baseline resumed David session `20260805_001925_755d15` answered:

```text
Identity: David — executive partner to Liam Duff, founder of Time to Revenue.
Personal continuity: Liam works alone.
```

After registration, the same resumed session repeated `Liam works alone` as
native David conversation continuity and separately returned organisational
facts from `business_brain:memory/company.md` and
`business_brain:operating_context/current_priorities.md`.

Native artifact:
`queue/context_assemblies/hermes-20260805_001925_755d15-20260805_001925_755d15:1941e709-5740-4897-98d3-573193e01e97:6743126c.json`.
The artifact is `knowledge_sensitive`, assembler v2, whole-vault default false,
zero source-discovery model/input/output tokens, with 13 isolated actual reads.
The two cited canonical reads were:

```text
business_brain:memory/company.md
  route=pointer
  sha256=472a930ed55dfd08cc05f69b8fe340edcf07e76a486df39302314b6e5330e3e9
business_brain:operating_context/current_priorities.md
  route=pointer
  sha256=e9e22d3c4cb5d1fa2417df3ebda54917824da1a109d14243314903573a003176
```

One invocation increased the assembly-artifact count from 1211 to 1212: one
native assembled-context path, no duplicate shell path and no fallback.

Final post-cleanup David invocation created exactly one artifact (1289 to
1290) and one model call. It identified David, recalled a separate pre-existing
personal continuity item from native conversation state, and read the restored
company note. Artifact:
`queue/context_assemblies/hermes-20260805_060210_a27bb5-20260805_060210_a27bb5:83f411a3-95f6-4565-b7fa-e70caf9920c1:f4ef105a.json`.
Its company actual-read SHA-256 is the restored preimage hash
`472a930ed55dfd08cc05f69b8fe340edcf07e76a486df39302314b6e5330e3e9`.

## David Brain transaction and cross-profile retrieval

David called only the existing `remember_brain_knowledge` MCP tool. The tool
classified the concise distillation as
`eligible_ordinary_organisational_knowledge`, `knowledge_state=verified_fact`,
`review_required=false`, and `external_action=false`.

```text
target: business_brain:memory/company.md
section: david_brain_boundary_proof_20260805
source: business_brain:memory/company.md#sha256=472a930ed55dfd08cc05f69b8fe340edcf07e76a486df39302314b6e5330e3e9
vault commit: 86f0703f0569a19d1bcd0727b7d7fb03152f5b1a
author: Hermes <hermes@local.ttros>
subject: hermes: david-brain-boundary-20260805
exact changed path: memory/company.md
postimage sha256: 61b490146d08b708d81e50e9edf996cd8cd5938717febdcc1dadcc98b80fda50
```

The complete Brain validator passed after the write. Focused fixtures prove
expected-hash conflict refusal, same-directory atomic replacement, candidate
validation, exact-path staging/commit, post-write verification, rollback and
preservation of concurrent/human content.

A normal native `aos-ops` invocation later returned the managed fact. Its
artifact is
`queue/context_assemblies/hermes-20260805_055308_5ec35a-20260805_055308_5ec35a:e8b16041-65a1-45ee-9527-884a4a29e097:48adbcc1.json`.
It records the actual read of `business_brain:memory/company.md` by `pointer`
with the postimage SHA-256 `61b490146d08b708d81e50e9edf996cd8cd5938717febdcc1dadcc98b80fda50`.
Exact usage was input 28,305, output 221, reasoning subset 136, canonical total
28,526, one API call, model `gpt-5.5`.

Cleanup used a hash-gated exact revert of the one vault commit. Cleanup commit
`aaea37a0c544cbaa21e28362c938fcfe2cd9477f` is Hermes-authored, changes only
`memory/company.md`, removes the synthetic marker, and restores the exact
preimage SHA-256 `472a930ed55dfd08cc05f69b8fe340edcf07e76a486df39302314b6e5330e3e9`.
The complete Brain validator passed again, and the vault content aggregate
returned exactly to its baseline digest.

## Deterministic policy and regression proof

`POLICY_CLASSIFICATION.json` records the fixture matrix. Review-tier classes
were refused by the writer without an approval reference; never-promote
classes were non-writable and exposed no candidate diff; the fixture target
was byte-identical before and after.

- Compilation: changed Python plus installed `turn_context.py` passed.
- Focused plugin/installer/drift/assembler/Brain/write/promotion/hygiene: 50 tests PASS.
- Step 6/native routing/orchestration/Codex affected suite: 84 tests PASS.
- Standing queue/path suite: 92 tests PASS.
- Dashboard backend suite: 222 tests PASS (one existing `utcnow` deprecation warning).
- Installer check, drift dry-run, Step 6 verifier `all`, and full Brain validation: PASS.
- No service restart was required; each native Hermes invocation loaded the
  profile/plugin configuration in a fresh process.

## Preservation hashes

| Target | Before | After | Meaning |
|---|---|---|---|
| `queue/work_items.jsonl` | `b7eec0121f36383fad100bb2fd7e765a1495d69f73503cecd2d26c4c9c2cc0a3` | same | no queue item or AOS-2026-0488–0491 mutation |
| `queue/run_ledger.jsonl` | `9f0f7b199a807b88eeb8ff43d11b157162fba6258e56758ed257f0f1fa51f4f9` | same | no run/workflow event |
| `queue/orchestration_events.jsonl` | `a4818271098cc343665e1ae777db2b724016db23b8226c3bc8e52c20b93ae4f5` | same | no orchestrator/worker event |
| `queue/notifications.json` | `fdbce41ccaa8f2bb7b3fd82d1eca52587801175fd16d5c5e81e4f674ba15f235` | same | no notification/Telegram activation |
| `queue/token_ledger.jsonl` | `3cfc25bcc5d1f7e916e9172b261e7e8024a190ea1019fd9967e9d1d814d7f564` | `1b33aacabab51900375412707f21f30917c8c60a293d90431ff2350c39bd3a41` | expected exact `aos-ops` proof usage row |
| `context/client_scope_registry.json` | `74c25f03c3499d58c9940f449a2f2fa92ddeaaffb3f0af41e5267de77d8dffe8` | same | protected routing JSON untouched |
| Telegram bridge source | `67b869202cfb613db8024b1fd74da69468e6360949353bee133b621736ba7e17` | same | bridge files untouched |
| repository `soul.md` | `811e56ccad2548fb8691ad309054362efb2dca5383be9fe9d24e8f6569f11b80` | same | Operating Hermes identity preserved |
| David `SOUL.md` | `a883ab59777a7b4521844420afff82879cc63c5e1f12c64d43b97eae53fbcc24` | same | David identity preserved |
| David `MEMORY.md` | empty-file SHA `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | same | personal memory store not copied into Brain |
| Agentic OS HEAD | `1ec13b608fdcd66ed62052d28fe3b908d1ddfc97` | same | no Agentic OS commit or push |
| vault content aggregate excluding `.git`/`.obsidian` | `1a7bf5752dd8b1028d816e2782e6aa1975c2cd093d0e52602098902544cae933` | same | synthetic Brain data fully cleaned |

David `config.yaml`, native `state.db`, installed `turn_context.py`, and the
token ledger changed for their intended reasons: registration, real resumed
conversation continuity, fail-closed profile coverage, and exact AOS proof
usage. Vault HEAD advanced by the required local write and exact cleanup audit
commits; no vault push occurred.

## Protected/external boundary

No email, Calendar, Drive, CRM, third-party send, external action, workflow,
Telegram activation, Agentic OS commit/push, or vault push was invoked. No
credential, authentication, `.env`, global/default Hermes profile, protected
routing JSON, Telegram bridge file, North Shore workspace, or AOS-2026-0488–0491
record was read for content or modified. Existing services were left running.

## Receipt / token usage

```json
{
  "lane": "workbench-verification",
  "profile": "codex",
  "model_requested": "current Codex session model",
  "model_confirmed": "unavailable from current CLI output",
  "provider_total_input": "unavailable from current CLI output",
  "fresh_input": "unavailable from current CLI output",
  "cached_input": "unavailable from current CLI output",
  "output": "unavailable from current CLI output",
  "reasoning": "unavailable from current CLI output",
  "closing_context_percentage": "unavailable from current CLI output",
  "artifact_paths": [
    "proofs/david-business-brain-2026-08-05/DAVID_BUSINESS_BRAIN_BOUNDARY_PROOF.md",
    "proofs/david-business-brain-2026-08-05/POLICY_CLASSIFICATION.json"
  ]
}
```
