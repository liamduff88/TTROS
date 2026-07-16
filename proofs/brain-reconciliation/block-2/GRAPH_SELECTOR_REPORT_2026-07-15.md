# Scoped Graphify selector report — Block 2

Status: **PASS**

The source change was detected as stale before refresh. A stale query returned no graph target and an explicit fallback state. The failure-preserving publisher then refreshed `ttros-business-brain` from 18 permitted global sources; the denied protected-client source is absent from `source_manifest.json`. Projection bodies are disabled.

Current artifact hashes are graph `4e738a77b763a6564e867266bd7769d545b912a78094800b8504a6e406eef6e6`, projection manifest `272625c5324235a9da5017dd226b49181d73ea9bf34362a635741eab078a6793`, and source manifest `ea49c31b3118fabc9efda3845733ca4f8019fac05819660b237d837c8afcd607`. Receipt: `20260715T184623465588Z-build-success.json`.

Unchanged repeat publication preserved all hashes and emitted `20260715T184624120238Z-unchanged-success.json`. Injected extractor failure preserved the published hashes and emitted `20260715T184652509620Z-build-failed.json`. The pre-refresh published set remains in namespace history.

Scoped query returned only `{path: business_brain:index/MEMORY_INDEX.md, score: 4.0}`. A fresh loader process separately opened it through the shared scope gate and recorded route `graphify`; suggested but unread targets were not recorded. Raw Graphify artifacts may retain a link identity mentioned by an allowed index note, but the denied note is not a source and cannot be returned or opened because target authorization is exact and default-deny.

Pass 10 intake, repo graphs, receipts, and history hashes are unchanged.

Token usage: no agent invocation
