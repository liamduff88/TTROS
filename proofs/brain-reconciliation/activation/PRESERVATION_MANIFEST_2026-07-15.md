# Phase 6B preservation manifest
> Expires: when this activation proof is superseded. · Last touched: 2026-07-15.

Result: **PASS**.

Preflight authorities:

- HEAD/main/origin-main: `8b26010772196c448e01fae4dacfbe4ef9106c4b`.
- Unrelated dirty hashes: decisions `78f0563c788c982138c01587f8670f0fb9ae136796e9aae18ee9471369b86ad2`; orchestration test `9a4ee82b8b5802d2d1ce803d8b76fdd69755ff9be82c780fe72cca1b0aa52e7d`; Linux runtime script `ba78638fe7db6eb69a973cf79aed15fb3a84f1d0d41a0d4506b7d05748b49183`; dashboard cleanup test `3a8bf7b7169435ea5549614d62b5d738d0b26ed1d8ba785b69a0d71a2cd74a82`.
- Accepted Block 1 aggregate: `f2d1596ebab16387db4aa6832a93b2bff2fe05ca5429f72a7acb67e7abdf2cd7`.
- Accepted Block 2 aggregate: `103dfed5dd69cdd9560d614523af7f22cd6cf4d5bf102bda26e94a5c6bb28304`.
- Accepted Block 3 aggregate excluding the pre-existing duplicate copy: `e4561c2a5805be057a41edc9fd49ec288db98887acfebcc44ced4680673053d4`.
- Business Brain accepted aggregate: `2c6b1d8297542c2c61ef9ad8eb8903c64a3ffa4eff95e39b5b7a20fcdb05d72d`; accepted 29-row manifest has zero hash mismatch.
- Accepted Brain graph/source/projection hashes: `4e738a77b763a6564e867266bd7769d545b912a78094800b8504a6e406eef6e6`, `ea49c31b3118fabc9efda3845733ca4f8019fac05819660b237d837c8afcd607`, `272625c5324235a9da5017dd226b49181d73ea9bf34362a635741eab078a6793`.
- Pass 10 intake/repo-graphs/receipts manifests: 64/56/2 rows, zero mismatch and zero extra/missing files.
- Historical queue/run/token prefixes: 93/21/82 lines, preserved byte-for-byte.
- Historical receipt set: 153 files, preserved byte-for-byte.
- Immutable item canonical hashes: 0071 `44d1d9ddacc2a6ea66f5e6e2ad64b342cdc253710e475482e1448ae560042eb0`; 0073 `b734109d3bd7f37da5825bb35d29c352d613deaa3a31a9a520fccef79ef880a2`; 0074 `4325bbc106076ce45d43d995c3e42c1f6bc2abcfc0b7793010f2e901cadd3ab8`; 0075 `3b88d3beb4ae7a074bb1331711dcbc28ee73e606959b0928da9fdfc9f22286bf`.

The canonical Brain validator remains PASS: 19 notes/IDs, zero broken links, backups excluded. Capture runtime remains ignored, untracked, owner-only (`0700` directories, `0600` files). The accepted capture graph hash remains `ec00dc046a4c94b0bf07a0a012dd63e5ecda3d4b596585549b0e7078f2801f05`; only additive Graphify receipts were added. Search changed only through authorized failure-preserving metadata reindex.

Protected path interiors were not opened. Path-level protected Git status remains clean. No protected or unrelated file was staged, reverted, formatted, absorbed, committed, or pushed.

Token usage: no agent invocation.
