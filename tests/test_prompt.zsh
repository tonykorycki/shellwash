#!/usr/bin/env zsh
# Tests for the battery chip in linux/prompt.zsh — Linux sysfs and the macOS
# pmset path, both exercised on any platform via $AD_BAT_SYSFS and a stub
# pmset. Runs anywhere:
#
#     zsh tests/test_prompt.zsh
#
# The regression these exist for: ad_battery_pct keeps its 60s cache in
# globals, so calling it as "$(ad_battery_pct)" runs it in a subshell that
# throws the cache away and forks pmset on EVERY prompt. Test 2 pins that.

emulate -L zsh
# Deliberately NOT err_return: ad_battery_pct is called from precmd, so a
# nonzero return from it must never abort anything — and err_return here
# would turn an assertion failure into a silent abort with no output at all,
# which is worse than a red line. The return code is asserted explicitly
# instead (see rc0 below).
zmodload zsh/datetime

ROOT="${0:A:h:h}"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/shellwash-test.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT

PASS=0 FAIL=0
# Plain assignment, not (( PASS++ )): post-increment evaluates to the OLD
# value, so it reports "false" when the counter is 0 — and under err_return
# that aborts the function before it can return success, making every first
# assertion print both ok and FAIL.
ok()   { print -- "  ok    $1"; PASS=$(( PASS + 1 )); return 0; }
bad()  { print -- "  FAIL  $1"; print -- "        $2"; FAIL=$(( FAIL + 1 )); return 0; }
is()   { [[ "$2" == "$3" ]] && ok "$1" || bad "$1" "expected [$3], got [$2]"; }
# ad_battery_pct runs in precmd; a nonzero return would leak into the shell's
# error handling (and abort outright under err_return), so pin it at 0.
rc0()  { ad_battery_pct; local rc=$?
         (( rc == 0 )) && ok "$1 (returns 0)" || bad "$1 (returns 0)" "rc=$rc"; }

AD_ROOT="$ROOT"
source "$ROOT/linux/core.zsh"
source "$ROOT/linux/prompt.zsh"

# ── stub pmset: counts its own invocations in a file, because it runs
#    inside $(…) and a variable increment there would be lost ─────────────
PMSET_CALLS="$TMP/pmset.calls"
PMSET_OUT="$TMP/pmset.out"
print -n 0 > "$PMSET_CALLS"
pmset() {
  print -n $(( $(<$PMSET_CALLS) + 1 )) > "$PMSET_CALLS"
  cat "$PMSET_OUT"
}
calls() { print -- "$(<$PMSET_CALLS)"; }
reset_calls() { print -n 0 > "$PMSET_CALLS"; }

print "── Linux sysfs path ──────────────────────────────────────────────"

mkdir -p "$TMP/sysfs/BAT0"
print 42 > "$TMP/sysfs/BAT0/capacity"
AD_BAT_SYSFS="$TMP/sysfs"
OSTYPE=linux-gnu
reset_calls
AD_BAT_PCT="" AD_BAT_AT=0
ad_battery_pct
is "reads capacity from sysfs"            "$AD_BAT_PCT" "42"
is "never shells out on Linux"            "$(calls)"    "0"

# a machine with no battery at all: empty dir, no glob match, no error
AD_BAT_SYSFS="$TMP/empty"; mkdir -p "$TMP/empty"

# This check runs FIRST and in a SUBSHELL, on purpose. The glob needs its (N)
# qualifier: without it zsh's NOMATCH prints "no matches found: …/BAT*/capacity"
# on every prompt AND terminates the running script. A direct call would
# therefore kill this test file before it could report anything, so isolate the
# blast radius here and assert on stderr.
( ad_battery_pct ) 2>"$TMP/stderr"
is "no-battery path is silent on stderr"  "$(<$TMP/stderr)" ""

AD_BAT_PCT="99"
rc0 "no-battery path"
is "no battery -> empty, not stale value" "$AD_BAT_PCT" ""

print "── macOS pmset path ──────────────────────────────────────────────"

OSTYPE=darwin24.0
print " -InternalBattery-0 (id=4653155)\t87%; discharging; 4:12 remaining" > "$PMSET_OUT"

reset_calls
AD_BAT_PCT="" AD_BAT_AT=0
rc0 "pmset refresh path"
is "parses pmset percentage"              "$AD_BAT_PCT" "87"
is "forked pmset once"                    "$(calls)"    "1"

# THE REGRESSION TEST: five more prompts must reuse the cache, not refork.
rc0 "cached path"
repeat 5 ad_battery_pct
is "5 more calls still one fork"          "$(calls)"    "1"
is "value survives the cached calls"      "$AD_BAT_PCT" "87"
[[ $AD_BAT_AT -ne 0 ]] && ok "cache timestamp persisted in caller" \
  || bad "cache timestamp persisted in caller" "AD_BAT_AT is still 0 — the \
function was run in a subshell, so the cache is dead and every prompt forks"

# ...and calling it the WRONG way must not silently look fine
AD_BAT_AT=0; reset_calls
_discard="$(ad_battery_pct)"
[[ $AD_BAT_AT -eq 0 ]] && ok "subshell call demonstrably loses the cache" \
  || bad "subshell call demonstrably loses the cache" "unexpectedly persisted"

# expiry: after 60s the cache must refresh
AD_BAT_AT=$(( EPOCHSECONDS - 61 ))
reset_calls
print " -InternalBattery-0 (id=4653155)\t64%; charging; 1:03 remaining" > "$PMSET_OUT"
ad_battery_pct
is "refreshes after 60s"                  "$AD_BAT_PCT" "64"
is "refresh forked exactly once"          "$(calls)"    "1"

# charged at 100% — three digits must not truncate
AD_BAT_AT=0
print " -InternalBattery-0 (id=4653155)\t100%; charged; 0:00 remaining" > "$PMSET_OUT"
ad_battery_pct
is "100% parses whole"                    "$AD_BAT_PCT" "100"

# desktop Mac: pmset prints no percentage at all
AD_BAT_AT=0
print "Now drawing from 'AC Power'" > "$PMSET_OUT"
ad_battery_pct
is "desktop Mac -> no reading"            "$AD_BAT_PCT" ""

# the chip is only drawn for a digit string — confirm the guard the prompt uses
for v in "" "not-a-number" "Now drawing from 'AC Power'"; do
  [[ "$v" == <-> ]] && bad "prompt guard rejects [$v]" "matched <->" \
                    || ok "prompt guard rejects [$v]"
done

print ""
print "── $PASS passed, $FAIL failed ────────────────────────────────────"
(( FAIL == 0 ))
