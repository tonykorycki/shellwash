#!/usr/bin/env bash
# Run every shellwash test suite. Used by CI and by hand:  bash tests/run.sh
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
rc=0

echo "── python: fetch parsers + logos ─────────────────────────────────"
python3 -m unittest discover "$ROOT/tests" -v 2>&1 | tail -3 || rc=1

echo
echo "── zsh: battery chip ─────────────────────────────────────────────"
# A zsh script dies outright on some errors (an unmatched glob, for one), so
# a suite that exits without printing its summary must count as a failure —
# checking only the exit code would let a silent abort look like a pass.
out="$(zsh "$ROOT/tests/test_prompt.zsh" 2>&1)"; zrc=$?
echo "$out" | tail -3
if (( zrc != 0 )) || ! grep -q "0 failed" <<<"$out"; then
  echo "  !! zsh suite failed or aborted before finishing (exit $zrc)"
  rc=1
fi

echo
(( rc == 0 )) && echo "ALL SUITES PASSED" || echo "FAILURES — see above"
exit $rc
