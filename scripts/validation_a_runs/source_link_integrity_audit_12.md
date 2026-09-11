# Source-Link Integrity Audit — 12 Validation A Candidates

Scope: provenance/source-link audit only. Does NOT assess candidate claim accuracy, does not
reopen Validation A, does not repair anything, does not touch B6/B7.

## Authoritative population

- File: `/home/liam/ttros_backups/indexsplit_2026-09-02/INDEX.md.preimage`
- SHA-256 verified: `587b12fdab3ac3fbfded7f4375bc9422f55cddf124f35046c1795ccde8a754e4` — **MATCH**
- 12 candidates derived in positional order from the preimage's "Compact durable knowledge
  candidates" section: items 1–6 = Liam intentions/preferences, items 7–12 = third-party
  statements/opinions. (Note: the current, post-2026-09-02-split `sources/historical_calls/MANIFEST.md`
  in the live vault lists a slightly different set — one Liam-intention item dropped, one extra
  third-party item added, referencing `[[memory/positioning]]`. That drift is out of scope for this
  audit; the preimage is the authoritative population per the task and was used exclusively.)

## Vault root

`/mnt/c/Users/Admin/Documents/A-Time to revenue/TTROS Business Brain/sources/historical_calls/`
(resolved via `tools/brain_memory.py` `VAULT_ROOT`). All 15 unique historical source wrappers
referenced by the 12 candidates exist at this location. Each wrapper was checked for exactly one
`<!-- TTROS:VERBATIM_SOURCE:BEGIN:<sha256> -->` … `<!-- TTROS:VERBATIM_SOURCE:END:<sha256> -->`
block (no concatenation across any of the 15 files), and the marker's inline SHA-256 was checked
against the `source_sha256` frontmatter field on each file — all matched.

## 12-row table

| # | Source(s) | Intended material present? | Provenance clear? | Classification | Brief evidence |
|---|---|---|---|---|---|
| 1 | `first-call-cci` (wrapper sha `bb23cd69…d71628`); `call-kenneth-after-first-cci` (`cecabece…991998`); `mike-knapp-july-21` (`47749fcf…dd58f`) | Yes | Yes | **SOUND** | first-call-cci: "we could build a pilot based upon that and then test that pilot on in the real world"; call-kenneth-after-first-cci: "break them out into a pilot project... to save time"; mike-knapp-july-21: niche/vertical-focus language ("the more you niche down... the easier it is to get sales"). |
| 2 | `first-call-cci`; `trent-july-9` (`3e0d9492…d3232`); `hermes-water-treatment-summary-trent` (`46ad2a29…dd4`) | Yes | Yes | **SOUND** | first-call-cci: "Human in the loop has to be a key part of it"; hermes-water-treatment-summary-trent: "Everything important would go through human review before be[ing sent]... Hermes would not be making final decisions or sending estimates by itself"; trent-july-9: invoice/estimate handling discussion. |
| 3 | `call-dr-kenneth-after-second-cci` (`5e0ee105…6bad`); `mike-knapp-july-21`; `trent-first-call` (`3a5aa564…665b0`) | Yes | Yes | **SOUND** | call-dr-kenneth-after-second-cci: "it's a time saving and you can... estimate the hours"; mike-knapp-july-21: "It's great at administrative work... save time and build workflows"; trent-first-call: "if you eliminate an estimator position, an even administrative position." |
| 4 | `mike-knapp-july-21`; `mike-knapp-gtm-context-july-22` (`dd4ae9b7…867f62`) | Yes | Yes | **SOUND** | mike-knapp-july-21: "it's a huge differentiator to say I'm an AI enabled CTO for small and medium businesses"; mike-knapp-gtm-context-july-22: "The strategic AI-enabled CTO position is more differentiated..." alongside positioning/niche-selection framing. |
| 5 | `mike-knapp-july-21` (single source) | Yes | Yes | **SOUND** | "the more you niche down... the easier it is to get sales for that niche"; "If there's a specific vertical of business... you focus there." |
| 6 | `cci-second-call-june-15` (`eaf9e3f4…e1f3f`); `kenneth-sme-june-18` (`ac53ffc1…65fc4d`); `kenneth-june-30` (`ce389637…f21d5c`) | Yes | Yes | **SOUND** | cci-second-call-june-15: "there's going to be a cost to this, which I need to work out what budget"; kenneth-sme-june-18: "you're taking a risk... balance out your risk and reward"; kenneth-june-30: CCI "wanted to give me equity... not huge percentages," discussion of not doing 5–6 days/month unpaid. |
| 7 | `first-call-cci`; `cci-second-call-june-15` | Yes | Yes | **SOUND** | first-call-cci: "our sweet spot is food and beverage... top 100 food and beverage companies in the UK," "par dot in Salesforce," "sales navigator," "outreach"; cci-second-call-june-15: verbatim "our ideal customer profile is food and beverage chemicals and pharma," plus Salesforce/Sales Navigator references. |
| 8 | `call-kenneth-after-first-cci`; `call-dr-kenneth-after-second-cci` | Yes | Yes | **SOUND** | call-kenneth-after-first-cci: "overlay AI solution... to improve the efficiency," "personalized... targeted approach to the potential client"; call-dr-kenneth-after-second-cci: "save you 10% on waste and 5% improvement on OEE, or this efficiency... if your pilot can show." |
| 9 | `mike-knapp-july-21` (single source) | Yes | Yes | **SOUND** | "if you could take your skills to a managed service provider..."; "one of my clients is a $5 million MSP"; niche-testing language shared with items 4/5. |
| 10 | `meeting-ken-stanick` (`6ea8b3e6…f965a`) | Yes | Yes | **SOUND** | Verbatim transcript body (post-`BEGIN` marker, distinct from the wrapper's own "Selective discovery note" summary line, which was excluded as evidence): "If you can show them that they're going to return Revenue very quickly or that there's a real pain point"; "it's really about building trust"; Quinn/platform framed as Ken's own thesis ("we've been trying to build an AI chief Revenue officer"). |
| 11 | `andrea-roberts-june-26` (`cd41f23c…af7c`); `andrea-second-call-june-30` (`039a4f95…73234`) | Yes | Yes | **SOUND** | andrea-roberts-june-26: full transcript is the Ken Stanick introduction offer ("if you want an introduction to Ken, just let me know and I'll just do an email introduction"); andrea-second-call-june-30: "I'll introduce you to Ken," "he is an AI consultant looking to expand his network." |
| 12 | `trent-first-call` (`3a5aa564…665b0`); `trent-july-9` (`3e0d9492…d3232`) | Yes | Yes | **SOUND** | Both name Lance directly and discuss water-treatment operations automation (estimating, dispatch, emails); trent-first-call: "if Lance is going to be the business owner..."; trent-july-9: "reaching out to companies introducing West Coast water treatment," "creating the emails and then sending a message to Lance." No independent Lance-side confirmation appears in either transcript — consistent with the candidate's own caveat. |

Wrapper hashes above are SHA-256 of the resolved `.md` file as stored in the vault (whole file,
computed independently via `sha256sum`), used to pin exactly which bytes were inspected. All 15
files' internal `source_sha256` frontmatter values were separately cross-checked against their
own `VERBATIM_SOURCE:BEGIN/END` markers and against the deterministic inventory tables in
`sources/historical_calls/MANIFEST.md` — all matched, no mismatches found.

## Totals

- SOUND: 12/12
- AMBIGUOUS_WRAPPER: 0/12
- WRONG_SOURCE: 0/12
- SOURCE_MISSING: 0/12

## Conclusion

1. **Is there a real source-link integrity defect in this 12-item historical set?**
   No. All 12 candidates resolve to the correct, existing historical source file(s); every
   resolved file's verbatim wrapper is a single, unconcatenated call/document block whose
   internal SHA-256 marker matches its declared frontmatter hash; and in every case the
   transcript body (not the wrapper's own summary annotation) contains material that
   corresponds to the specific person, date-context, and topic the candidate cites.

2. **If yes, which item numbers, and how?**
   N/A — no item is affected.

3. **Is there enough evidence to justify investigating whether repaired-B6 CONTEXT-MISSING
   results were affected?**
   **NO — source wrappers may be noisy, but this audit does not establish a B6 source-integrity
   problem.** No source-link, provenance, or wrapper-attribution defect was found in any of the
   12 items or their 15 underlying source files.

## Files touched

- Created: `scripts/validation_a_runs/source_link_integrity_audit_12.md` (this file)
- No other files created, edited, or written. No vault writes. No model/Hermes calls. No commit/push.
