# Agentic OS Path Convention
> Revisit: when the canonical runtime root or mount policy changes. · Last touched: 2026-07-23.

- `/home/liam/agentic-os-live` is the canonical live installation.
- `AOS_ROOT` is the portable runtime root contract; code defaults from its repository location.
- Code should resolve runtime files from `AOS_ROOT` or root-relative paths.
- Authoritative mutation is Linux/POSIX-only on a Linux-native filesystem.
- `/mnt/c`, other Windows drive mounts, NTFS/DrvFS/9p/fuseblk roots, native Windows Python, and Windows APIs are unsupported for queue, package, receipt, artifact, runner, dashboard, and orchestration mutation.
- The old `/mnt/c/Users/Admin/Documents/A-Time to revenue/Agentic OS Live` tree is a frozen rollback snapshot.
- Windows may only invoke the Linux launcher and open the Linux-hosted dashboard.
- Secrets stay outside git and are re-provisioned during migration.
- `/home/liam/agentic-os/hermes/hermes.py` is a real router script that
  `~/.local/bin/aos-hermes` execs into. It lives outside this repo — it is
  not tracked by this repo's git, not covered by this repo's test suite,
  and edits to it are invisible to `git diff`/`git log` here. It carries the
  PERMISSION MODE dedup logic (2026-07-23, see DECISIONS.md): it only wraps
  a bare task in the "PERMISSION MODE — SCOPED LOCAL TASK APPROVED" header
  when the incoming task doesn't already start with that header, so a
  queue-assembled prompt isn't double-wrapped. A pre-edit backup is kept
  alongside it at `/home/liam/agentic-os/hermes/hermes.py.bak-2026-07-23`.
