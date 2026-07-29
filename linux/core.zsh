# ═══════════════════════════════════════════════════════════════════════
#  bedazzle — core: colors, accent math, config (zsh port of bedazzle.ps1)
#  Sourced by init.zsh. No per-prompt python: config is read ONCE into
#  memory and only re-read when the user changes something.
# ═══════════════════════════════════════════════════════════════════════

typeset -g  AD_ROOT="${AD_ROOT:-${${(%):-%x}:A:h:h}}"   # repo root (…/ascii-art)
typeset -g  AD_LINUX="$AD_ROOT/linux"
typeset -g  AD_PY="python3"
typeset -g  AD_VENV_PY="$AD_ROOT/.venv/bin/python"
[[ -x "$AD_VENV_PY" ]] && AD_PY="$AD_VENV_PY"
typeset -g  AD_ESC=$'\033'

# in-memory config (loaded by ad_load_config)
typeset -gA AD_FEAT
typeset -g  AD_ACCENT=215.0 AD_SPRITE=cat AD_HAT=daily AD_THEME=p10k

ad_load_config() {
  local dump
  dump="$(command $AD_PY "$AD_LINUX/adconf.py" dump-sh 2>/dev/null)" || return 1
  eval "$dump"
}

ad_cfg_set()   { command $AD_PY "$AD_LINUX/adconf.py" set "$1" "$2" 2>/dev/null; }
ad_cfg_toggle(){ command $AD_PY "$AD_LINUX/adconf.py" toggle "$1" "$2" 2>/dev/null; }

# feature test: `ad_on fetch` -> true/false
ad_on() { [[ "${AD_FEAT[$1]:-0}" == 1 ]]; }

# ── color helpers ────────────────────────────────────────────────────────

# ad_hsv2rgb <h> <s> <v> -> echoes "r g b" (0-255)
# sector algorithm: avoids float modulo / abs (which zsh math lacks)
ad_hsv2rgb() {
  local -F h=$1 s=$2 v=$3 f p q t r g b
  local -i i
  while (( h >= 360 )); do h=$(( h - 360 )); done
  while (( h < 0 ));    do h=$(( h + 360 )); done
  i=$(( h / 60 ))                       # integer var truncates -> floor (h>=0)
  f=$(( h / 60.0 - i ))
  p=$(( v * (1 - s) ))
  q=$(( v * (1 - f * s) ))
  t=$(( v * (1 - (1 - f) * s) ))
  case $i in
    0) r=$v; g=$t; b=$p ;;
    1) r=$q; g=$v; b=$p ;;
    2) r=$p; g=$v; b=$t ;;
    3) r=$p; g=$q; b=$v ;;
    4) r=$t; g=$p; b=$v ;;
    *) r=$v; g=$p; b=$q ;;
  esac
  printf '%.0f %.0f %.0f' $(( r * 255 )) $(( g * 255 )) $(( b * 255 ))
}

# ad_fg <r> <g> <b> -> truecolor foreground escape
ad_fg() { printf '%s[38;2;%d;%d;%dm' "$AD_ESC" "$1" "$2" "$3"; }

# ad_accent [sat] [val] -> escape at the configured accent hue
ad_accent() {
  local rgb; rgb=($(ad_hsv2rgb $AD_ACCENT ${1:-0.62} ${2:-0.98}))
  ad_fg $rgb[1] $rgb[2] $rgb[3]
}
ad_accent2() {
  local rgb; rgb=($(ad_hsv2rgb $(( AD_ACCENT + 55 )) 0.55 0.95))
  ad_fg $rgb[1] $rgb[2] $rgb[3]
}
ad_reset() { printf '%s[0m' "$AD_ESC"; }

# rgb -> nearest xterm-256 index (for p10k segment colors, which want an int)
ad_rgb2xterm() {
  local -i r=$1 g=$2 b=$3 ri gi bi
  if (( r == g && g == b )); then       # grayscale ramp
    if (( r < 8 ));   then print -- 16;  return; fi
    if (( r > 248 )); then print -- 231; return; fi
    print -- $(( (r - 8) * 24 / 247 + 232 )); return
  fi
  ri=$(( (r * 5 + 127) / 255 ))         # +127 -> round to nearest of 0..5
  gi=$(( (g * 5 + 127) / 255 ))
  bi=$(( (b * 5 + 127) / 255 ))
  print -- $(( 16 + 36 * ri + 6 * gi + bi ))
}

# accent hue -> xterm-256 index (used to tint p10k)
ad_accent_xterm() {
  local rgb; rgb=($(ad_hsv2rgb $AD_ACCENT ${1:-0.62} ${2:-0.98}))
  ad_rgb2xterm $rgb[1] $rgb[2] $rgb[3]
}
