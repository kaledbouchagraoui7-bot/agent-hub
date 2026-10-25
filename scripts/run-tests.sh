#!/usr/bin/env bash
# Run every suite in the hub and FAIL LOUDLY if any of them fails.
#
# Two rules this script exists to enforce:
#   1. `set -o pipefail` - without it, `python3 -m unittest | tail` returns tail's
#      status and a failing suite reports success. That bug shipped once already.
#   2. The summary is taken from unittest's own output, not from whatever the last
#      four lines happen to be (some suites print JSON to stdout).
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fail=0
total=0

run() {
  name="$1"; dir="$2"; shift 2
  echo
  echo "=============================================================="
  echo "  $name"
  echo "=============================================================="
  out="$(cd "$ROOT/$dir" && python3 -m unittest discover "$@" 2>&1)"
  rc=$?
  echo "$out" | grep -E "^(Ran [0-9]+ tests|OK|FAILED|ERROR)" || true
  n="$(echo "$out" | sed -n 's/^Ran \([0-9]\+\) test.*/\1/p' | tail -1)"
  [ -n "$n" ] && total=$((total + n))
  if [ "$rc" -ne 0 ]; then
    echo "  !! $name FAILED (rc=$rc)"
    echo "$out" | grep -A 12 -E "^(FAIL|ERROR):" | head -40
    fail=1
  fi
}

run "trader-agents   (12 skills, incl. trader-labs)" "trader-agents"     -s tests
run "trader-skill    (11 v1 skills)"                 "trader-skill"      -s tests
run "trader-console  (16 agents wired)"              "trader-console"    -s . -p test_console.py
run "obsidian-datafarm (graph + probe)"              "obsidian-datafarm" -s tests

echo
echo "=============================================================="
find "$ROOT" -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null
if [ "$fail" -eq 0 ]; then
  echo "  ALL SUITES PASSED   ($total tests)"
else
  echo "  FAILURE - see above ($total tests ran)"
fi
echo "=============================================================="
exit "$fail"
