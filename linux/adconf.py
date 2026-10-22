#!/usr/bin/env python3
"""
adconf.py — tiny config CLI over bedazzle.config.json.

One source of truth shared by the zsh integration (linux/*.zsh) and the
Python renderers (termbg.py reads `accent` from the same file). zsh reads
the whole config ONCE at startup via `dump-sh` (no per-prompt python), and
only shells out again when the user actually changes something.

Usage:
  adconf.py dump-sh                 emit shell assignments for `eval`
  adconf.py get <dotted.key>        print one value (features.fetch, accent…)
  adconf.py set <dotted.key> <val>  set + persist (val: true/false/number/str)
  adconf.py toggle <feature> on|off flip a feature flag
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)          # repo root (config lives beside bedazzle.ps1)
CONFIG = os.path.join(ROOT, "bedazzle.config.json")

DEFAULTS = {
    "accent": 215.0,
    "sprite": "cat",
    "hat": "daily",
    "theme": "p10k",                  # p10k | bedazzle | <any omz theme name>
    "logo": "planet",                 # fetch image: a name in logos.LOGOS, or "random"
    "logo_pool": [],                  # names "random" may roll; empty = all
    "logo_bands": False,              # color text logos in horizontal bands
    "features": {
        "fetch": True,        # system panel on startup
        "sprite": True,       # buddy in the prompt corner (bedazzle theme)
        "rightinfo": True,    # duration/status/clock, right-aligned
        "git": True,          # branch + state
        "venv": True,         # python venv chip
        "shortpath": True,    # fish-style path compression
        "title": True,        # tab/window title follows folder
        "airy": True,         # breathing room above the prompt
        "battery": True,      # battery % when present
        "weather": True,      # cached wttr.in temperature
        "spirits": False,     # kaomoji visitors (legacy)
        "rule": False,        # gradient rule line (legacy)
        "accent_p10k": False,  # tint p10k's segments with accent (best-effort; p10k configs vary)
        "pet_github": True,    # pet reacts to git + GitHub PR review comments
        "termbg_auto": True,   # start the living background automatically on login
    },
}


def load():
    cfg = json.loads(json.dumps(DEFAULTS))  # deep copy
    try:
        with open(CONFIG, encoding="utf-8-sig") as f:
            j = json.load(f)
    except (OSError, json.JSONDecodeError):
        return cfg
    if isinstance(j.get("accent"), (int, float)):
        cfg["accent"] = float(j["accent"])
    for k in ("sprite", "hat", "theme", "logo"):
        if isinstance(j.get(k), str):
            cfg[k] = j[k]
    if isinstance(j.get("logo_bands"), bool):
        cfg["logo_bands"] = j["logo_bands"]
    if isinstance(j.get("logo_pool"), list):
        cfg["logo_pool"] = [n for n in j["logo_pool"] if isinstance(n, str)]
    if isinstance(j.get("features"), dict):
        for name, val in j["features"].items():
            if name in cfg["features"]:
                cfg["features"][name] = bool(val)
    return cfg


def save(cfg):
    tmp = CONFIG + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    os.replace(tmp, CONFIG)


def _coerce(v):
    low = v.lower()
    if low in ("true", "on", "yes", "1"):
        return True
    if low in ("false", "off", "no", "0"):
        return False
    try:
        return float(v) if ("." in v or "e" in low) else int(v)
    except ValueError:
        return v


def _get(cfg, dotted):
    cur = cfg
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _shq(s):
    """POSIX single-quote escaping so the value is safe to `eval` in zsh —
    a hand-edited/corrupt config must never be able to execute code."""
    return "'" + str(s).replace("'", "'\\''") + "'"


def dump_sh(cfg):
    # scalars (single-quoted so $(), backticks, $vars etc. are inert)
    print(f"AD_ACCENT={_shq(cfg['accent'])}")
    print(f"AD_SPRITE={_shq(cfg['sprite'])}")
    print(f"AD_HAT={_shq(cfg['hat'])}")
    print(f"AD_THEME={_shq(cfg['theme'])}")
    # feature flags -> AD_FEAT associative array assignments (always 0/1)
    for name, val in cfg["features"].items():
        if name.isidentifier():                       # guard the array key too
            print(f'AD_FEAT[{name}]={1 if val else 0}')


def main(argv):
    cmd = argv[0] if argv else "dump-sh"
    cfg = load()

    if cmd == "dump-sh":
        dump_sh(cfg)
        return 0
    if cmd == "get" and len(argv) > 1:
        v = _get(cfg, argv[1])
        if isinstance(v, bool):
            print("true" if v else "false")
        elif v is not None:
            print(v)
        return 0 if v is not None else 1
    if cmd == "set" and len(argv) > 2:
        key, val = argv[1], _coerce(argv[2])
        if "." in key:
            top, sub = key.split(".", 1)
            cfg.setdefault(top, {})[sub] = val
        else:
            cfg[key] = val
        save(cfg)
        return 0
    if cmd == "toggle" and len(argv) > 2:
        name = argv[1]
        cfg["features"][name] = (argv[2].lower() in ("on", "true", "1", "yes"))
        save(cfg)
        return 0
    sys.stderr.write(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
