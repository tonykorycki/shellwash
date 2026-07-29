# ═══════════════════════════════════════════════════════════════════════
#  bedazzle — always-on hooks (any theme, p10k included).
#  Cheap by design: file appends + one printf'd json. No python in the
#  hot path; the GitHub/git poll is throttled and fully backgrounded.
# ═══════════════════════════════════════════════════════════════════════

zmodload zsh/datetime 2>/dev/null

typeset -gF AD_CMD_START=0
typeset -gF AD_LAST_MS=0
typeset -gi AD_LAST_STATUS=0
typeset -gi AD_CMD_COUNT=0
typeset -gi AD_GH_LAST=0

ad_feed_preexec() { AD_CMD_START=$EPOCHREALTIME; }

# write pet.json the pet daemon polls (cheap: printf, atomic rename)
ad_write_petstate() {
  local ok=$1 ms=$2 ts=$EPOCHSECONDS okj=false
  [[ "$ok" == 0 ]] && okj=true
  local tmp="$AD_ROOT/pet.json.tmp"
  printf '{"ok":%s,"ms":%d,"count":%d,"ts":%d,"sprite":"%s","hat":"%s"}' \
    "$okj" "${ms:-0}" "$AD_CMD_COUNT" "$ts" "$AD_SPRITE" "$AD_HAT" > "$tmp" 2>/dev/null \
    && mv -f "$tmp" "$AD_ROOT/pet.json" 2>/dev/null
}

ad_feed_precmd() {
  AD_LAST_STATUS=$?
  (( AD_CMD_COUNT++ ))
  if (( AD_CMD_START > 0 )); then
    AD_LAST_MS=$(( (EPOCHREALTIME - AD_CMD_START) * 1000 ))
    AD_CMD_START=0
  else
    AD_LAST_MS=0
  fi
  local -i ms_i=${AD_LAST_MS%.*}

  # feed the termbg daemon (only when it's running)
  if [[ -f "$AD_ROOT/termbg.pid" ]]; then
    local st=ok; (( AD_LAST_STATUS != 0 )) && st=fail
    print -r -- "${st}|${AD_CMD_COUNT}|${PWD}" >> "$AD_ROOT/termbg.events" 2>/dev/null
  fi

  # feed a pinned pet daemon if one exists (Windows launches pet.py that way)
  [[ -f "$AD_ROOT/bedazzle.pet.pid" ]] && ad_write_petstate "$AD_LAST_STATUS" "$ms_i"

  # throttled, backgrounded git + GitHub PR-comment poll -> github.state.json,
  # which drives the corner buddy's ✉ notify reaction. Gated on the FEATURES
  # (not a daemon pidfile), so it actually runs on Linux.
  if ad_on sprite && ad_on pet_github && (( EPOCHSECONDS - AD_GH_LAST > 90 )); then
    AD_GH_LAST=$EPOCHSECONDS
    ( command $AD_PY "$AD_LINUX/ghpoll.py" "$PWD" >/dev/null 2>&1 &! ) 2>/dev/null
  fi
  return 0
}

# corner buddy, EVERY theme: painted in the top-right corner once per prompt,
# with the cursor saved/restored (so it overlays without taking a single line
# of prompt space). We clear a fixed box first, then paint, so the CURRENT
# buddy is always clean — no async-timer mangling. Old copies scroll into
# history (harmless). Skips the first prompt (p10k instant-prompt would flag
# console output). This is the corner equivalent of the Windows pinned pet.
typeset -gi AD_BUDDY_MAXW=16       # widest box we ever clear (fits any sprite+hat)
typeset -gi AD_BUDDY_TOP=4         # first viewport row the buddy occupies (2-line margin)
ad_buddy_precmd() {
  ad_on sprite || return 0
  (( AD_CMD_COUNT > 1 )) || return 0
  (( $+functions[ad_buddy_render] )) || return 0
  ad_buddy_render "$(ad_buddy_state)"
  local e="$AD_ESC" cols=${COLUMNS:-80} w=$AD_BUDDY_W
  local clearcol=$(( cols - AD_BUDDY_MAXW )); (( clearcol < 1 )) && clearcol=1
  local col0=$(( cols - w ));                (( col0 < 1 ))     && col0=1
  local blank="${(l:$AD_BUDDY_MAXW:: :)}" out="${e}7" y bl   # DECSC (save cursor)
  for (( y = AD_BUDDY_TOP-1; y <= AD_BUDDY_TOP + 5; y++ )); do  # wipe the box first
    out+="${e}[${y};${clearcol}H${e}[0m${blank}"
  done
  y=$AD_BUDDY_TOP
  for bl in "${AD_BUDDY_LINES[@]}"; do                        # paint right-aligned
    out+="${e}[${y};${col0}H${bl}"
    (( y++ ))
  done
  out+="${e}8"                                                # DECRC (restore cursor)
  print -rn -- "$out"
}

# refresh cached weather in the background (shared with fetch + prompt)
ad_refresh_weather() {
  local wf="$AD_ROOT/bedazzle.weather.txt" mtime=0
  command -v curl >/dev/null 2>&1 || return
  [[ -f "$wf" ]] && mtime=$(stat -c %Y "$wf" 2>/dev/null || echo 0)
  (( EPOCHSECONDS - mtime < 1800 )) && return   # fresh enough
  ( curl -fsS --max-time 8 'https://wttr.in/?format=%t+%C' -o "$wf" 2>/dev/null &! ) 2>/dev/null
}
