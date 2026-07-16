# Block 3 preservation manifest
> Expires: when the accepted Block 1/2 baseline changes. · Last touched: 2026-07-15.

Result: **PASS**.

Preflight/final values:

| Surface | Preserved evidence |
|---|---|
| HEAD/main/origin-main | `8b26010772196c448e01fae4dacfbe4ef9106c4b` |
| unrelated dirty: decisions | `78f0563c788c982138c01587f8670f0fb9ae136796e9aae18ee9471369b86ad2` |
| unrelated dirty: orchestration test | `9a4ee82b8b5802d2d1ce803d8b76fdd69755ff9be82c780fe72cca1b0aa52e7d` |
| unrelated dirty: runtime script | `ba78638fe7db6eb69a973cf79aed15fb3a84f1d0d41a0d4506b7d05748b49183` |
| unrelated dirty: cleanup test | `3a8bf7b7169435ea5549614d62b5d738d0b26ed1d8ba785b69a0d71a2cd74a82` |
| accepted Block 1 package aggregate | `f2d1596ebab16387db4aa6832a93b2bff2fe05ca5429f72a7acb67e7abdf2cd7` |
| accepted Block 2 package aggregate | `103dfed5dd69cdd9560d614523af7f22cd6cf4d5bf102bda26e94a5c6bb28304` |
| canonical Business Brain aggregate | `2c6b1d8297542c2c61ef9ad8eb8903c64a3ffa4eff95e39b5b7a20fcdb05d72d` |
| accepted Brain graph | `4e738a77b763a6564e867266bd7769d545b912a78094800b8504a6e406eef6e6` |
| accepted Brain source manifest | `ea49c31b3118fabc9efda3845733ca4f8019fac05819660b237d837c8afcd607` |
| accepted Brain projection manifest | `272625c5324235a9da5017dd226b49181d73ea9bf34362a635741eab078a6793` |
| Pass 10 intake | `6e7efed2469a7649576a5b67ddef5be75a924748ed12355969363d98e8b1a8a4` |
| Pass 10 repo graphs | `20109cb5e9f9b0ddcbc4e551b792889072a1e3f0ed6ce617ea692688c606017e` |
| Pass 10 receipts | `f19f880abe3982dcf616c2ada61434501dabec40ef2182bf23d3a5f2a6c47332` |
| historical work-item prefix | `a0405a9ae2c266b7f7292cc44dbc73f2d49157e554b06a2d178852a2d09c6bf6` |
| historical run-ledger prefix | `c6b52ed39baa6ba3a3b20a8cc5c9b48247cb09599c9c6282d7ed2b90e8a34e49` |
| historical token-ledger prefix | `0594c77b92cf9ae74dd025832d10e00cb83c7315f57801db9d9b10215aaa4561` |
| goal ledger | `7767aa855662d0148aa81a99818716d36b9339d42b8800fd1fab336beb3d6b7f` |

All 150 historical receipt files from the accepted Block 2 manifest passed
`sha256sum -c`. The three Block 2 promotion receipt/diff hashes remain
`603cc028a7445c11f64a6fa7602e5a9a0f8b7e08e76bed4b84ccb1f9f252bc13`,
`62c8779064f2d476dba52a0ad0dcf5684078a44961049afcc3a3fbef21539f1f`,
and `9eb4b6d816b7072ad912057bf47a68a44e4b98be5c8d79f9a1502baea2ede9b2`.
Immutable items 0071/0073/0074/0075 retain their preflight per-item hashes.
Protected interiors were not opened;
path-level Git status is empty. Vault validation remains 19 notes, 19 unique
IDs, zero broken links, backups excluded. Search changed only through the
authorized failure-preserving reindex. The accepted Brain graph files did not
change; the additive capture graph hash is
`ec00dc046a4c94b0bf07a0a012dd63e5ecda3d4b596585549b0e7078f2801f05`.
Search moved from preflight
`44c28dceeceb6035da0c0f74ec35f62a6a319e82bbc24f1cd73a42bec0171267`
to authorized post-reindex
`9764e1e842b7b8fb3063d2ff1f67d58c5c73a15477563c331b93eaeb379780b7`.
No Pass 10 file changed.

Token usage: no agent invocation.
