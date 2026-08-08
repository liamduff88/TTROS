# Executive Team consultation runtime evidence
> Point-in-time proof · Created: 2026-08-01.

Six bounded records were appended to the existing `logs/token_usage.jsonl`
store at lines 452–457. No new audit service or receipt store was introduced.
The UI response exposes only profile/context labels, hashes, and byte counts;
it does not expose prompt or protected context bodies.

| Executive | Requested / actual profile | Fallback | Context | Invocation | Input | Cached | Output | Reasoning |
|---|---|---:|---|---|---:|---:|---:|---:|
| Hermes / Executive Coordinator | operator-lean / operator-lean | false | Executive Header only; 91 bytes; SHA-256 `0135f071423b335bfb5da315c8a0f2eb0c8828fa2f687bab279303100de26b8a` | `hermes-0244cefba56b4480a9851c766acb112e` | 1,330 | 0 | 290 | 42 |
| Revenue | aos-revenue / aos-revenue | false | named department profile | `hermes-1e521feb003f4587bc06d0031ebfa9c0` | 14,375 | 0 | 799 | 43 |
| Marketing | aos-marketing / aos-marketing | false | named department profile | `hermes-da534b357b3c4e2088496b002700ad72` | 14,154 | 0 | 386 | 58 |
| Delivery | aos-delivery / aos-delivery | false | named department profile | `hermes-349b5c385c624f6cb3c0c2b69a436ab4` | 14,218 | 0 | 697 | 61 |
| Operations | aos-ops / aos-ops | false | named department profile | `hermes-c40773a4055440b38b0db123aee61a3c` | 14,254 | 0 | 495 | 71 |
| Executive Team | aos-orchestrator / aos-orchestrator | false | full Executive Brief; 7,073 bytes; SHA-256 `c2676b15d4c1debbeb007c5a59872a080f69cd55dd02a2ad4d46b409353150c6` | `hermes-69ccb326805d458094664dd4a239987f` | 16,050 | 0 | 1,851 | 54 |

Consultation totals: input 74,381; cached input 0; fresh input 74,381;
output 4,518; reasoning 329; input plus output 78,899. Provider/model
reported for every run: `openai-codex` / `gpt-5.5`.

Browser screenshots prove the permanent surface, department result,
orchestrator result, profile/context evidence, and deterministic honest 503
rendering without a backend or model call.
