#!/usr/bin/env bash
# Shellwash — Linux / zsh installer.
# Usually invoked by ./install.sh or after clone: bash linux/install.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ZSHRC="${ZDOTDIR:-$HOME}/.zshrc"
KITTY_CONF="${XDG_CONFIG_HOME:-$HOME/.config}/kitty/kitty.conf"
KITTY_MARKER='# >>> shellwash termbg >>>'
KITTY_END='# <<< shellwash termbg <<<'

say() { printf '  %s\n' "$*"; }
warn() { printf '  \033[33m%s\033[0m\n' "$*"; }

printf '\033[36mShellwash installer\033[0m\n'
say "repo: $ROOT"

if ! command -v python3 >/dev/null 2>&1; then
  say "python3 not found — install Python 3.10+ first"; exit 1
fi
if python3 -c 'import numpy' >/dev/null 2>&1; then
  say "system python3 has numpy"
  LOGIN_PY="python3"
elif [[ -x "$ROOT/.venv/bin/python" ]] && "$ROOT/.venv/bin/python" -c 'import numpy' >/dev/null 2>&1; then
  say "venv python has numpy"
  LOGIN_PY="$ROOT/.venv/bin/python"
else
  say "creating venv + installing numpy…"
  python3 -m venv "$ROOT/.venv"
  "$ROOT/.venv/bin/python" -m pip install --quiet --upgrade pip >/dev/null 2>&1 || true
  "$ROOT/.venv/bin/python" -m pip install --quiet -r "$ROOT/requirements.txt"
  LOGIN_PY="$ROOT/.venv/bin/python"
fi

# ── zshrc: main source block ─────────────────────────────────────────────
MARKER_START='# >>> shellwash >>>'
MARKER_END='# <<< shellwash <<<'
if [[ -f "$ZSHRC" ]] && grep -qE '# >>> (shellwash|bedazzle|ascii-dreams) >>>' "$ZSHRC"; then
  say "zshrc block already present — skipped"
else
  touch "$ZSHRC"
  cp -f "$ZSHRC" "$ZSHRC.bak-before-shellwash" 2>/dev/null || true
  {
    printf '\n\n%s\n' "$MARKER_START"
    printf 'source "%s/linux/init.zsh"\n' "$ROOT"
    printf '%s\n' "$MARKER_END"
  } >> "$ZSHRC"
  say "appended shellwash block to $ZSHRC"
fi

# ── zshrc: login panel (before p10k instant prompt) ───────────────────────
TOP_START='# >>> shellwash login >>>'
TOP_END='# <<< shellwash login <<<'
if grep -qE '# >>> (shellwash|bedazzle|ascii-dreams) login >>>' "$ZSHRC" 2>/dev/null; then
  say "login block already present — skipped"
else
  cp -f "$ZSHRC" "$ZSHRC.bak-before-shellwash" 2>/dev/null || true
  tmp="$(mktemp)"
  {
    printf '%s\n' "$TOP_START"
    printf '[[ -o interactive ]] && command %s "%s/linux/fetch.py" --login 2>/dev/null\n' "$LOGIN_PY" "$ROOT"
    printf '%s\n\n' "$TOP_END"
    cat "$ZSHRC"
  } > "$tmp"
  mv "$tmp" "$ZSHRC"
  say "prepended login block (before p10k instant prompt)"
fi

# ── kitty: termbg remote-control snippet ──────────────────────────────────
install_kitty_snippet() {
  if ! command -v kitty >/dev/null 2>&1; then
    warn "kitty not on PATH — skipped kitty.conf (termbg needs kitty on Linux)"
    return 0
  fi
  if [[ -f "$KITTY_CONF" ]] && grep -qF "$KITTY_MARKER" "$KITTY_CONF" 2>/dev/null; then
    say "kitty.conf snippet already present — skipped"
    return 0
  fi
  mkdir -p "$(dirname "$KITTY_CONF")"
  [[ -f "$KITTY_CONF" ]] && cp -f "$KITTY_CONF" "$KITTY_CONF.bak-before-shellwash" 2>/dev/null || true
  {
    [[ -f "$KITTY_CONF" ]] && cat "$KITTY_CONF" && printf '\n'
    printf '%s\n' "$KITTY_MARKER"
    grep -v '^#' "$ROOT/docs/kitty.conf.snippet" | grep -v '^[[:space:]]*$' || true
    printf '%s\n' "$KITTY_END"
  } > "${KITTY_CONF}.shellwash-tmp"
  mv "${KITTY_CONF}.shellwash-tmp" "$KITTY_CONF"
  say "appended termbg settings to $KITTY_CONF"
  warn "restart kitty fully (all windows) for termbg to work"
}
install_kitty_snippet

# ── optional apt hints (never run sudo here) ──────────────────────────────
if command -v apt-get >/dev/null 2>&1; then
  missing=()
  command -v playerctl >/dev/null 2>&1 || missing+=(playerctl)
  if ((${#missing[@]})); then
    warn "optional: sudo apt install ${missing[*]}  (nowplaying module)"
  fi
fi

printf '\n\033[32mdone.\033[0m open a new terminal (or: exec zsh), then try:\n'
say "bedazzle"
say "termbg on        living background (after kitty restart)"
say "buddy            pet roster"
