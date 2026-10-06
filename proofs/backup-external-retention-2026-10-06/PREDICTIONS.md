# Predictions — written 2026-10-06 ~12:15 PDT, before any check below was run

Findings already established (live, before predicting):
- Sole scheduler: Windows Task Scheduler "TTROS Automated Backup", daily 18:00 PDT, wsl.exe -> tools/aos-linux-backup.sh. No systemd unit/timer, no cron.
- External My Passport = D: (/mnt/d). Newest external snapshot D:\TTROS_Backups\2026-07-31_0304, which copied the
  RETIRED Windows tree C:\...\Agentic OS Live (62 files). Nothing has written to D: since 2026-07-31. => external backup BROKEN.

Predictions:
P1 Test suite for the backup script (new tests): all pass; negative cases (missing external root, verify mismatch) return non-zero and write a "fail" receipt.
P2 Missing external root: run exits non-zero, no local snapshot is pruned, receipt status=fail.
P3 Real run via the Windows task: Task LastTaskResult = 0; new local snapshot + new D:\TTROS_Backups\<YYYY-MM-DD_HHMM>.
P4 External AgenticOSLive file count == new local snapshot file count (~7,000-7,100). BusinessBrain file count ~1,630 (incl .git).
P5 Independent checksum comparison (rsync -c dry run) between local snapshot and external AgenticOSLive: 0 differing files.
   Independent sha256 of 5 representative files (repo + brain) matches live source.
P6 Negative rehearsal of P5 detector: tampering 1 byte in a scratch copy yields >=1 differing file.
P7 Local snapshots: before = 77 (78 once the manual test run lands), after = exactly 7. du before ~14G, after ~1.5G (7 x ~216 MB).
P8 .ignore still present; `rg --files ~` and `fdfind . ~` list 0 paths under agentic-os-backups.
