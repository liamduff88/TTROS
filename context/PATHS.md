# Agentic OS Path Convention
> Revisit: when the canonical runtime root or mount policy changes. · Last touched: 2026-07-11.

- `/home/liam/agentic-os-live` is the canonical live installation.
- `AOS_ROOT` is the portable runtime root contract; code defaults from its repository location.
- Code should resolve runtime files from `AOS_ROOT` or root-relative paths.
- Authoritative mutation is Linux/POSIX-only on a Linux-native filesystem.
- `/mnt/c`, other Windows drive mounts, NTFS/DrvFS/9p/fuseblk roots, native Windows Python, and Windows APIs are unsupported for queue, package, receipt, artifact, runner, dashboard, and orchestration mutation.
- The old `/mnt/c/Users/Admin/Documents/A-Time to revenue/Agentic OS Live` tree is a frozen rollback snapshot.
- Windows may only invoke the Linux launcher and open the Linux-hosted dashboard.
- Secrets stay outside git and are re-provisioned during migration.
