#!/usr/bin/env python3
"""
pet.py — a pinned shell buddy, the /buddy way.

Claude Code's /buddy cat lived beside the input box because Claude Code is
a full-screen TUI that repaints everything constantly. A shell can't do
that — so this daemon does the next best thing: it repaints ONE buddy at a
fixed spot in the viewport (top-right), transparently (only glyphs are
painted, and it erases exactly what it painted). No duplicates in your
scrollback, and it reacts live:

  command failed  -> startled ( o o ) !   (for a few seconds)
  long task done  -> happy    ( ^ ^ )
  away 4+ minutes -> asleep   ( - - ) zZ
  otherwise       -> idle, with blinks and tail flicks

The bedazzle prompt writes {ok, ms, count, ts, sprite, hat} to pet.json on
every command; this daemon polls it. Started/stopped by the `pet` command
(pidfile: bedazzle.pet.pid). Buddy art mirrors bedazzle.ps1 — keep in sync.
"""

import json
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
STATEFILE = os.path.join(HERE, "pet.json")
PIDFILE = None
if "--pidfile" in sys.argv:
    PIDFILE = sys.argv[sys.argv.index("--pidfile") + 1]

TOP = 1          # first viewport row the pet occupies
TICK = 0.45      # seconds per animation tick
REACT_SECS = 7   # how long fail/happy faces hold
SLEEP_SECS = 240

if os.name == "nt":
    import ctypes
    import struct

    try:
        OUT = open("CONOUT$", "w", encoding="utf-8", newline="")
    except OSError:
        OUT = sys.stdout

    def enable_vt():
        k32 = ctypes.windll.kernel32
        h = k32.CreateFileW("CONOUT$", 0xC0000000, 3, None, 3, 0, None)
        mode = ctypes.c_uint32()
        if k32.GetConsoleMode(h, ctypes.byref(mode)):
            k32.SetConsoleMode(h, mode.value | 0x0004)

    def term_size():
        k32 = ctypes.windll.kernel32
        h = k32.CreateFileW("CONOUT$", 0xC0000000, 3, None, 3, 0, None)
        csbi = ctypes.create_string_buffer(22)
        if k32.GetConsoleScreenBufferInfo(h, csbi):
            (_bx, _by, _cx, _cy, _wa,
             left, top, right, bottom, _mx, _my) = struct.unpack("hhhhHhhhhhh", csbi.raw)
            return right - left + 1, bottom - top + 1
        raise OSError("no console")
else:
    OUT = sys.stdout

    def enable_vt():
        pass

    def term_size():
        ts = os.get_terminal_size()
        return ts.columns, ts.lines


# ── buddy art (mirror of bedazzle.ps1 $ADBuddies) ───────────────────────

BUDDIES = {
    "duck": {"color": (255, 223, 92), "head": 4, "eyeRow": 1,
             "rows": ["   __", " <(. )___", "  (  ._> /", "   `---'"],
             "eyes": {"blink": " <(- )___", "fail": " <(o )___", "happy": " <(^ )___"}},
    "goose": {"color": (200, 204, 216), "head": 3, "eyeRow": 0,
              "rows": ["  (.>", "  ||", "_(__)_", " ^^^^"],
              "eyes": {"blink": "  (->", "fail": "  (o>", "happy": "  (^>"}},
    "blob": {"color": (126, 231, 135), "head": 4, "eyeRow": 1,
             "rows": [" .----.", "( .  . )", "(      )", " `----'"],
             "eyes": {"blink": "( -  - )", "fail": "( o  o )", "happy": "( ^  ^ )"}},
    "cat": {"color": (230, 200, 170), "head": 3, "eyeRow": 1,
            "rows": [" /\\_/\\", "( .  .)", "(  ω  )", "(\")_(\")"],
            "eyes": {"blink": "( -  -)", "fail": "( o  o)", "happy": "( ^  ^)"}},
    "dragon": {"color": (248, 110, 90), "head": 4, "eyeRow": 1,
               "rows": [" /^\\  /^\\", "<  .  .  >", "(   ~~   )", " `-vvvv-'"],
               "eyes": {"blink": "<  -  -  >", "fail": "<  o  o  >", "happy": "<  ^  ^  >"}},
    "octopus": {"color": (255, 121, 198), "head": 4, "eyeRow": 1,
                "rows": [" .----.", "( .  . )", "(______)", "/\\/\\/\\/\\"],
                "eyes": {"blink": "( -  - )", "fail": "( o  o )", "happy": "( ^  ^ )"}},
    "owl": {"color": (210, 180, 140), "head": 4, "eyeRow": 1,
            "rows": [" /\\  /\\", "((.)(.))", "(  ><  )", " `----'"],
            "eyes": {"blink": "((-)(-))", "fail": "((o)(o))", "happy": "((^)(^))"}},
    "penguin": {"color": (180, 200, 230), "head": 3, "eyeRow": 1,
                "rows": [" .---.", " (.>.)", " /(   )\\", "  `---'"],
                "eyes": {"blink": " (->-)", "fail": " (o>o)", "happy": " (^>^)"}},
    "turtle": {"color": (140, 200, 120), "head": 3, "eyeRow": 1,
               "rows": [" _,--._", "( .  . )", "/[______]\\", "  ||  ||"],
               "eyes": {"blink": "( -  - )", "fail": "( o  o )", "happy": "( ^  ^ )"}},
    "snail": {"color": (220, 180, 130), "head": 6, "eyeRow": 0,
              "rows": [" .   .--.", "  \\ ( @ )", "   \\_`--'", " ~~~~~~~~"],
              "eyes": {"blink": " -   .--.", "fail": " o   .--.", "happy": " ^   .--."}},
    "ghost": {"color": (187, 154, 247), "head": 4, "eyeRow": 1,
              "rows": [" .----.", "/ .  . \\", "|      |", "~`~``~`~"],
              "eyes": {"blink": "/ -  - \\", "fail": "/ o  o \\", "happy": "/ ^  ^ \\"}},
    "axolotl": {"color": (255, 150, 170), "head": 5, "eyeRow": 1,
                "rows": ["}~(______)~{", "}~( .  . )~{", "  ( .--. )", "  (_/  \\_)"],
                "eyes": {"blink": "}~( -  - )~{", "fail": "}~( o  o )~{", "happy": "}~( ^  ^ )~{"}},
    "capybara": {"color": (200, 160, 110), "head": 4, "eyeRow": 1,
                 "rows": [" n_____n", "( .   . )", "(   oo  )", " `-----'"],
                 "eyes": {"blink": "( -   - )", "fail": "( o   o )", "happy": "( ^   ^ )"}},
    "cactus": {"color": (120, 200, 110), "head": 4, "eyeRow": 1,
               "rows": ["n  ___  n", "| |. .| |", "|_|   |_|", "  |   |"],
               "eyes": {"blink": "| |- -| |", "fail": "| |o o| |", "happy": "| |^ ^| |"}},
    "robot": {"color": (110, 220, 255), "head": 4, "eyeRow": 1,
              "rows": [" .[|||].", "[ .  . ]", "[ ==== ]", " `----'"],
              "eyes": {"blink": "[ -  - ]", "fail": "[ x  x ]", "happy": "[ ^  ^ ]"}},
    "rabbit": {"color": (235, 235, 235), "head": 4, "eyeRow": 1,
               "rows": ["  (\\__/)", " ( .  . )", "=(  ..  )=", " (\")__(\")"],
               "eyes": {"blink": " ( -  - )", "fail": " ( o  o )", "happy": " ( ^  ^ )"}},
    "mushroom": {"color": (255, 130, 120), "head": 4, "eyeRow": 2,
                 "rows": [".-o-OO-o-.", "(________)", "  |.  .|", "  |____|"],
                 "eyes": {"blink": "  |-  -|", "fail": "  |o  o|", "happy": "  |^  ^|"}},
    "chonk": {"color": (200, 204, 216), "head": 4, "eyeRow": 1,
              "rows": [" /\\   /\\", "( .   . )", "(   ..  )", " `-----'"],
              "eyes": {"blink": "( -   - )", "fail": "( o   o )", "happy": "( ^   ^ )"}},
}

# ── pixel-art buddy sprites (used by termbg's nowplaying scene) ─────────
# Real bitmaps, not faked from the ASCII rows above: each sprite is a list
# of rows, each character a key into PIXEL_PALETTE ('.'/' ' = transparent).
# Ported 1:1 from the bedazzle nowplaying design handoff.

_PIXEL_PALETTE_HEX = {
    "k": "#22222e", "w": "#f2efe6", "W": "#ffffff", "d": "#9a9fac", "D": "#6d7280",
    "o": "#f29b3d", "O": "#d76a1e", "y": "#f6c944", "Y": "#e0a91f",
    "p": "#f58fb6", "P": "#d95a8c", "r": "#e0503a", "R": "#b23528",
    "g": "#6fae5a", "G": "#4d8a43", "t": "#46b6a4", "c": "#57c2d6",
    "b": "#5b7fd6", "u": "#9a6fd4", "m": "#cf6fd0", "n": "#b07a4c", "N": "#7c5533",
    "s": "#c9ccd4", "S": "#8f94a3", "e": "#2a2a38",
}
PIXEL_PALETTE = {k: tuple(int(h[i:i + 2], 16) for i in (1, 3, 5)) for k, h in _PIXEL_PALETTE_HEX.items()}

PIXEL_SPRITES = {
    "duck": ["......kkkk....", ".....kyyyyk...", "....kyWeyyk...", "...kkyyyyyk...",
             "kkkkyyyyyoOk..", "kyyppyyyyyk...", "kyyyyyyyyyk...", "kyyyyyyyyyyk..",
             ".kyyyyyyyyk...", "..kkkkkkkk...."],
    "goose": ["...kk.........", "..kwwk........", "..kWek........", "..kwwkkk......",
              "..kwwyOk......", ".kwppwk.......", ".kwwwwk.......", "kwwwwwwwk.....",
              "kwwwwwwwwwk...", "kwwwwwwwwwk...", ".kwwwwwwwk....", "..kkkkkkk....."],
    "blob": ["...kkkk...", ".kttttttk.", "kttttttttk", "ktWeetteWk", "kteetteetk",
             "ktpttttptk", "kttttttttk", ".kttttttk.", ".k.kkkk.k."],
    "cat": ["..kk......kk..", ".kddk....kook.", ".kddkkkkkkook.", "kwwwwwwwwwwwwk",
            "kwWeewwwweeWwk", "kwweewwwweewwk", "kppwwwwwwwwppk", "kwwwwwppwwwwwk",
            "kwwwwwwwwwwwwk", ".kwwwwwwwwwwk.", ".kwkkwwwwkkwk.", "..kk..kk..kk.."],
    "dragon": [".k.......k..", "kRk.....kRk.", "kRkkkkkkkRk.", "krrrrrrrrrrk",
               "krWeerreeWrk", "krpprrrrpprk", "krrRRRRRRrrk", "kRrrrrrrrRk.",
               ".krrrrrrrk..", "..krrrrk....", "kRk....kRk..", ".k......k..."],
    "octopus": ["..kkkkkk..", ".kmmmmmmk.", "kmmmmmmmmk", "kmWeemeeWk", "kmpmmmmpmk",
                "kmmmPPmmmk", "kmmmmmmmmk", "kmkmkmkmkm", "kmkmkmkmkm", ".k.k.k.k.k"],
    "owl": [".k......k.", ".kNk..kNk.", "kNnnnnnnNk", "knWWnnWWnk", "knWeWWeWnk",
            "knppooppnk", "knnnnnnnnk", "knNNNNNNnk", ".knnnnnnk.", "..kn..nk.."],
    "penguin": ["..kkkk..", ".kkkkkk.", "kkwwwwkk", "kkWeewkk", "kkwOOwkk",
                "kpkwwkpk", "kkwwwwkk", "kkwwwwkk", "kkwwwwkk", "kkkwwkkk", ".OO..OO."],
    "turtle": [".......kkkk...", ".....kkggggkk.", "kkkkkgGGggGgk.", "kWeekgggggggk.",
               "kgppkgGGggGgk.", ".kkkkgggggggk.", "....kkgggggkk.", "....gk.kk.kg.."],
    "snail": [".k.k.......", ".k.k.kkkk..", ".knnkuuuuk.", "kWenuNwNuk.", "knnnuNNNuk.",
              "knppuuuuk..", ".knnnuuk...", "..kkkkk...."],
    "ghost": ["..kkkk..", ".kwwwwk.", "kwwwwwwk", "kWeewewk", "kpwwwwpk",
              "kwwwwwwk", "kwwwwwwk", "kwkwkwkw"],
    "axolotl": ["..p.....p..", ".pk.....kp.", "ppkkpppkkpp", ".kppppppppk", "kpWeepeeWpk",
                "kpppppppppk", "kpppPPPppk.", "kpppppppppk", ".kpppppppk.", "..kppppppk.",
                "..kpk.kpk.."],
    "capybara": ["..kkkkkkkk..", ".knnnnnnnnk.", "knnnnnnnnnnk", "knWeenneeWnk", "knppnnnnppnk",
                 "knnnnNNnnnnk", "knnnnnnnnnnk", ".knnnnnnnnk.", ".knkknnkknk.", "..kk...kk..."],
    "cactus": ["....kk......", ".kk.kgk.....", "kgk.kgk..kk.", "kgkkkgkkkgk.", ".kgWeggeeWk.",
               ".kgppPPppgk.", ".kgggggggk..", ".kgGgGgGgk..", ".knnnnnnnk..", "..knnnnnk...",
               "..knnnnnk...", "...kkkkk...."],
    "robot": ["....cc....", "....k.....", ".kkkkkkkk.", "kssssssssk", "ksccccccsk",
              "kscWeeWcsk", "ksccccccsk", "kssssssssk", "ksppssppsk", "kssssssssk", ".kk.kk.kk."],
    "rabbit": [".kk....kk.", ".kwk..kwk.", ".kpk..kpk.", ".kwkkkkwk.", "kwwwwwwwwk",
               "kWeewweeWk", "kwppwwppwk", "kwwwppwwwk", "kwwwwwwwwk", ".kwkkkkwk."],
    "mushroom": ["..kkkkkk..", ".krrWrrrk.", "krrrrWrrrk", "krWrrrrrWk", "krrrrrWrrk",
                 "kkkkkkkkkk", ".kwwwwwwk.", ".kWeewwek.", ".kpwwwwpk.", ".kwwPPwwk.",
                 ".kkwwwwkk."],
    "chonk": [".kk........kk.", ".kDk......kDk.", ".kDkkkkkkkkDk.", "kDDDDDDDDDDDDk",
              "kDWeeDDDDeeWDk", "kDppDDDDDDppDk", "kDDDDDppDDDDDk", "kDDDDDDDDDDDDk",
              "kDDDDDDDDDDDDk", ".kDDDDDDDDDDk.", ".kDkk.kk.kkDk.", "..kk......kk.."],
}


HATS = {
    "beanie": ("(___)", (126, 231, 135)),
    "propeller": ("-+-", (126, 231, 135)),
    "tophat": ("[___]", (110, 160, 255)),
    "tinyduck": (",>", (110, 160, 255)),
    "crown": ("\\^^^/", (190, 130, 255)),
    "wizard": ("/^\\", (190, 130, 255)),
    "halo": ("(   )", (255, 200, 60)),
}

BUDDY_ORDER = ["duck", "goose", "blob", "cat", "dragon", "octopus", "owl",
               "penguin", "turtle", "snail", "ghost", "axolotl", "capybara",
               "cactus", "robot", "rabbit", "mushroom", "chonk"]

HAT_RARITY = {"beanie": "uncommon", "propeller": "uncommon", "tophat": "rare",
              "tinyduck": "rare", "crown": "epic", "wizard": "epic", "halo": "legendary"}

RARITY_COLORS = {"common": (140, 145, 160), "uncommon": (126, 231, 135),
                 "rare": (110, 160, 255), "epic": (190, 130, 255),
                 "legendary": (255, 200, 60)}

CONFIG = os.path.join(HERE, "bedazzle.config.json")
E = "\x1b["
RESET = E + "0m"
DIM = E + "2m"


def load_config():
    try:
        with open(CONFIG, encoding="utf-8-sig") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def save_config(cfg):
    tmp = CONFIG + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    os.replace(tmp, CONFIG)


def fg(rgb):
    return f"{E}38;2;{rgb[0]};{rgb[1]};{rgb[2]}m"


def roll_hat(rng):
    """common 60% (bare) · uncommon 25 · rare 10 · epic 4 · legendary 1."""
    roll = rng.randrange(1000)
    if roll < 600:
        return None
    if roll < 850:
        return rng.choice(["beanie", "propeller"])
    if roll < 950:
        return rng.choice(["tophat", "tinyduck"])
    if roll < 990:
        return rng.choice(["crown", "wizard"])
    return "halo"


def daily_hat():
    import datetime
    seed = int(datetime.date.today().strftime("%Y%m%d"))
    for ch in os.environ.get("USER", "user"):
        seed += ord(ch) * 7
    return roll_hat(random.Random(seed))


def resolve_hat(name):
    """Config stores 'daily'/'none'/<hatname>; the daemon needs a real hat."""
    if not name or name == "none":
        return None
    if name == "daily":
        return daily_hat()
    return name if name in HATS else None


# ── github/git glance state (written by linux/ghpoll.py) ─────────────────

def read_ghstate():
    try:
        with open(os.path.join(HERE, "github.state.json"), encoding="utf-8-sig") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


# ── on-demand subcommands (gallery / roll / sprite / hat) ────────────────

def cmd_gallery():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    cfg = load_config()
    hue = float(cfg.get("accent", 215.0))
    import colorsys
    r, g, b = colorsys.hsv_to_rgb((hue % 360) / 360, 0.62, 0.98)
    acc = fg((int(r * 255), int(g * 255), int(b * 255)))
    cur = cfg.get("sprite", "cat")
    print()
    print(f"  {acc}shell buddies{RESET} {DIM}(bedazzle sprite <name> · buddy roll to gamble){RESET}")
    print()
    per, cw = 4, 17
    for gi in range(0, len(BUDDY_ORDER), per):
        group = BUDDY_ORDER[gi:gi + per]
        print("  " + "".join(
            f"{DIM}{(n + (' *' if n == cur else '')).ljust(cw)}{RESET}" for n in group))
        for row in range(4):
            line = "  "
            for n in group:
                bd = BUDDIES[n]
                line += f"{fg(bd['color'])}{bd['rows'][row].ljust(cw)}{RESET}"
            print(line)
        print()
    print(f"  {acc}hats{RESET} {DIM}(daily draw per day — or 'bedazzle hat <name>'){RESET}")
    hatline = "  "
    for hn, (art, _c) in HATS.items():
        rc = RARITY_COLORS[HAT_RARITY[hn]]
        hatline += f"{fg(rc)}{art}{RESET}{DIM} {hn}  {RESET}"
    print(hatline)
    rar = "  "
    for name, pct in [("common", "60%"), ("uncommon", "25%"), ("rare", "10%"),
                      ("epic", "4%"), ("legendary", "1%")]:
        rar += f"{fg(RARITY_COLORS[name])}■ {name} {pct}{RESET}  "
    print(rar)
    print(f"\n  {DIM}today: {cur}, {resolve_hat(cfg.get('hat', 'daily')) or 'bare-headed'}{RESET}\n")


def cmd_roll():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    rng = random.Random()
    buddy = rng.choice(BUDDY_ORDER)
    hat = roll_hat(rng)
    cfg = load_config()
    cfg["sprite"] = buddy
    cfg["hat"] = hat if hat else "none"
    save_config(cfg)
    hue = float(cfg.get("accent", 215.0))
    import colorsys
    r, g, b = colorsys.hsv_to_rgb((hue % 360) / 360, 0.62, 0.98)
    acc = fg((int(r * 255), int(g * 255), int(b * 255)))
    print()
    if hat:
        rc = RARITY_COLORS[HAT_RARITY[hat]]
        print(f"  you rolled: {acc}{buddy}{RESET} wearing {fg(rc)}{hat}{RESET} "
              f"{fg(rc)}({HAT_RARITY[hat]}!){RESET}")
    else:
        print(f"  you rolled: {acc}{buddy}{RESET} {DIM}(bare-headed — common){RESET}")
    rows, colors = build_rows(buddy, hat, "happy")
    for row, col in zip(rows, colors):
        print(f"    {fg(col)}{row}{RESET}")
    print(f"\n  {DIM}('bedazzle hat daily' to return to the daily draw){RESET}\n")


def cmd_render(sprite):
    """Emit the current buddy's art for each state, pre-colored, for the zsh
    inline prompt buddy to cache — so the roster/escaping lives in ONE place
    (here) instead of being re-encoded fragilely in zsh. One line per state:
        <state>\\t<width>\\t<coloredrow>\\x1f<coloredrow>...
    """
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    cfg = load_config()
    if not sprite or sprite in ("current", ""):
        sprite = cfg.get("sprite", "cat")
    if sprite == "random":
        sprite = random.choice(BUDDY_ORDER)
    if sprite not in BUDDIES:
        sprite = "cat"
    hat = resolve_hat(cfg.get("hat", "daily"))
    for state in ("idle", "blink", "fail", "happy", "notify"):
        rows, colors = build_rows(sprite, hat, state)
        w = max(len(r) for r in rows)
        parts = [f"{fg(col)}{r.ljust(w)}\x1b[0m" for r, col in zip(rows, colors)]
        sys.stdout.write(f"{state}\t{w}\t" + "\x1f".join(parts) + "\n")


def cmd_set(key, value):
    cfg = load_config()
    if key == "sprite":
        allowed = BUDDY_ORDER + ["random"]
        if value == "random":
            value = random.choice(BUDDY_ORDER)
        if value not in allowed:
            print(f" buddies: {', '.join(BUDDY_ORDER)}, random")
            return
    elif key == "hat":
        if value not in list(HATS) + ["daily", "none"]:
            print(f" hats: {', '.join(HATS)}, daily, none")
            return
    cfg[key] = value
    save_config(cfg)
    print(f" {key} -> {value}")


def read_petstate():
    try:
        with open(STATEFILE, encoding="utf-8-sig") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError, ValueError):
        return {}


def build_rows(name, hat, state):
    b = BUDDIES.get(name, BUDDIES["cat"])
    rows = list(b["rows"])
    eyes = b.get("eyes", {})
    if state == "fail" and "fail" in eyes:
        rows[b["eyeRow"]] = eyes["fail"]
    elif state in ("blink", "sleep") and "blink" in eyes:
        rows[b["eyeRow"]] = eyes["blink"]
    elif state in ("happy", "notify") and "happy" in eyes:
        rows[b["eyeRow"]] = eyes["happy"]
    if state == "fail":
        rows[0] = rows[0] + "  !"
    if state == "sleep":
        rows[0] = rows[0] + " zZ"
    if state == "notify":
        rows[0] = rows[0] + " ✉!"
    hatrow = None
    if hat and hat in HATS:
        art, _ = HATS[hat]
        start = max(0, b["head"] - len(art) // 2)
        hatrow = " " * start + art
    out = ([hatrow] if hatrow else []) + rows
    colors = ([HATS[hat][1]] if hatrow else []) + [b["color"]] * len(rows)
    return out, colors


def paint(cells_prev, rows, colors, col0):
    """Paint glyphs, erase what was painted before and is now gone."""
    new_cells = {}
    parts = []
    for y, (row, col) in enumerate(zip(rows, colors)):
        r, g, b = col
        for x, ch in enumerate(row):
            if ch != " ":
                new_cells[(y, x)] = (ch, col)
    for (y, x) in cells_prev:
        if (y, x) not in new_cells:
            parts.append(f"\x1b[{TOP + y};{col0 + x}H\x1b[0m ")
    for (y, x), (ch, (r, g, b)) in new_cells.items():
        parts.append(f"\x1b[{TOP + y};{col0 + x}H\x1b[38;2;{r};{g};{b}m{ch}")
    if parts:
        OUT.write("\x1b7" + "".join(parts) + "\x1b[0m\x1b8")
        OUT.flush()
    return new_cells


def erase(cells, col0):
    parts = [f"\x1b[{TOP + y};{col0 + x}H\x1b[0m " for (y, x) in cells]
    if parts:
        OUT.write("\x1b7" + "".join(parts) + "\x1b8")
        OUT.flush()


def main():
    enable_vt()
    born = time.time()
    cells = {}
    last_col0 = None
    tick = 0
    blink_until = 0
    notify_until = 0.0
    seen_comments = None
    try:
        while True:
            time.sleep(TICK)
            tick += 1
            if PIDFILE and time.time() - born > 3.0 and not os.path.exists(PIDFILE):
                return
            st = read_petstate()
            name = st.get("sprite", "cat")
            hat = resolve_hat(st.get("hat"))
            now = time.time()
            ts = float(st.get("ts", 0))
            since = now - ts if ts else 1e9

            # GitHub PR review comments -> the pet perks up with a "✉!"
            gh = read_ghstate()
            comments = int(gh.get("pr_comments", 0))
            if seen_comments is None:
                seen_comments = comments               # baseline; don't alert on boot
            elif comments > seen_comments:
                notify_until = now + REACT_SECS
            seen_comments = comments

            if not st.get("ok", True) and since < REACT_SECS:
                state = "fail"
            elif now < notify_until:
                state = "notify"
            elif st.get("ms", 0) > 10000 and since < REACT_SECS:
                state = "happy"
            elif since > SLEEP_SECS:
                state = "sleep"
            elif tick < blink_until:
                state = "blink"
            else:
                state = "idle"
                if random.random() < 0.10:
                    blink_until = tick + 1
            rows, colors = build_rows(name, hat, state)
            width = max(len(r) for r in rows)
            try:
                cols, _ = term_size()
            except OSError:
                return
            col0 = max(1, cols - width - 1)
            if last_col0 is not None and col0 != last_col0:
                erase(cells, last_col0)
                cells = {}
            last_col0 = col0
            try:
                cells = paint(cells, rows, colors, col0)
            except OSError:
                return
    finally:
        try:
            if cells and last_col0 is not None:
                erase(cells, last_col0)
        except OSError:
            pass


def dispatch(argv):
    # strip --flag pairs (e.g. --pidfile <path>) to find the positional cmd
    pos = []
    skip = False
    for a in argv:
        if skip:
            skip = False
            continue
        if a.startswith("--"):
            skip = a in ("--pidfile",)
            continue
        pos.append(a)
    cmd = pos[0] if pos else "daemon"
    if cmd == "gallery":
        cmd_gallery()
    elif cmd == "roll":
        cmd_roll()
    elif cmd == "render":
        cmd_render(pos[1] if len(pos) > 1 else "current")
    elif cmd in ("sprite", "hat") and len(pos) > 1:
        cmd_set(cmd, pos[1])
    elif cmd in ("sprite", "hat"):
        cmd_set(cmd, "")  # prints the valid list
    else:
        main()  # daemon (default when launched with just --pidfile)


if __name__ == "__main__":
    dispatch(sys.argv[1:])
