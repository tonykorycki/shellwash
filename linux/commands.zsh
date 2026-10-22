# Shellwash — command surface: bedazzle control, themes, launchers.

autoload -Uz add-zsh-hook

# ── theme manager ─────────────────────────────────────────────────────────
# p10k is the default; "bedazzle" is our prompt; any other name is treated
# as an omz theme file. Switching to/from p10k live is best-effort; if it
# looks off, `reload` gives a clean shell.

ad_theme_teardown_ours() {
  add-zsh-hook -d precmd ad_bedazzle_precmd 2>/dev/null
}

# p10k's instant prompt redirects stdout/stderr until its own first precmd
# hook restores them. Removing the _p9k* hooks at startup skips that, and
# every command's output vanishes — so end the instant prompt first.
ad_p10k_release() {
  (( $+functions[_p9k_instant_prompt_cleanup] )) || return 0
  _p9k_instant_prompt_cleanup 0
  setopt prompt_cr prompt_sp
}

ad_theme_apply() {
  local name="$1" h
  case "$name" in
    bedazzle)
      # stop p10k driving the prompt, then install ours
      ad_p10k_release
      for h in $precmd_functions;  do [[ $h == (_p9k*|powerlevel*|prompt_powerlevel*) ]] && add-zsh-hook -d precmd  $h; done
      for h in $preexec_functions; do [[ $h == (_p9k*|powerlevel*|prompt_powerlevel*) ]] && add-zsh-hook -d preexec $h; done
      add-zsh-hook precmd ad_bedazzle_precmd
      RPROMPT=''
      ;;
    p10k|powerlevel10k)
      ad_theme_teardown_ours
      if (( $+functions[prompt_powerlevel10k_setup] )); then
        prompt_powerlevel10k_setup
      fi
      ;;
    *)
      ad_theme_teardown_ours
      # p10k's precmd rewrites PROMPT every command, so it must be removed or
      # it clobbers whatever the omz theme sets.
      ad_p10k_release
      for h in $precmd_functions;  do [[ $h == (_p9k*|powerlevel*|prompt_powerlevel*) ]] && add-zsh-hook -d precmd  $h; done
      for h in $preexec_functions; do [[ $h == (_p9k*|powerlevel*|prompt_powerlevel*) ]] && add-zsh-hook -d preexec $h; done
      RPROMPT=''
      local f
      for f in "$ZSH_CUSTOM/themes/$name.zsh-theme" \
               "$ZSH/custom/themes/$name.zsh-theme" \
               "$ZSH/themes/$name.zsh-theme"; do
        [[ -r "$f" ]] && { source "$f"; return 0; }
      done
      print -r -- " theme '$name' not found in omz themes"
      return 1
      ;;
  esac
}

ad_theme() {
  local name="$1"
  local e0="${AD_ESC}[0m" acc="$(ad_accent)"
  [[ "$name" == list ]] && name=""
  if [[ "$name" == random ]]; then
    local -a pool
    pool=(bedazzle p10k "$ZSH"/themes/*.zsh-theme(N:t:r) "$ZSH"/custom/themes/*.zsh-theme(N:t:r))
    pool=(${pool:#example})                    # drop the omz placeholder theme
    name="${pool[RANDOM % ${#pool} + 1]}"
    print -r -- " theme roll -> ${acc}${name}${e0}"
  fi
  if [[ -z "$name" ]]; then
    print -r -- ""
    print -r -- "  ${acc}themes${e0}  (current: ${acc}${AD_THEME}${e0})"
    print -r -- "    ${acc}p10k${e0}      your powerlevel10k config (default)"
    print -r -- "    ${acc}bedazzle${e0}  the minimal accent prompt"
    print -r -- "    ${acc}random${e0}    surprise me — roll a random theme"
    print -r -- "    <name>    any oh-my-zsh theme in your themes dir"
    print -r -- ""
    local -a avail
    avail=("$ZSH"/themes/*.zsh-theme(N:t:r) "$ZSH"/custom/themes/*.zsh-theme(N:t:r))
    print -r -- "  ${AD_ESC}[2mavailable omz themes:${e0} ${(j:, :)${(o)avail}}"
    print -r -- ""
    return
  fi
  # validate before we persist + reload
  if [[ "$name" != (bedazzle|p10k|powerlevel10k) ]]; then
    local found=0 f
    for f in "$ZSH_CUSTOM/themes/$name.zsh-theme" "$ZSH/custom/themes/$name.zsh-theme" "$ZSH/themes/$name.zsh-theme"; do
      [[ -r "$f" ]] && { found=1; break; }
    done
    (( found )) || { print -r -- " theme '$name' not found in omz themes (try plain 'bedazzle theme')"; return 1; }
  fi
  ad_cfg_set theme "$name"
  print -r -- " theme -> ${acc}${name}${e0} ${AD_ESC}[2m(reloading shell…)${e0}"
  # a clean reload is the only fully reliable way to hand the prompt between
  # p10k and another theme; init.zsh re-applies the saved choice at startup.
  exec zsh
}

# tint p10k's key segments with the accent hue (accent recolors the letters)
ad_apply_accent_to_p10k() {
  ad_on accent_p10k || return 0
  [[ "$AD_THEME" == (p10k|powerlevel10k) ]] || return 0
  (( $+functions[prompt_powerlevel10k_setup] )) || return 0
  local idx idx2
  idx="$(ad_accent_xterm)"
  local rgb; rgb=($(ad_hsv2rgb $(( AD_ACCENT + 55 )) 0.55 0.95))
  idx2="$(ad_rgb2xterm $rgb[1] $rgb[2] $rgb[3])"
  typeset -g POWERLEVEL9K_DIR_FOREGROUND=$idx
  typeset -g POWERLEVEL9K_VCS_CLEAN_FOREGROUND=$idx2
  typeset -g POWERLEVEL9K_VIRTUALENV_FOREGROUND=$idx2
  typeset -g POWERLEVEL9K_PROMPT_CHAR_OK_{VIINS,VICMD,VIVIS,VIOWR}_FOREGROUND=$idx
  # re-run setup so p10k picks up the new colors
  prompt_powerlevel10k_setup 2>/dev/null
}

# ── accent ────────────────────────────────────────────────────────────────
ad_set_accent() {
  local name="$1" hue
  typeset -A named=(blue 215 violet 270 green 140 amber 45 red 2 cyan 185 pink 330)
  if [[ -n "${named[$name]}" ]]; then hue="${named[$name]}"
  elif [[ "$name" == <-> || "$name" == <->.<-> ]]; then hue="$name"
  else
    print -r -- " accent: ${(kj:, :)named}, or any hue 0-360"; return 1
  fi
  AD_ACCENT="$hue"
  ad_cfg_set accent "$hue"
  ad_apply_accent_to_p10k
  (( $+functions[ad_buddy_cache] )) && ad_buddy_cache
  local e0="${AD_ESC}[0m"
  print -r -- " accent -> $(ad_accent)${hue}${e0}  $(ad_accent)██$(ad_accent2)██${e0}"
}

# ── bedazzle control command ───────────────────────────────────────────────
bedazzle() {
  local action="$1" name="$2"
  local e0="${AD_ESC}[0m" dim="${AD_ESC}[2m" acc="$(ad_accent)"
  typeset -A desc=(
    fetch 'system panel on startup' sprite 'inline buddy in the bedazzle prompt'
    rightinfo 'duration/status/clock (bedazzle theme)' git 'branch + state'
    venv 'python venv chip' shortpath 'fish-style path compression'
    title 'window title follows folder' airy 'breathing room above prompt'
    battery 'battery % when present' weather 'cached wttr.in temperature'
    spirits 'kaomoji visitors (legacy)' rule 'gradient rule line (legacy)'
    accent_p10k 'tint p10k segments with the accent' pet_github 'pet reacts to git + PR comments'
    termbg_auto 'living background auto-starts on login'
  )
  case "$action" in
    on|off)
      if [[ -z "${desc[$name]}" ]]; then print -r -- "${dim} unknown feature '$name' — try plain 'bedazzle'${e0}"; return; fi
      AD_FEAT[$name]=$([[ "$action" == on ]] && print 1 || print 0)
      ad_cfg_toggle "$name" "$action"
      print -r -- " ${acc}${name}${e0} -> ${action}"
      ;;
    theme)   ad_theme "$name" ;;
    accent)  ad_set_accent "$name" ;;
    sprite)  command $AD_PY "$AD_ROOT/pet.py" sprite "$name"; ad_load_config
             (( $+functions[ad_buddy_cache] )) && ad_buddy_cache ;;
    hat)     command $AD_PY "$AD_ROOT/pet.py" hat "$name";    ad_load_config
             (( $+functions[ad_buddy_cache] )) && ad_buddy_cache ;;
    stats)   ad_stats ;;
    ""|help|list)
      print -r -- ""
      print -r -- "  ${acc}${AD_ESC}[1mbedazzle${e0} ${dim}— every addon, individually togglable${e0}"
      print -r -- ""
      local k state
      for k in ${(ko)AD_FEAT}; do
        if (( AD_FEAT[$k] )); then state="$(ad_fg 126 231 135) on${e0} "; else state="${dim} off${e0}"; fi
        printf '   %s %s%-12s%s %s%s%s\n' "$state" "$acc" "$k" "$e0" "$dim" "${desc[$k]}" "$e0"
      done
      print -r -- ""
      print -r -- "  ${dim} bedazzle on|off <name>      toggle a feature${e0}"
      print -r -- "  ${dim} bedazzle theme <name>       p10k (default) · bedazzle · any omz theme${e0}"
      print -r -- "  ${dim} bedazzle accent <name|hue>  blue·violet·green·amber·red·cyan·pink${e0}"
      print -r -- "  ${dim} bedazzle sprite|hat <name>  pick buddy / hat   ('buddy' shows the roster)${e0}"
      print -r -- "  ${dim} buddy [roll] · pet · fetch · lava · termbg · hr${e0}"
      print -r -- ""
      ;;
    *) print -r -- "${dim} unknown — try plain 'bedazzle'${e0}" ;;
  esac
}

ad_stats() {
  local e0="${AD_ESC}[0m" acc="$(ad_accent)"
  print -r -- ""
  print -r -- "  ${acc}theme${e0}    ${AD_THEME}"
  print -r -- "  ${acc}accent${e0}   ${AD_ACCENT}  $(ad_accent)██$(ad_accent2)██${e0}"
  print -r -- "  ${acc}sprite${e0}   ${AD_SPRITE}"
  print -r -- ""
}

# ── launchers ──────────────────────────────────────────────────────────────
fetch()  { command $AD_PY "$AD_ROOT/linux/fetch.py" "$@"; }

buddy() {
  command $AD_PY "$AD_ROOT/pet.py" "${1:-gallery}" "${@:2}"
  ad_load_config
  (( $+functions[ad_buddy_cache] )) && ad_buddy_cache
}

hr() {
  local w=${COLUMNS:-80} i chunks=14 per rgb
  local sb="" hue=$(( RANDOM % 360 ))
  per=$(( (w - 1) / chunks ))
  for (( i = 0; i < chunks; i++ )); do
    rgb=($(ad_hsv2rgb $(( hue + 150.0 * i / chunks )) 0.6 0.85))
    sb+="$(ad_fg $rgb[1] $rgb[2] $rgb[3])${(l:per::─:)}"
  done
  print -r -- "${sb}${AD_ESC}[0m"
}

# lava: corner metaballs daemon (bgfx.py)
lava() {
  local pf="$AD_ROOT/bedazzle.lava.pid" action="$1"
  local running=0
  if [[ -f "$pf" ]] && kill -0 "$(<$pf)" 2>/dev/null; then running=1; fi
  if [[ "$action" == off ]] || (( running )) && [[ "$action" != on ]]; then
    (( running )) && { kill "$(<$pf)" 2>/dev/null; print -r -- " lava: off"; } || print -r -- " lava: not running"
    rm -f "$pf"; return
  fi
  (( running )) && { print -r -- " lava: already flowing"; return; }
  command $AD_PY "$AD_ROOT/bgfx.py" --pidfile "$pf" &!
  print $! > "$pf"
  print -r -- " lava: on ${AD_ESC}[2m(metaballs in the corner — 'lava' again to stop)${AD_ESC}[0m"
}

# pet: toggle the corner buddy on/off. The buddy is now painted cleanly in
# the top-right corner once per prompt (ad_buddy_precmd) in EVERY theme — no
# async daemon (that version stamped a mangled column down the screen). Any
# stale daemon from an older version is killed here.
pet() {
  local pf="$AD_ROOT/bedazzle.pet.pid"
  [[ -f "$pf" ]] && { kill "$(<$pf)" 2>/dev/null; rm -f "$pf"; }   # retire old daemon
  local action="$1"
  [[ -z "$action" ]] && { ad_on sprite && action=off || action=on; }
  if [[ "$action" == off ]]; then
    AD_FEAT[sprite]=0; ad_cfg_toggle sprite off
    print -r -- " pet: off ${AD_ESC}[2m(corner buddy hidden)${AD_ESC}[0m"
  else
    AD_FEAT[sprite]=1; ad_cfg_toggle sprite on
    (( $+functions[ad_buddy_cache] )) && ad_buddy_cache
    print -r -- " pet: on ${AD_ESC}[2m(${AD_SPRITE} lives in the top-right corner — 'pet' again to hide)${AD_ESC}[0m"
  fi
}

# termbg: living background daemon (kitty backend on Linux)
termbg() {
  local action="$1" name="$2"
  local pf="$AD_ROOT/termbg.pid"
  case "$action" in
    on)
      # clean slate: kill any stale daemon so exactly one runs current code
      [[ -f "$pf" ]] && kill "$(<$pf)" 2>/dev/null
      pkill -f "termbg.py daemon" 2>/dev/null
      rm -f "$pf"
      command $AD_PY "$AD_ROOT/termbg.py" once    # renders now + surfaces backend errors
      command $AD_PY "$AD_ROOT/termbg.py" daemon --pidfile "$pf" &!
      print $! > "$pf"
      print -r -- " termbg: on ${AD_ESC}[2m(background evolves per command — 'termbg' for options)${AD_ESC}[0m"
      ;;
    freeze)
      [[ -f "$pf" ]] && kill "$(<$pf)" 2>/dev/null; rm -f "$pf"
      print -r -- " termbg: frozen ${AD_ESC}[2m(current image stays; 'termbg on' resumes)${AD_ESC}[0m"
      ;;
    off)
      [[ -f "$pf" ]] && kill "$(<$pf)" 2>/dev/null; rm -f "$pf"
      command $AD_PY "$AD_ROOT/termbg.py" off
      ;;
    use|palette|overlay|opacity|once|"") command $AD_PY "$AD_ROOT/termbg.py" ${action:-status} $name ;;
    *) command $AD_PY "$AD_ROOT/termbg.py" "$action" "$name" ;;
  esac
}
wall() { [[ "$1" == off ]] && termbg off || termbg once; }
