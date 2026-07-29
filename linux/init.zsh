# ═══════════════════════════════════════════════════════════════════════
#  bedazzle — entrypoint. Source this ONE line from ~/.zshrc, AFTER
#  oh-my-zsh + p10k have loaded:
#
#     source ~/ascii-art/linux/init.zsh
#
#  Keeps p10k as the default prompt; layers the addons + toggles on top.
#  `bedazzle` shows everything. Undo: remove that source line.
# ═══════════════════════════════════════════════════════════════════════

# only in interactive shells
[[ -o interactive ]] || return 0

typeset -g AD_ROOT="${${(%):-%x}:A:h:h}"

source "$AD_ROOT/linux/core.zsh"
ad_load_config || {
  print -r -- "bedazzle: could not load config (is python3 available?)" >&2
  return 1
}
source "$AD_ROOT/linux/buddies.zsh"
source "$AD_ROOT/linux/prompt.zsh"
source "$AD_ROOT/linux/hooks.zsh"
source "$AD_ROOT/linux/commands.zsh"

autoload -Uz add-zsh-hook

# our feed hooks run FIRST (prepended) so ad_feed_precmd sees the true $?,
# then the inline buddy prints, then the theme draws its prompt below.
add-zsh-hook preexec ad_feed_preexec
add-zsh-hook precmd  ad_feed_precmd
add-zsh-hook precmd  ad_buddy_precmd
precmd_functions=(ad_feed_precmd ad_buddy_precmd ${precmd_functions:#(ad_feed_precmd|ad_buddy_precmd)})

# venv Activate would prepend "(.venv) " — the ⚡ chip / p10k segment covers it
export VIRTUAL_ENV_DISABLE_PROMPT=1

# apply the saved theme choice (default p10k, already loaded by .zshrc)
if [[ "$AD_THEME" == bedazzle ]]; then
  ad_theme_apply bedazzle
elif [[ "$AD_THEME" != (p10k|powerlevel10k) ]]; then
  ad_theme_apply "$AD_THEME" 2>/dev/null
fi
ad_apply_accent_to_p10k

# pre-render the inline buddy art once (cheap; refreshed on sprite/hat change)
ad_on sprite && (( $+functions[ad_buddy_cache] )) && ad_buddy_cache

# startup niceties. NOTE: the fetch login panel is printed from a small
# block at the TOP of ~/.zshrc (before p10k's instant prompt) so it never
# trips the "console output during initialization" warning — see install.sh.
ad_on weather && ad_refresh_weather

# termbg on by default: start the daemon once (first interactive shell wins;
# others see the live pidfile and skip). Only when a real display backend
# exists — kitty here — so it's a no-op in a plain VTE terminal.
if ad_on termbg_auto; then
  if [[ ! -f "$AD_ROOT/termbg.pid" ]] || ! kill -0 "$(<$AD_ROOT/termbg.pid 2>/dev/null)" 2>/dev/null; then
    if [[ -n "$KITTY_WINDOW_ID" || "$TERM" == xterm-kitty || -n "$WT_SESSION" ]]; then
      command $AD_PY "$AD_ROOT/termbg.py" daemon --pidfile "$AD_ROOT/termbg.pid" >/dev/null 2>&1 &!
      print $! > "$AD_ROOT/termbg.pid" 2>/dev/null
      command $AD_PY "$AD_ROOT/termbg.py" once >/dev/null 2>&1 &!
    fi
  fi
fi
