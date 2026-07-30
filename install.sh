#!/usr/bin/env bash
# Shellwash bootstrap — clone/update and run the installer.
# curl -fsSL https://raw.githubusercontent.com/tonykorycki/shellwash/main/install.sh | bash
set -euo pipefail

REPO="${SHELLWASH_REPO:-https://github.com/tonykorycki/shellwash.git}"
DIR="${SHELLWASH_DIR:-${XDG_DATA_HOME:-$HOME/.local/share}/shellwash}"
REF="${SHELLWASH_REF:-main}"

say() { printf '  %s\n' "$*"; }

# Running from an existing checkout? Just install in place.
_script="${BASH_SOURCE[0]:-$0}"
if [[ -f "$(cd "$(dirname "$_script")" && pwd)/linux/init.zsh" ]]; then
  ROOT="$(cd "$(dirname "$_script")" && pwd)"
  say "installing from checkout: $ROOT"
  exec bash "$ROOT/linux/install.sh"
fi

printf '\033[36mShellwash bootstrap\033[0m\n'
say "repo: $REPO"
say "dir:  $DIR"
say "ref:  $REF"

if ! command -v git >/dev/null 2>&1; then
  say "git not found — install git first"; exit 1
fi

mkdir -p "$(dirname "$DIR")"

if [[ -d "$DIR/.git" ]]; then
  say "updating existing install…"
  git -C "$DIR" fetch --depth 1 origin "$REF" 2>/dev/null || git -C "$DIR" fetch origin
  git -C "$DIR" checkout -q "$REF" 2>/dev/null || git -C "$DIR" pull --ff-only
else
  say "cloning…"
  git clone --depth 1 --branch "$REF" "$REPO" "$DIR" 2>/dev/null \
    || git clone "$REPO" "$DIR" && git -C "$DIR" checkout -q "$REF"
fi

exec bash "$DIR/linux/install.sh"
