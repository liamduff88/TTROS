#!/usr/bin/env bash
# loop/verify-goals.sh — read-only standing goal verifier stub.
# Revisit: when a goal predicate changes or this stub is wired to a scheduler. · Last touched: 2026-07-07.
#
# Runs the six goals/*.goal.md predicates locally/read-only. It does not call
# connectors, send messages, mutate ledgers, trigger agents, or schedule itself.
# Exit 0 = all currently checkable predicates passed. Exit 1 = one or more
# predicates failed or were unverified.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FAIL=0

pass() { printf 'PASS\t%s\t%s\n' "$1" "$2"; }
fail() { printf 'VIOLATED\t%s\t%s\n' "$1" "$2"; FAIL=1; }
unverifiable() { printf 'UNVERIFIABLE\t%s\t%s\n' "$1" "$2"; FAIL=1; }

check_os_startup_health() {
  local g="os_startup_health.goal.md"
  ( cd "$ROOT" && test -f soul.md && test -f CLAUDE.md && test -f AGENTS.md && test -f CODEX.md && test -f ANTIGRAVITY.md && test -f ROT.md && test -f rules/always.md && test -f rules/never.md && test -d hooks && test -d goals ) \
    && pass "$g" "root identity/rules/hooks/goals present" \
    || fail "$g" "missing one or more required root files/directories"
}

check_business_brain_pointer_valid() {
  local g="business_brain_pointer_valid.goal.md"
  local brain="/mnt/c/Users/Admin/Documents/A-Time to revenue/TTROS Business Brain/_substrate.wiki/schema.md"
  test -r "$brain" && pass "$g" "schema readable at TTROS Business Brain" || fail "$g" "TTROS Business Brain schema not readable"
}

check_no_old_runtime_references() {
  local g="no_old_runtime_references.goal.md"
  local tmp
  local p1 p2 p3 p4 p5
  p1="C:"; p1+="\\AI-Vault"
  p2="AI Native Source"; p2+=" of Truth"
  p3="old"; p3+=" Ubuntu"
  p4="legacy"; p4+="_harvest"
  p5="Z"; p5+="PC"
  tmp="$(mktemp)"
  ( cd "$ROOT" && grep -rIl -e "$p1" -e "$p2" -e "$p3" -e "$p4" -e "$p5" . \
      --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=.venv --exclude-dir=venv --exclude-dir=dist --exclude-dir=build --exclude-dir=.next --exclude-dir=.cache \
      --exclude-dir=.venv-pdf --exclude-dir=archive --exclude-dir=legacy_harvest --exclude-dir=TTROS_Agentic_OS_fileset --exclude-dir=workspaces 2>/dev/null \
      | grep -v '^./goals/' \
      | grep -v '^./operating_context/old_vault_archive_plan\.md$' \
      | grep -v '^./loop/verify-goals\.sh$' \
      > "$tmp" )
  if test -s "$tmp"; then fail "$g" "legacy references outside allowed docs: $(tr '\n' ' ' < "$tmp")"; else pass "$g" "no disallowed legacy references found"; fi
  rm -f "$tmp"
}

check_queue_receipts_visible() {
  local g="queue_receipts_visible.goal.md"
  python3 - "$ROOT" <<'PY'
import json, pathlib, sys
root = pathlib.Path(sys.argv[1])
ledger = root/'queue/run_ledger.jsonl'
if not ledger.exists():
    print('PASS\tqueue_receipts_visible.goal.md\tqueue/run_ledger.jsonl absent; no done-transition to verify')
    raise SystemExit(0)
missing=[]
for n,line in enumerate(ledger.read_text(encoding='utf-8').splitlines(),1):
    if not line.strip(): continue
    try: row=json.loads(line)
    except Exception as e:
        print(f'UNVERIFIABLE\tqueue_receipts_visible.goal.md\tinvalid JSON line {n}: {e}')
        raise SystemExit(2)
    status = str(row.get('status') or row.get('to_status') or row.get('transition_to') or '').lower()
    if status == 'done':
        receipt = row.get('receipt_path') or row.get('receipt') or row.get('receipt_file')
        if isinstance(receipt, dict): receipt = receipt.get('path')
        if not receipt or not (root/str(receipt)).exists(): missing.append(f'line {n}: {receipt or "missing receipt_path"}')
if missing:
    print('VIOLATED\tqueue_receipts_visible.goal.md\t' + '; '.join(missing)); raise SystemExit(1)
print('PASS\tqueue_receipts_visible.goal.md\tdone transitions have existing receipt paths')
PY
  case $? in 0) ;; *) FAIL=1 ;; esac
}

check_token_ledger_current() {
  local g="token_ledger_current.goal.md"
  python3 - "$ROOT" <<'PY'
import json, pathlib, sys
root=pathlib.Path(sys.argv[1]); p=root/'queue/token_ledger.jsonl'
if not p.exists():
    print('UNVERIFIABLE\ttoken_ledger_current.goal.md\tqueue/token_ledger.jsonl missing'); raise SystemExit(2)
lines=[l for l in p.read_text(encoding='utf-8').splitlines() if l.strip()]
if not lines:
    print('UNVERIFIABLE\ttoken_ledger_current.goal.md\tqueue/token_ledger.jsonl empty'); raise SystemExit(2)
try: json.loads(lines[-1])
except Exception as e:
    print(f'UNVERIFIABLE\ttoken_ledger_current.goal.md\tlast token ledger line invalid JSON: {e}'); raise SystemExit(2)
print('PASS\ttoken_ledger_current.goal.md\ttoken ledger has a parseable most-recent entry; active-session window check remains a harness responsibility')
PY
  case $? in 0) ;; *) FAIL=1 ;; esac
}

check_no_external_action_without_approval() {
  local g="no_external_action_without_approval.goal.md"
  python3 - "$ROOT" <<'PY'
import json, pathlib, re, sys
root=pathlib.Path(sys.argv[1]); p=root/'queue/run_ledger.jsonl'
verbs=re.compile(r'\b(send|write|publish|post|push|mutate|delete|archive|move|connect|grant|spend)\b', re.I)
if not p.exists():
    print('PASS\tno_external_action_without_approval.goal.md\tqueue/run_ledger.jsonl absent; no gated action to verify'); raise SystemExit(0)
viol=[]
for n,line in enumerate(p.read_text(encoding='utf-8').splitlines(),1):
    if not line.strip(): continue
    try: row=json.loads(line)
    except Exception as e:
        print(f'UNVERIFIABLE\tno_external_action_without_approval.goal.md\tinvalid JSON line {n}: {e}'); raise SystemExit(2)
    blob=json.dumps(row, sort_keys=True)
    if verbs.search(blob) and 'approved_external_action' not in row and 'approved_external_action' not in blob:
        viol.append(f'line {n}')
if viol:
    print('VIOLATED\tno_external_action_without_approval.goal.md\tgated verb without approved_external_action: ' + ', '.join(viol)); raise SystemExit(1)
print('PASS\tno_external_action_without_approval.goal.md\tno unapproved gated action found')
PY
  case $? in 0) ;; *) FAIL=1 ;; esac
}

check_os_startup_health
check_business_brain_pointer_valid
check_no_old_runtime_references
check_queue_receipts_visible
check_token_ledger_current
check_no_external_action_without_approval
exit "$FAIL"
