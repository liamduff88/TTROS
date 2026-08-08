# Steps 7–8 proof — Context Assembler v2 and nightly knowledge hygiene

> Revisit: if the assembler retrieval hierarchy, Brain transaction contract, Graphify/search publication format, or nightly schedule changes. · Last touched: 2026-08-04.

## Verdict

**PASS.** Steps 7 and 8 reached their locked completion boundary. Context Assembler v2 extends the one existing assembler path; nightly hygiene uses the existing Hermes scheduler, Brain transaction writer, Graphify, exact search, provenance, receipt, and vault-local Git machinery. No second memory, queue, scheduler, graph authority, promotion layer, provenance store, private Hermes namespace, whole-vault default, or further architecture phase was created.

The named current-state handoff supplied in the task was not present in the repository. In accordance with the task, the prompt, live architecture note, and live Step 4–6 proof files were used as authority. No closed Step 0–6 design was reopened.

## Implemented production behavior

### Context Assembler v2

- Preserves the installed `TTROS_ASSEMBLED_CONTEXT_V1` transport marker while declaring manifest `schema_version: 2` and `assembler_version: 2`.
- Resolves through one enforced route: explicit canonical pointer or known entity, then relationship-dependent one-hop Graphify target discovery, then exact scoped search, then direct canonical-file fallback.
- Treats Graphify as derived routing metadata and opens the canonical Brain note it identifies.
- Applies client scope before Graphify, search, Brain, queue/activity, session, or open-loop result construction.
- Selects relevant paragraphs from at most two session turns, matching active commitments, and matching open-loop bullets. It does not include session transcripts or the vault wholesale.
- Emits actual-read identity, route, client scope, content SHA-256, route hierarchy, `whole_vault_default: false`, and zero-token source-discovery accounting.
- Keeps the Step 6 dial/fuse and automatic compaction. The 60,000-token budget is a visible warning, not a silent omission boundary.

### Nightly knowledge hygiene

- Production CLI: `tools/nightly_knowledge_hygiene.py`.
- Existing-scheduler entry: `/home/liam/.hermes/profiles/aos-orchestrator/scripts/ttros-nightly-knowledge-hygiene.py`.
- Existing Hermes job: `e5638ac27359`, `TTROS nightly knowledge hygiene`, `30 2 * * *`, local delivery, no-agent mode, repository workdir.
- Parses only explicit structured `knowledge_candidates` in scoped historical session journals. Verified facts/operator corrections require their verification predicate and an exact canonical target. Interpretations/hypotheses/uncertainties fold into `executive_view.md`; unresolved follow-ups into `open_loops.md`; contradictions into `contradictions.md`; formal commitments are deferred for Liam.
- Uses stable managed-section IDs, so it consolidates instead of appending duplicate prose or copying transcripts.
- Reconciles deterministic Step 5 staleness, canonical operator corrections, and the formally proved closed Revenue Gate.
- Performs all Brain replacements atomically under expected hashes, validates provenance and the complete Brain, refreshes Graphify and search within the same rollback boundary, and commits only the exact Brain paths through the vault-local Hermes identity.
- Snapshots the last usable Graphify/search publications and restores them on write, provenance, graph, reindex, or validation failure.
- Never invokes a model, writes Agentic OS code, pushes, or takes an external action.

## Context Assembler v2 real proofs

### Relationship-dependent one-hop Graphify and actual reads

Command, exit `0`:

```bash
.venv/bin/python tools/context_assembler.py assemble --surface step78-proof \
  'For AOS-2026-0174, explain the relationship and consequence.' \
  > /tmp/step78-graph.json
```

Focused result:

```text
retrieval_hierarchy = explicit_pointer -> graphify_one_hop -> exact_search -> direct_canonical_fallback
whole_vault_default = false
source_discovery_token_usage = {model_invocations: 0, input_tokens: 0, output_tokens: 0}
total_bytes = 40,545
total_tokens = 8,564
actual_read_count = 10
graph actual read = business_brain:prospects/2026-07-talent-harbour-loretta-davis.md
route = graphify
canonical content sha256 = 122343ea7a43dcc7529ddf2a5647b05faa19d21f9d5e79ed2480632644a2d01c
```

The request supplied only the queue ID and relationship need. Graphify supplied the one-hop canonical prospect target; the assembler read that canonical note and recorded the actual read. The other reads were the three required canonical operating blocks, two relevant queue/activity records, one relevant session journal, `open_loops.md`, and two relevant current commitments. There was no graph-body authority or vault scan.

### Episodic recency, open loop, and current commitment

Command, exit `0`:

```bash
.venv/bin/python tools/context_assembler.py assemble --surface step78-proof \
  'Where should I focus and why? Include the latest Loretta Davis session outcome, open loop, and current commitment AOS-2026-0482.' \
  > /tmp/step78-focus.json
```

Focused result:

```text
total_bytes = 49,920
total_tokens = 10,620
actual_read_count = 9
canonical entity = Loretta note, sha256 122343ea7a43dcc7529ddf2a5647b05faa19d21f9d5e79ed2480632644a2d01c
episodic activity = queue/work_items.jsonl#AOS-2026-0482
episodic recency = sessions/2026-08-04_hermes-cli_4fae0ae7ed76.md and sessions/2026-08-04_hermes-cli_2b590acc5677.md
open loop = operating_context/open_loops.md, sha256 86a9fcfde3942bdeed6643f9ca66499bdc689fdd23774100c52074cee6702755
current commitment = queue/work_items.jsonl#AOS-2026-0482
whole_vault_default = false
source discovery model/input/output tokens = 0/0/0
```

This is the smallest useful canonical context for that request: one prospect, one matching activity item, two bounded historical turns, one open-loop note projected to relevant bullets, and one active commitment, plus the three always-required operating notes. No soft-budget warning fired and nothing required for understanding was omitted.

### Exact-search route and two-client isolation

Command, exit `0`:

```bash
.venv/bin/python -m unittest -v \
  tests.test_step7_8_context_hygiene.ContextAssemblerV2Tests
```

Focused result: `2 tests`, `OK`. The production `ScopedBrainLoader` fixture contains distinct Client A/Client B sentinels in canonical notes, Graphify targets, exact-search rows, queue activity/commitments, session journals, and open loops. A Client A relationship query returned all four Client A evidence classes and no `CLIENT-B-` sentinel. The exact phrase query returned only the Client A search result with route `search`. Scope resolution ran before every result construction and default-denied cross-client identities.

### Worker pack propagation

Command, exit `0`:

```bash
tmpdir=$(mktemp -d /tmp/step78-worker-pack.XXXXXX)
STEP78_PACK_DIR="$tmpdir" .venv/bin/python <bounded worker_context_pack proof>
```

Focused result:

```text
item = AOS-2026-0482
bytes = 57,643
assembled tokens = 11,832
sha256 = 680178a26fd27c9b0617d35344e4410d8519141c712debc913c27e7f82056846
Evan operator correction present = true
canonical Evan pointer present = true
Hermes transcript included wholesale = no
```

## Nightly real proofs

### Exact dry-run, no mutation

Command, exit `0`:

```bash
.venv/bin/python tools/nightly_knowledge_hygiene.py --dry-run
```

The first live-state dry-run planned exactly:

```text
changed paths = inbox/contradictions.md, operating_context/open_loops.md
staleness findings = 8
contradiction resolutions = 1
session candidates = 0
contradictions expected sha256 = b74d20270e64c3a8f0e7d1b7ecb6f6d2bf54c8eeba1393fc3610a1e042126e0a
open_loops expected sha256 = df924906cdb1731287b43f66ee2d8fc1a6c780ed2758e25f8bfbba04c490f496
status = dry_run
mutated = false
model/input/output tokens = 0/0/0
external actions = 0
```

After that reconciliation, the final closure dry-run planned exactly one note and still did not mutate:

```text
changed paths = operating_context/open_loops.md
change = Revenue Gate completion before Step 4, evidence proofs/unbound-hermes-one-brain-2026-08-04/REVENUE_GATE.md
expected sha256 = 9b085aad4784fb88a374435f8d0435eeb20d17576aaa29b7d1a0db5269d7495d
candidate sha256 = d2d12e8f9dc5abae474fe3551799330075cb5346962ba17a5c9b55e5cdfd9e5e
status = dry_run
mutated = false
```

### Real safe fold/reconciliation through the production path

Commands, exit `0`:

```bash
.venv/bin/python tools/nightly_knowledge_hygiene.py
.venv/bin/python tools/nightly_knowledge_hygiene.py
```

The first production transaction moved Evan's already-confirmed classification contradiction from Open to Resolved, wrote eight deterministic stale-prospect findings to the open-loop operating note, validated the Brain, rebuilt Graphify/search, and created this exact-path vault commit:

```text
commit = 6aa38ba0009f96088e956515bff1a048ed370720
author = Hermes <hermes@local.ttros>
subject = hermes: nightly-knowledge-hygiene-2026-08-04
paths = inbox/contradictions.md, operating_context/open_loops.md
```

The bounded production-path test additionally folded one verified durable fact into its exact canonical note and one interpretation into `executive_view.md`, retained the session journal, deferred a formal commitment, created a Hermes-authored exact-path Git commit, refreshed Graphify/search, and produced no duplicate on rerun.

The final live transaction reconciled the obsolete pre-Step-4 release loop only after reading the explicit Revenue Gate PASS verdict. It retained the Loretta invitation, Evan email, and Evan authoritative-classification predicates until their own authoritative conditions resolve:

```text
commit = a5fecb3fbefb66e5151ddbd8a81572f0943df4aa
author = Hermes <hermes@local.ttros>
subject = hermes: nightly-knowledge-hygiene-2026-08-04
paths = operating_context/open_loops.md
```

Current canonical hashes:

```text
inbox/contradictions.md = 64526aa6d837e63e2902a254217742b776b59ed2adcbe25b47a13595525ab038
operating_context/open_loops.md = 86a9fcfde3942bdeed6643f9ca66499bdc689fdd23774100c52074cee6702755
```

### Idempotency

The unchanged rerun returned:

```text
status = unchanged
mutated = false
changed_paths = []
commit = null
planned_graph_action = none_fresh
planned_search_action = none_fresh
graph before = graph after
search before = search after = b9ce0c69bb211bbc3098c0d198a219791f768c6c55f60025455a9e1e0c4ee7f6
```

The real scheduler route was then invoked, exit `0`:

```bash
hermes cron run e5638ac27359
hermes cron list
```

Focused output:

```text
Ran now: succeeded.
Schedule: 30 2 * * *
Deliver: local
Mode: no-agent
Last run: 2026-08-04T14:50:32.459420+01:00 ok
Next run: 2026-08-05T02:30:00+01:00
```

This scheduler invocation was another unchanged no-op. It invoked no model and delivered nothing externally.

### Failure injection and rollback

Command, exit `0`:

```bash
.venv/bin/python -m unittest -v \
  tests.test_step7_8_context_hygiene.NightlyHygieneTests
```

Six injected production-path failures were proved: `expected_hash`, `write`, `provenance`, `graphify`, `reindex`, and `validation`. Expected errors were `ConcurrentEditError`, two `BrainMemoryError` cases, `BusinessBrainGraphError`, and two `NightlyHygieneError` cases. For every case:

```text
Brain byte manifest before = after
vault HEAD before = after
Graphify publication hashes before = after
search database sha256 before = after
Graphify status after failure = fresh
partial folded knowledge = 0 paths
partial Git commit = none
```

Representative fixture publication hashes preserved across failure:

```text
graph.json = ac7c0d6b11449cdcfd5555933b6071393b239884d7b4492276fbfa20c5da4274
projection_manifest.json = bb0ce43d76c3ee3fa408daed03253e5794a396a58c2d67a26ce82765dee46bfd
source_manifest.json = ca0787b3f4d19701103c5f2fac354ea623e40142ae859ebfa5ea74ebfd2b863d
vault manifest = bd3cbe00cc2318a795173e947b28d910fbcaef4a943023e3f34b0bedd34a8eac
```

The first live transaction also encountered a real validation failure: an untracked point-in-time `TTROS_HANDOFF_2026-08-04.md` lacked canonical frontmatter/navigation. The transaction rolled back the two candidate notes, Git index/HEAD, Graphify, and search byte-for-byte. The validator was repaired with the narrow existing-naming-contract exemption for `TTROS_HANDOFF_` notes; human-authored content was not edited. The same production transaction then passed.

### Graphify freshness and previous-publication preservation

Final published files:

```text
graph.json = e171893fe067c74dfeee6de640e63e7755ff90dcc4f3dbb6d4d407a3c12aaf66
projection_manifest.json = 5082f34006f5d643d4cb748f65a6e52ebd210f1c61bc14273d456e29c5d5d6fd
source_manifest.json = 58ab8432adaa0efd61e5b4057e980d8534e076bfcbaf54718841af27b9b3b2d1
Graphify status = fresh
trusted = true
status source-manifest digest = 365ad30c18f3897270ee20ada5d4287db49d66ec3a64d9da73f707f050b0e46b
search/os_index.db = b9ce0c69bb211bbc3098c0d198a219791f768c6c55f60025455a9e1e0c4ee7f6
```

A deliberately missing Graphify executable and a pre-publication search failure both left the prior usable publication intact. The final unchanged run performed neither rebuild nor reindex.

## Week-of-use readiness chain

No claim is made that a calendar week elapsed. The complete chain was exercised now:

1. Evan's operator correction is a vault-Git-audited fact in `business_brain:prospects/2026-07-highway-99-evan-thompson.md` (SHA-256 `23197f6ce1bce384c59ea2cf6a62ff80f344ac13036009e9cd6f6c67e59a126f`).
2. Assembler v2 retrieved that canonical note and actual-read provenance across the live operator surface.
3. The AOS-2026-0482 Revenue worker pack included the correction and canonical pointer (57,643 bytes; SHA-256 `680178a26fd27c9b0617d35344e4410d8519141c712debc913c27e7f82056846`).
4. Deterministic brief command, exit `0`:

   ```bash
   .venv/bin/python tools/aos_executive_brief.py \
     --now 2026-08-04T14:55:00Z --format json > /tmp/step78-brief.json
   ```

   Result: 87 findings; Loretta Davis, Evan Thompson, and AOS-2026-0482 were present; discovery tokens were `0/0/0`; artifact SHA-256 was `4666da00c37c4afa360d748438ede3a6a3cfd0b8de8f300c8eb8c7a2b5e79d3a`.
5. A real local Hermes operator-lean consultation answered “Where should I focus and why?” by prioritising AOS-2026-0482, Loretta first and Evan second, applying Evan's authoritative ICP-A MSP/technology-services correction instead of the older partner-adjacent interpretation, retaining both external decision gates, and citing canonical/brief provenance.

Exact Step 6 accounting for that model proof:

```text
invocation_id = hermes-step78-week-readiness
model = gpt-5.5
input = 19,064
output = 1,384
reasoning subset = 516
canonical total = 20,448
cost = $0.13684
fuse = 4.09%
threshold events = []
source-discovery model tokens = 0
```

Queue count and SHA-256 were identical before and after the discussion; no queue item, session commitment, send, publication, or external mutation was created.

## Validation and regression ledger

### Focused and affected integration suite

Final command, exit `0`:

```bash
.venv/bin/python -m unittest \
  tests.test_one_brain_context \
  tests.test_step4_entity_relationships \
  tests.test_step5_morning_brief \
  tests.test_step6_cost_fuse \
  tests.test_step7_8_context_hygiene \
  tests.test_business_brain_graph \
  tests.test_business_brain_vault \
  tests.test_aos_search \
  tests.test_aos_executive_brief \
  tests.test_codex_context_repair \
  tests.test_aos_codex_policy \
  tests.test_unbound_runtime_drift \
  tests.test_telegram_conversational_routing \
  tests.test_aos_orchestration
```

Result: `Ran 141 tests in 45.715s — OK`. The validation environment initially lacked its declared dashboard dependencies; `.venv/bin/pip install -r dashboard/backend/requirements.txt` installed the pinned requirements, and the failed import module then passed `9/9` before the full green rerun.

Earlier standing suites, before the final narrow release-loop rule, also passed:

```text
tests.test_aos_queue + tests.test_aos_paths + dashboard.backend.test_composio_hermes: 311 tests, OK
Telegram + orchestration standing suite: 45 tests, OK
```

### Step 6 dial/fuse regressions

Command, exit `0`:

```bash
.venv/bin/python tools/verify_step6.py all
```

Result: accounting PASS, pricing PASS, coverage PASS, guards PASS, historical fixture PASS, Step 5 attribution PASS. Coverage includes the assembler, worker packs, queue/workbench dispatch, dashboard/sticky/Telegram surfaces, protected native runner, capture, reviews, and scheduled model work.

### Runtime, Brain, syntax, and Git integrity

Commands, all exit `0`:

```bash
.venv/bin/python tools/validate_unbound_runtime.py --status
.venv/bin/python tools/validate_unbound_runtime.py --dry-run
.venv/bin/python tools/validate_business_brain.py
.venv/bin/python -m py_compile tools/context_assembler.py tools/brain_memory.py \
  tools/nightly_knowledge_hygiene.py tools/validate_business_brain.py \
  tests/test_step7_8_context_hygiene.py \
  /home/liam/.hermes/profiles/aos-orchestrator/scripts/ttros-nightly-knowledge-hygiene.py
bash -n tools/aos-hermes-operator-lean.sh tools/aos-hermes-coordinator.sh
python3 -m json.tool context/client_scope_registry.json >/dev/null
git diff --check
git -C "$BRAIN" diff --check
git -C "$BRAIN" diff --cached --check
git -C "$BRAIN" fsck --full
```

Focused result:

```text
runtime status = PASS, 25/25 checks, global/default profile inspected = false
runtime dry-run = PASS, 25/25 checks
Brain = PASS, 46 canonical notes, unique/all IDs, zero broken links, two-hop reachability, Obsidian/backups valid
vault fsck = clean
repo/vault diff checks = clean
```

Vault-local Hermes commits are coherent. Agentic OS repository HEAD remains `1ec13b608fdcd66ed62052d28fe3b908d1ddfc97`; no Agentic OS commit or push occurred. No vault push occurred.

## Queue, protected boundaries, and external action result

Final queue baseline:

```text
queue/work_items.jsonl count = 475
queue/work_items.jsonl sha256 = 746fdea55682b9633a92ba3447b0304589e2cc9dca0f6ec3563a5c8652ee3228
```

Immutable canonical-object hashes all match the opening baseline:

```text
AOS-2026-0071 44d1d9ddacc2a6ea66f5e6e2ad64b342cdc253710e475482e1448ae560042eb0
AOS-2026-0073 b734109d3bd7f37da5825bb35d29c352d613deaa3a31a9a520fccef79ef880a2
AOS-2026-0074 4325bbc106076ce45d43d995c3e42c1f6bc2abcfc0b7793010f2e901cadd3ab8
AOS-2026-0075 3b88d3beb4ae7a074bb1331711dcbc28ee73e606959b0928da9fdfc9f22286bf
AOS-2026-0174 2df5abf2957a26da57992bc02f760dbf0c55c05a2dd9111e74375c3d37efe190
AOS-2026-0175 e92ff399f5fb59de8f9a7d8b3aab00e83a031a6ab12079a7b8d32f3615b0909c
```

`git status --short --` returned empty for `workspaces/north_shore_sales_coach/`, `connectors/telegram_bridge/`, `queue/command_routes.json`, `queue/model_routes.json`, `queue/lane_profiles.json`, and `.env`. Global/default Hermes profile was not inspected or changed. No credentials, secrets, tokens, authentication files, legacy runtime/Graphify location, route table, or protected client workspace was changed.

External-action result: **zero**. No email send, LinkedIn action, CRM/Calendar/Drive mutation, deployment, publication, payment, credential change, destructive deletion, external recurring job, Agentic OS commit/push, or vault push occurred. The local nightly scheduler job is the requested existing Step 8 scheduler path; it has local delivery and no-agent execution.

## Defects found and repaired

- The old assembler accepted a nonexistent placeholder Brain pointer in a test; v2 correctly fails closed, and the fixture now uses the live Loretta canonical pointer.
- Full fresh morning-finding artifacts made ordinary contexts unnecessarily large; selection now projects request-relevant current findings without silently removing needed evidence.
- Search freshness compared against intentionally excluded or secret-content notes and caused unnecessary reindexes; freshness now applies the indexer's real exclusion rules.
- The first scheduler wrapper was installed outside the active profile's script directory; it was moved to the existing `aos-orchestrator` profile path and the real job rerun successfully.
- Brain validation treated point-in-time `TTROS_HANDOFF_` context as an ordinary canonical note; a narrow navigation exemption now matches its intended handoff semantics.
- The live open-loop note retained a Revenue Gate item after its explicit PASS proof. Nightly now reconciles that exact proven gate idempotently while retaining unresolved business decisions.

## Completion boundary

Context Assembler v2, nightly hygiene, real local paths, failure recovery, unchanged-rerun idempotency, Graphify/search freshness, Steps 0–6 regressions, protected boundaries, and the week-of-use readiness chain are green. The locked Unbound Hermes architecture build is complete. There is no Step 9.

Token usage: no agent invocation for deterministic assembler discovery, nightly hygiene, validation, or scheduling. Exact Codex harness token footer: unavailable.
