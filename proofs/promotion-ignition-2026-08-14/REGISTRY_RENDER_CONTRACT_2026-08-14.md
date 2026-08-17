# Registry render contract - promotion ignition

> Durable record for evidence identity `proof:promotion-ignition:registry-render-contract`.
> Established 2026-08-14. Read-only proofs; no Brain mutation occurred in establishing it.

The machine-maintained outcome index in `business_brain:index/MEMORY_INDEX.md`
(marker `block-2-outcome-index`) is rendered in full, every run, from the client scope
registry. `evidence_identities` is authoritative for membership and order;
`evidence_index_entries` supplies the rendered text. The renderer refuses to write when
the two disagree, and returns None rather than an empty block when nothing is registered.

| proof | established |
|---|---|
| Q1 production renderer reproduces the live file byte-for-byte | postimage sha `e0f12c34143579ba586eaccea7360f33c75f8457015b838ba792f9248784c4e8` |
| Q2 identities map 1:1 and in order to the rendered lines | 3 of 3 |
| Q3 dropped identity is refused | negative control passed |
| Q4 reordered entries change the whole-file sha | negative control passed |
| R1 unmodified registry validates against the extended schema | no broken window |
| R4 render sourced solely from the registry is byte-identical | circularity closed |
| R5 order mismatch refused | negative control passed |
| R6 malformed entry rejected by schema | negative control passed |
| S1 render from the file as installed on disk is byte-identical | production path |
| V6 nested vault-lock acquisition would deadlock; lock is released | proved non-blocking |
| V7 empty registry renders None, not an empty block | erasure hazard controlled |

`safe_for_broad_receipt` stays True: `PromotionWriter` does not commit, `MEMORY_INDEX.md`
is never in hygiene's `plan.documents`, and hashes are one-way - so the receipt `.patch`
is the only byte-level record of what a promotion changed.

Transcripts: `TTROS Reviews/ttros_ignition_p1_render.txt`,
`ttros_ignition_backfill_{report,apply}.txt`, `ttros_ignition_postinstall.txt`,
`ttros_ignition_step3a_*.txt`, `ttros_ignition_chunk1_*.txt`.
