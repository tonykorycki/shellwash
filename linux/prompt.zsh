# ═══════════════════════════════════════════════════════════════════════
#  bedazzle — the minimal accent prompt theme (zsh port)
#  A minimal one-accent prompt: shortened path (+git +venv) on the left,
#  duration · status · clock · battery · weather right-aligned.
#  Opt-in: `bedazzle theme bedazzle`. p10k stays the default.
#  The buddy is NOT inline here — it's the `pet` daemon, which works under
#  ANY theme (p10k included), so the roster lives in one place (pet.py).
# ═══════════════════════════════════════════════════════════════════════

zmodload zsh/datetime 2>/dev/null
# AD_LAST_MS / AD_LAST_STATUS are maintained by hooks.zsh (ad_feed_*),
# which run before this precmd — so the bedazzle prompt just consumes them.

# Battery percentage -> $AD_BAT_PCT ("" when there is no battery).
# Runs in precmd, so it must not fork: Linux reads sysfs directly ($(<file)
# is a builtin read in zsh, not a subshell), and the macOS pmset call is
# cached for 60s.
#
# NEVER call this as "$(ad_battery_pct)" — the cache lives in these globals
# and a command substitution runs in a subshell that discards them, so every
# prompt would fork pmset. Read $AD_BAT_PCT after calling instead.
typeset -g AD_BAT_PCT="" AD_BAT_AT=0
: ${AD_BAT_SYSFS:=/sys/class/power_supply}   # overridable so tests can fake it
ad_battery_pct() {
  local bf
  for bf in $AD_BAT_SYSFS/BAT*/capacity(N); do   # (N): no match -> no error
    [[ -r "$bf" ]] && { AD_BAT_PCT="$(<$bf)"; return; }
  done
  [[ "$OSTYPE" == darwin* ]] || { AD_BAT_PCT=""; return; }
  (( EPOCHSECONDS - AD_BAT_AT < 60 )) && return          # cached answer stands
  AD_BAT_AT=$EPOCHSECONDS
  # " -InternalBattery-0 (id=…)<TAB>87%; discharging; …" -> "87"
  AD_BAT_PCT="${$(pmset -g batt 2>/dev/null)%%\%*}"
  AD_BAT_PCT="${AD_BAT_PCT##*[^0-9]}"
}

# walk up for .git/HEAD; echo "branch<TAB>state" or nothing
ad_git_info() {
  local d="$PWD" head branch state=""
  while [[ -n "$d" ]]; do
    if [[ -f "$d/.git/HEAD" ]]; then
      head="$(<"$d/.git/HEAD")"
      if [[ "$head" == ref:*refs/heads/* ]]; then branch="${head##*refs/heads/}"
      else branch="${head[1,7]}"; fi
      [[ -f "$d/.git/MERGE_HEAD" ]] && state="merge"
      [[ -d "$d/.git/rebase-merge" || -d "$d/.git/rebase-apply" ]] && state="rebase"
      print -r -- "${branch}"$'\t'"${state}"
      return
    fi
    [[ "$d" == "/" ]] && break
    d="${d:h}"
  done
}

# fish-style path compression: keep head + last, first-letter the middle
ad_short_path() {
  local p="${PWD/#$HOME/~}"
  if ad_on shortpath; then
    local -a segs; segs=("${(@s:/:)p}")
    if (( ${#segs} > 3 )); then
      local head="${segs[1]}" tail="${segs[-1]}" mid="" i
      for (( i = 2; i < ${#segs}; i++ )); do
        [[ -n "${segs[i]}" ]] && mid+="/${segs[i][1]}" || mid+="/"
      done
      p="${head}${mid}/${tail}"
    fi
  fi
  print -r -- "$p"
}

# build the right-info string + its visible length (into REPLY / REPLY2)
ad_right_info() {
  local -a parts plain
  local dim="${AD_ESC}[2m" e0="${AD_ESC}[0m"
  if (( AD_LAST_MS >= 1 )); then
    local dur
    if   (( AD_LAST_MS >= 60000 )); then dur="$(printf '%.1fm' $(( AD_LAST_MS / 60000.0 )))"
    elif (( AD_LAST_MS >= 1000  )); then dur="$(printf '%.2fs' $(( AD_LAST_MS / 1000.0 )))"
    else dur="$(printf '%.0fms' $AD_LAST_MS)"; fi
    parts+=("${dim}${dur}${e0}"); plain+=("$dur")
  fi
  if (( AD_LAST_STATUS == 0 )); then
    parts+=("$(ad_fg 126 231 135)✓${e0}"); plain+=("x")
  else
    parts+=("$(ad_fg 248 81 73)✗${e0}"); plain+=("x")
  fi
  local clock; strftime -s clock '%H:%M' $EPOCHSECONDS
  parts+=("${dim}${clock}${e0}"); plain+=("$clock")
  if ad_on battery; then
    ad_battery_pct                      # sets AD_BAT_PCT; not $(…) — see above
    local cap="$AD_BAT_PCT"
    if [[ "$cap" == <-> ]]; then
      local bc="$dim"; (( cap <= 20 )) && bc="$(ad_fg 248 81 73)"
      parts+=("${bc}${cap}%${e0}"); plain+=("${cap}%")
    fi
  fi
  if ad_on weather; then
    local wf="$AD_ROOT/bedazzle.weather.txt" wx=""
    [[ -f "$wf" ]] && wx="$(<$wf)"
    if [[ -n "$wx" ]]; then
      local temp="${wx%% *}"
      parts+=("${dim}${temp}${e0}"); plain+=("$temp")
    fi
  fi
  # join with a colored separator (zsh's j: flag won't expand a variable,
  # so build it by hand)
  local sep="${dim} · ${e0}" i
  REPLY="${parts[1]}"
  for (( i = 2; i <= ${#parts}; i++ )); do REPLY+="${sep}${parts[i]}"; done
  REPLY2="${(j: · :)plain}"
}

ad_bedazzle_precmd() {
  local e0="${AD_ESC}[0m" acc="$(ad_accent)" acc2="$(ad_accent2)"
  local cols=${COLUMNS:-80}

  # (the inline buddy is printed by ad_buddy_precmd in hooks.zsh, which runs
  # in EVERY theme — not just here — so p10k gets it too)
  ad_on airy && print -r -- ""

  # left: path (+git +venv)
  local path_txt="$(ad_short_path)"
  local left="${acc}${AD_ESC}[1m${path_txt}${e0}"
  local left_plain="$path_txt"
  if ad_on git; then
    local gi; gi="$(ad_git_info)"
    if [[ -n "$gi" ]]; then
      local branch="${gi%%$'\t'*}" state="${gi##*$'\t'}"
      local btxt="$branch"; [[ -n "$state" ]] && btxt+=" ${state}!"
      left+="  ${acc2}⎇ ${btxt}${e0}"; left_plain+="  x ${btxt}"
    fi
  fi
  if ad_on venv && [[ -n "$VIRTUAL_ENV" ]]; then
    local vn="${VIRTUAL_ENV:t}"
    [[ "$vn" == (.venv|venv) ]] && vn="${${VIRTUAL_ENV:h}:t}/${vn}"
    left+="  $(ad_fg 126 231 135)⚡${vn}${e0}"; left_plain+="  x${vn}"
  fi

  # right info, absolute-positioned
  local line="$left"
  if ad_on rightinfo; then
    local REPLY REPLY2; ad_right_info
    local col=$(( cols - ${#REPLY2} ))
    (( col > ${#left_plain} + 4 )) && line+="${AD_ESC}[${col}G${REPLY}"
  fi
  print -r -- "$line"

  # window title
  if ad_on title; then print -n -- $'\e]0;'"${path_txt}"$'\a'; fi

  # the arrow line itself (colored by last exit status)
  if (( ${AD_LAST_STATUS:-0} == 0 )); then
    PROMPT="%{${acc}%}❯%{${e0}%} "
  else
    PROMPT="%{$(ad_fg 248 81 73)%}❯%{${e0}%} "
  fi
}
