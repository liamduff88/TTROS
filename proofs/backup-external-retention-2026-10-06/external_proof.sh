#!/usr/bin/env bash
# Independent (sha256, not rsync) restore/readability proof of one external backup. Read-only on live data.
set -uo pipefail
LOC="$1"; EXT="$2"; OUT="$3"
[[ -e "$OUT" && "${4:-}" != "--overwrite" ]] && { echo "refusing to overwrite $OUT" >&2; exit 2; }
BB="/mnt/c/Users/Admin/Documents/A-Time to revenue/TTROS Business Brain"
LIVE=/home/liam/agentic-os-live
S="$(mktemp -d "${TMPDIR:-/tmp}/extproof.XXXXXX")"
{
echo "== External restore/readability proof $(date -Is)"; echo "local=$LOC"; echo "external=$EXT"; ls -la "$EXT"; cat "$EXT/MANIFEST.txt"
echo "== 1. Full independent sha256: local snapshot vs external AgenticOSLive"
(cd "$LOC" && find . -type f -print0 | sort -z | xargs -0 sha256sum) > "$S/loc.sha"
(cd "$EXT/AgenticOSLive" && find . -type f -print0 | sort -z | xargs -0 sha256sum) > "$S/ext.sha"
echo "local_files=$(wc -l < "$S/loc.sha") external_files=$(wc -l < "$S/ext.sha") differing_lines=$(diff "$S/loc.sha" "$S/ext.sha" | grep -c '^[<>]')"
echo "== 2. Business Brain working files (excl .git): live vs external"
(cd "$BB" && find . -path ./.git -prune -o -type f ! -name '.env' ! -name '.env.*' -print0 | sort -z | xargs -0 sha256sum) > "$S/bbl.sha"
(cd "$EXT/BusinessBrain" && find . -path ./.git -prune -o -type f -print0 | sort -z | xargs -0 sha256sum) > "$S/bbe.sha"
echo "live_files=$(wc -l < "$S/bbl.sha") external_files=$(wc -l < "$S/bbe.sha") differing_lines=$(diff "$S/bbl.sha" "$S/bbe.sha" | grep -c '^[<>]')"
diff "$S/bbl.sha" "$S/bbe.sha" | head -6
echo "external Brain .git present: $(test -d "$EXT/BusinessBrain/.git" && echo yes || echo no)"
echo "== 3. Representative files: LIVE source sha256 vs external"
for f in CLAUDE.md AGENTS.md tools/aos-linux-backup.sh tools/aos_paths.py tools/aos_orchestration.py dashboard/backend/main.py; do
  a=$(sha256sum < "$LIVE/$f" | cut -c1-16); b=$(sha256sum < "$EXT/AgenticOSLive/$f" | cut -c1-16)
  echo "$([ "$a" = "$b" ] && echo MATCH || echo DIFF) $a $f"; done
for f in README.md .gitignore; do
  a=$(sha256sum < "$BB/$f" | cut -c1-16); b=$(sha256sum < "$EXT/BusinessBrain/$f" | cut -c1-16)
  echo "$([ "$a" = "$b" ] && echo MATCH || echo DIFF) $a BusinessBrain/$f"; done
echo "== 4. Current authoritative tree, not the retired Windows tree"
echo "contains in-progress AOS-0528 test file: $(test -f "$EXT/AgenticOSLive/tests/test_queue_operator_lifecycle.py" && echo yes || echo no)"
echo "contains today's retention line: $(grep -c '^KEEP_LOCAL=7$' "$EXT/AgenticOSLive/tools/aos-linux-backup.sh")"
echo "newest file mtime in external repo copy: $(find "$EXT/AgenticOSLive" -type f -printf '%TY-%Tm-%Td %TH:%TM\n' | sort | tail -1)"
echo "previous external (2026-07-31_0304) repo file count: $(find /mnt/d/TTROS_Backups/2026-07-31_0304/AgenticOSLive -type f | wc -l)"
echo "== 5. Restore into scratch ($S/restore), never over live, and use it"
R="$S/restore"; mkdir -p "$R/repo/tools" "$R/repo/queue/receipts"
cp -r "$EXT/BusinessBrain" "$R/BusinessBrain"
cp "$EXT/AgenticOSLive/tools/aos_paths.py" "$EXT/AgenticOSLive/tools/aos-linux-backup.sh" "$R/repo/tools/"
cp "$EXT/AgenticOSLive/queue/receipts/linux-backups.jsonl" "$R/repo/queue/receipts/"
python3 -m py_compile "$R/repo/tools/aos_paths.py" && echo "restored aos_paths.py compiles"
bash -n "$R/repo/tools/aos-linux-backup.sh" && echo "restored backup script parses"
python3 -c "import json,sys; print('restored receipts jsonl parses, records =', sum(1 for l in open(sys.argv[1]) if json.loads(l)))" "$R/repo/queue/receipts/linux-backups.jsonl"
if git -c safe.directory='*' -C "$R/BusinessBrain" fsck --no-progress >"$S/fsck.txt" 2>&1; then echo "restored Brain git fsck: OK"; else echo "restored Brain git fsck: issues"; head -5 "$S/fsck.txt"; fi
echo "restored Brain HEAD=$(git -c safe.directory='*' -C "$R/BusinessBrain" rev-parse --short HEAD) live Brain HEAD=$(git -C "$BB" rev-parse --short HEAD)"
echo "restored Brain working tree vs its own HEAD: $(git -c safe.directory='*' -C "$R/BusinessBrain" status --porcelain | wc -l) changed paths"
echo "== 6. Negative rehearsal of the sha256 comparison"
cp "$S/ext.sha" "$S/ext_tampered.sha"; sed -i '100s/^./0/' "$S/ext_tampered.sha"
cp "$EXT/AgenticOSLive/AGENTS.md" "$S/neg_AGENTS.md"; printf x >> "$S/neg_AGENTS.md"
echo "tampered manifest differing_lines=$(diff "$S/loc.sha" "$S/ext_tampered.sha" | grep -c '^[<>]')"
echo "tampered file vs live: $([ "$(sha256sum < "$S/neg_AGENTS.md" | cut -c1-64)" = "$(sha256sum < "$LIVE/AGENTS.md" | cut -c1-64)" ] && echo MATCH || echo DIFF)"
echo "scratch=$S"
} 2>&1 | tee "$OUT"
