# Result — 2026-10-06 (scored against PREDICTIONS.md, which was written first)

Verdict: PASS.

| # | Prediction | Observed | |
|---|---|---|---|
| P1 | new tests pass; negative cases fail closed | 28 passed (3 new + capture contract); 6 dashboard backup tests passed | met |
| P2 | missing external root -> non-zero, nothing pruned, fail receipt | test_unplugged_drive_fails_and_prunes_nothing | met |
| P3 | Windows task result 0, new local + external snapshot | LastTaskResult=0; agentic-os-20261006T192055Z + D:\TTROS_Backups\2026-10-06_1220 | met |
| P4 | external repo count == local (~7,000-7,100); Brain ~1,630 incl .git | 7066==7066 (run1), 7070==7070 (run2); Brain working files 222==222, .git copied (total not re-counted) | met |
| P5 | 0 differing files; representative sha256 match live | 0 differing (sha256, independent of rsync), 8/8 MATCH, restored Brain fsck OK at live HEAD b695733 | met |
| P6 | tamper -> >=1 difference | 2 differing lines; tampered file DIFF; verifier unit test also catches a corrupted copy | met |
| P7 | 77 -> 7; ~14G -> ~1.5G | 77 (+2 runs) -> 7, 72 pruned; 13,460,654,898 B -> 1,487,091,580 B | met |
| P8 | .ignore present; home-wide rg/fd see 0 backup paths | .ignore = "*\n"; rg --files ~ -> 0 (negative: --no-ignore sees them); fd not installed | met (rg only) |

What this licenses: the external drive now holds current, checksum-verified, restorable copies of
/home/liam/agentic-os-live (minus the declared exclusions) and the Business Brain vault (incl .git), produced by the
production scheduled-task command line. It does not prove behaviour on a day the drive is unplugged beyond the unit test.

Design note: local pruning runs only after BOTH the local snapshot and the external copy verify. While the drive
is failing, local snapshots are kept (and the receipt/dashboard shows "failed") instead of being cut to 7.
External snapshots are never pruned by this script.
