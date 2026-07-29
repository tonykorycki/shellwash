# ═══════════════════════════════════════════════════════════════════════
#  bedazzle — inline buddy for the prompt.
#  A reactive ASCII pet drawn as part of the prompt block (top-right), so it
#  scrolls naturally with history — no pinned daemon, no scrollback stamping.
#  The art itself lives in pet.py ($BUDDIES); we cache its pre-rendered
#  output here so there's no fragile re-encoding of backslashes/quotes in zsh.
#  States: idle · blink · fail · happy · notify.
# ═══════════════════════════════════════════════════════════════════════

typeset -gA AD_BUDDY_CACHE AD_BUDDY_CACHE_W

# (re)build the cache for the current sprite+hat. Call at init and whenever
# the sprite/hat/accent changes. One python call, not per-prompt.
ad_buddy_cache() {
  AD_BUDDY_CACHE=(); AD_BUDDY_CACHE_W=()
  local state w rest
  while IFS=$'\t' read -r state w rest; do
    [[ -n "$state" ]] || continue
    AD_BUDDY_CACHE[$state]="$rest"
    AD_BUDDY_CACHE_W[$state]="$w"
  done < <(command $AD_PY "$AD_ROOT/pet.py" render "$AD_SPRITE" 2>/dev/null)
}

# ad_buddy_render <state> -> fills AD_BUDDY_LINES (array) + AD_BUDDY_W
ad_buddy_render() {
  local state="$1"
  [[ -n "${AD_BUDDY_CACHE[$state]}" ]] || state=idle
  AD_BUDDY_W="${AD_BUDDY_CACHE_W[$state]:-8}"
  AD_BUDDY_LINES=("${(@ps:\037:)AD_BUDDY_CACHE[$state]}")   # \037 = 0x1f separator
}

# pick the buddy mood from the last command (mirrors pet.py logic)
ad_buddy_state() {
  if (( AD_LAST_STATUS != 0 )); then print -r -- fail; return; fi
  local gh="$AD_ROOT/github.state.json"
  if ad_on pet_github && [[ -f "$gh" ]]; then
    local c="${$(grep -o '\"pr_comments\":[0-9]*' "$gh" 2>/dev/null)##*:}"
    if [[ "$c" == <-> ]]; then
      if (( c > ${AD_SEEN_COMMENTS:-c} )); then
        AD_SEEN_COMMENTS=$c; print -r -- notify; return
      fi
      AD_SEEN_COMMENTS=$c
    fi
  fi
  (( AD_LAST_MS > 10000 )) && { print -r -- happy; return; }
  (( RANDOM % 7 == 0 )) && { print -r -- blink; return; }
  print -r -- idle
}
