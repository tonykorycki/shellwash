#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════
#  bedazzle — Linux / zsh installer.
#  Clone the repo anywhere, then:  bash linux/install.sh
#  Idempotent. Keeps p10k as your default prompt; layers the addons on top.
#  Undo: remove the marked block from ~/.zshrc.
# ═══════════════════════════════════════════════════════════════════════
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ZSHRC="${ZDOTDIR:-$HOME}/.zshrc"

say() { printf '  %s\n' "$*"; }
printf '\033[36mbedazzle — linux installer\033[0m\n'
say "repo: $ROOT"

# 1. python + numpy. If system python3 already has numpy, use it as-is
#    (offline-friendly). Otherwise build a venv and pip-install requirements.
if ! command -v python3 >/dev/null 2>&1; then
  say "python3 not found — install Python 3.10+ first"; exit 1
fi
if python3 -c 'import numpy' >/dev/null 2>&1; then
  say "system python3 has numpy — using it (no venv needed)"
elif [[ -x "$ROOT/.venv/bin/python" ]] && "$ROOT/.venv/bin/python" -c 'import numpy' >/dev/null 2>&1; then
  say "existing venv has numpy — using it"
else
  say "creating venv + installing numpy…"
  python3 -m venv "$ROOT/.venv"
  "$ROOT/.venv/bin/python" -m pip install --quiet --upgrade pip >/dev/null 2>&1 || true
  "$ROOT/.venv/bin/python" -m pip install --quiet -r "$ROOT/requirements.txt"
fi

# 2. ~/.zshrc block (sourced AFTER omz/p10k so p10k stays the default prompt)
MARKER_START='# >>> bedazzle >>>'
MARKER_END='# <<< bedazzle <<<'
OLD_MARKER='# >>> ascii-dreams >>>'
if [[ -f "$ZSHRC" ]] && { grep -qF "$MARKER_START" "$ZSHRC" || grep -qF "$OLD_MARKER" "$ZSHRC"; }; then
  say "zshrc block already present — skipped"
else
  cp -f "$ZSHRC" "$ZSHRC.bak-before-bedazzle" 2>/dev/null || true
  {
    printf '\n\n%s\n' "$MARKER_START"
    printf 'source "%s/linux/init.zsh"\n' "$ROOT"
    printf '%s\n' "$MARKER_END"
  } >> "$ZSHRC"
  say "appended source block to $ZSHRC (backup: .bak-before-bedazzle)"
fi

# 3. login panel — prepended BEFORE p10k's instant prompt so a startup
#    banner never trips the "console output during initialization" warning.
#    (fetch.py --login self-checks the 'fetch' toggle and is numpy-free.)
TOP_START='# >>> bedazzle login >>>'
TOP_END='# <<< bedazzle login <<<'
OLD_TOP='# >>> ascii-dreams login >>>'
if grep -qF "$TOP_START" "$ZSHRC" 2>/dev/null || grep -qF "$OLD_TOP" "$ZSHRC" 2>/dev/null; then
  say "login-panel block already present — skipped"
else
  tmp="$(mktemp)"
  {
    printf '%s\n' "$TOP_START"
    printf '[[ -o interactive ]] && command python3 "%s/linux/fetch.py" --login 2>/dev/null\n' "$ROOT"
    printf '%s\n\n' "$TOP_END"
    cat "$ZSHRC"
  } > "$tmp"
  mv "$tmp" "$ZSHRC"
  say "prepended login-panel block (runs before p10k instant prompt)"
fi

printf '\n\033[32mdone.\033[0m open a new terminal (or run: reload), then try:\n'
say "bedazzle              feature toggles + theme manager"
say "bedazzle theme bedazzle   switch prompt (p10k is the default)"
say "buddy / buddy roll    pet roster + gacha"
say "pet                   corner buddy (works in any theme)"
say "fetch · lava · hr     system panel · corner lamp · divider"
say "termbg on             living background (needs kitty; see README)"
