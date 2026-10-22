#!/usr/bin/env bash
# Shellwash — macOS smoke check.
#
# The fixture tests (tests/run.sh) pin how output is PARSED. They cannot tell
# you whether the real tools on a real Mac actually emit that output. This
# script closes that gap: it is read-only, installs nothing, changes nothing,
# and prints raw tool output next to what shellwash made of it, so you can
# see at a glance whether any assumption is wrong.
#
#     git clone https://github.com/tonykorycki/shellwash.git
#     bash shellwash/tests/macos-smoke.sh
#
# Send back the whole output.

set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="${PYTHON:-python3}"
warn=0

hdr()  { printf '\n\033[1m── %s %s\033[0m\n' "$1" "$(printf '─%.0s' $(seq 1 $((60 - ${#1}))))"; }
note() { printf '  %s\n' "$*"; }
bad()  { printf '  \033[31m!! %s\033[0m\n' "$*"; warn=$((warn + 1)); }
good() { printf '  \033[32mok\033[0m %s\n' "$*"; }
raw()  { printf '\033[2m%s\033[0m\n' "$(sed 's/^/      /' <<<"$1")"; }

printf '\033[36mShellwash macOS smoke check\033[0m\n'
note "repo: $ROOT"

# ── 0. is this even a Mac ────────────────────────────────────────────────
hdr "platform"
note "uname:    $(uname -a)"
note "OSTYPE:   ${OSTYPE:-<unset>}"
note "arch:     $(uname -m)"
[[ "$(uname -s)" == "Darwin" ]] || bad "not macOS — this script is pointless here"

# ── 1. prerequisites ─────────────────────────────────────────────────────
hdr "prerequisites"
if command -v "$PY" >/dev/null 2>&1; then
  good "python3: $("$PY" -V 2>&1) at $(command -v "$PY")"
  "$PY" -c 'import numpy' 2>/dev/null \
    && good "numpy importable from system python3" \
    || note "numpy not in system python3 — the installer will build a .venv (fine)"
else
  bad "no python3 on PATH — run: xcode-select --install"
fi
command -v git >/dev/null 2>&1 && good "git: $(git --version)" || bad "git missing"
command -v zsh >/dev/null 2>&1 && good "zsh: $(zsh --version)" || bad "zsh missing"

# BSD mktemp needs a template; bare `mktemp` is GNU-only. The installer was
# fixed for this — confirm the fixed form works and note whether bare fails.
if t="$(mktemp "${TMPDIR:-/tmp}/shellwash-smoke.XXXXXX" 2>/dev/null)"; then
  good "mktemp with template works ($t)"; rm -f "$t"
else
  bad "mktemp WITH template failed — installer will break"
fi
if mktemp >/dev/null 2>&1; then
  note "bare mktemp also works here (GNU-style)"
else
  note "bare mktemp fails, as expected on BSD — the installer no longer uses it"
fi

# zsh/stat module, used for the weather cache mtime
if zsh -fc 'zmodload -F zsh/stat b:zstat 2>/dev/null && (( $+builtins[zstat] ))' 2>/dev/null; then
  good "zsh/stat (zstat) available"
else
  note "zstat unavailable — hooks.zsh falls back to stat(1); checking that:"
  stat -f %m "$ROOT/README.md" >/dev/null 2>&1 \
    && good "BSD 'stat -f %m' works (fallback is good)" \
    || bad "neither zstat nor 'stat -f %m' works — weather cache will thrash"
fi

# ── 2. raw system facts, then what shellwash parses out of them ──────────
hdr "raw tool output"
for k in machdep.cpu.brand_string hw.model hw.memsize kern.boottime; do
  v="$(sysctl -n "$k" 2>/dev/null)" && note "$k = $v" || bad "sysctl -n $k FAILED"
done
echo
note "vm_stat (first 8 lines) — page size and label spelling matter:"
raw "$(vm_stat 2>/dev/null | head -8)"
echo
note "pmset -g batt:"
raw "$(pmset -g batt 2>/dev/null)"
echo
note "sw_vers:"
raw "$(sw_vers 2>/dev/null)"

hdr "parsed by linux/fetch.py"
if command -v "$PY" >/dev/null 2>&1; then
  "$PY" - "$ROOT" <<'PYEOF'
import sys, os
sys.path.insert(0, os.path.join(sys.argv[1], "linux"))
import fetch

if sys.platform == "darwin" and not fetch.IS_MAC:
    print("  !! fetch.IS_MAC is False on a Mac — platform detection is broken")
elif sys.platform != "darwin":
    print("  (not a Mac: showing the Linux path, so these are Linux facts)")

rows = [("os", fetch.os_pretty), ("kernel", lambda: __import__("platform").release()),
        ("host", fetch.host_model), ("cpu", fetch.cpu_name), ("gpu", fetch.gpu_name),
        ("uptime", fetch.uptime_txt), ("terminal", fetch.terminal_name)]
for label, fn in rows:
    try:
        print(f"  {label:9}{fn()}")
    except Exception as exc:                      # must never happen
        print(f"  {label:9}!! RAISED {exc!r}")

try:
    used, total = fetch.mem_gib()
    flag = "" if total > 0 else "   !! total is 0 — /proc-style parse failed"
    print(f"  {'memory':9}{used:.1f} / {total:.1f} GiB{flag}")
    if total and used > total:
        print("           !! used exceeds total")
except Exception as exc:
    print(f"  {'memory':9}!! RAISED {exc!r}")

bat = fetch.battery_pct()
print(f"  {'battery':9}{bat if bat is not None else '(none — expected on a desktop Mac)'}")
PYEOF
  echo
  note "Compare the numbers above against About This Mac / Activity Monitor."
  note "memory should be close to Activity Monitor's 'Memory Used'."
else
  bad "skipped — no python3"
fi

# ── 3. the full fetch panel, rendered ────────────────────────────────────
hdr "fetch panel (visual)"
command -v "$PY" >/dev/null 2>&1 && "$PY" "$ROOT/linux/fetch.py" \
  || bad "skipped — no python3"

# ── 4. kitty / termbg ────────────────────────────────────────────────────
hdr "kitty + termbg"
kexe=""
if command -v kitty >/dev/null 2>&1; then
  kexe="$(command -v kitty)"; good "kitty on PATH: $kexe"
else
  for p in /Applications/kitty.app/Contents/MacOS/kitty \
           "$HOME/Applications/kitty.app/Contents/MacOS/kitty"; do
    [[ -x "$p" ]] && { kexe="$p"; good "kitty found in app bundle: $p"; break; }
  done
  [[ -n "$kexe" ]] || note "kitty not installed — termbg has nowhere to draw \
(bedazzle still works). brew install --cask kitty"
fi
[[ -n "$kexe" ]] && note "version: $("$kexe" --version 2>&1 | head -1)"

# Which config file does kitty actually read? The installer picks one; if the
# user's real config lives elsewhere, appending to the wrong file either does
# nothing or shadows their config.
xdg="${XDG_CONFIG_HOME:-$HOME/.config}/kitty/kitty.conf"
mac="$HOME/Library/Preferences/kitty/kitty.conf"
note "config candidates:"
for f in "$xdg" "$mac"; do
  [[ -f "$f" ]] && note "  EXISTS  $f" || note "  absent  $f"
done
if [[ -f "$xdg" && -f "$mac" ]]; then
  bad "BOTH exist — kitty reads one and ignores the other; say which one is live"
fi

note "termbg terminal detection:"
if command -v "$PY" >/dev/null 2>&1; then
  "$PY" - "$ROOT" <<'PYEOF'
import sys, os
sys.path.insert(0, sys.argv[1])
import termbg
print("      kitty binary :", termbg._kitty_exe())
print("      sockets      :", termbg._kitty_socket_paths() or "(none — run this INSIDE kitty)")
print("      KITTY_WINDOW_ID:", os.environ.get("KITTY_WINDOW_ID", "<unset>"))
print("      TERM         :", os.environ.get("TERM", "<unset>"))
PYEOF
fi
note "If you are inside kitty and 'sockets' is empty, remote control is not"
note "configured yet — that is what the installer's kitty.conf block sets up."

# ── 5. the fixture suites, for completeness ──────────────────────────────
hdr "fixture suites"
if command -v "$PY" >/dev/null 2>&1; then
  bash "$ROOT/tests/run.sh" 2>&1 | tail -6
fi

hdr "result"
if (( warn == 0 )); then
  printf '  \033[32mno problems detected\033[0m — send the whole output back anyway,\n'
  printf '  the raw numbers above are the part worth checking by eye.\n'
else
  printf '  \033[31m%d problem(s) flagged above\033[0m — send the whole output back.\n' "$warn"
fi
