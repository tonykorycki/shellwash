#!/usr/bin/env python3
"""
logos.py — the images beside the fetch panel, and `bedazzle logo`.

Two kinds of logo, both tinted from the accent hue:
  pixel  a function hue -> grid of (r, g, b) | None, drawn in half blocks
  text   a .txt file in fastfetch's format: $1…$9 switch color, $$ is a "$"
Text logos load from logos/ in the repo, then ~/.config/shellwash/logos/,
where a file of the same name overrides the bundled one.

Usage:
  logos.py                          list logos, the current choice, the pool
  logos.py <name|random>            pick one, or roll from the pool each launch
  logos.py pool [all | add|rm <names…> | <names…>]
  logos.py bands on|off             color text logos in horizontal bands
  logos.py gallery                  preview every logo
  logos.py show <name>              print one logo
"""

import colorsys
import os
import random
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import adconf  # noqa: E402

ROOT = os.path.dirname(HERE)
BUNDLED = os.path.join(ROOT, "logos")
USER_DIR = os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"),
                        "shellwash", "logos")

W, H = 23, 14                 # pixel logo size; text logos size themselves
E = "\x1b["
RESET = E + "0m"
DIM = E + "2m"


def hsv(h, s, v):
    r, g, b = colorsys.hsv_to_rgb((h % 360) / 360.0, s, v)
    return int(r * 255), int(g * 255), int(b * 255)


def fg(rgb):
    return f"{E}38;2;{rgb[0]};{rgb[1]};{rgb[2]}m"


# ── pixel logos ───────────────────────────────────────────────────────────

def render(grid):
    lines = []
    for y in range(0, H, 2):
        parts = []
        for x in range(W):
            t = grid[y][x]
            b = grid[y + 1][x] if y + 1 < H else None
            if t is None and b is None:
                parts.append(RESET + " ")
            elif b is None:
                parts.append(f"{RESET}{fg(t)}▀")
            elif t is None:
                parts.append(f"{RESET}{fg(b)}▄")
            else:
                parts.append(f"{E}38;2;{t[0]};{t[1]};{t[2]};48;2;{b[0]};{b[1]};{b[2]}m▀")
        lines.append("".join(parts) + RESET)
    return lines


def planet(hue):
    cx, cy, r = 11.0, 6.5, 5.2
    c1, c2, c3, c4 = hsv(hue, .30, 1.0), hsv(hue, .55, .95), hsv(hue, .70, .72), hsv(hue, .80, .45)
    ring1, ring2 = hsv(hue + 55, .55, 1.0), hsv(hue + 55, .65, .65)
    grid = [[None] * W for _ in range(H)]
    for y in range(H):
        for x in range(W):
            dx, dy = (x - cx) * 0.92, y - cy
            in_planet = dx * dx + dy * dy <= r * r
            ex, ey = (x - cx) / 10.5, (y - cy + (x - cx) * 0.18) / 2.1
            ringv = ex * ex + ey * ey
            on_ring = abs(ringv - 1.0) < 0.22
            ring_front = y > (cy - (x - cx) * 0.18)
            px = None
            if in_planet:
                lx, ly = dx / r + 0.55, dy / r + 0.55
                d = (lx * lx + ly * ly) ** 0.5
                px = c1 if d < .55 else c2 if d < .95 else c3 if d < 1.35 else c4
            if on_ring and (not in_planet or ring_front):
                px = ring2 if ringv < 1.0 else ring1
            if px is None and (x * 7 + y * 13) % 41 == 0:
                px = (90, 95, 120)
            grid[y][x] = px
    return grid


PIXEL = {"planet": (planet, "ringed planet, pixel art")}


# ── text logos ────────────────────────────────────────────────────────────

# Bundled files in listing order; files in logos/ not named here list after.
DESCRIPTIONS = {
    "tux":       "Tux",
    "arch":      "Arch Linux",
    "debian":    "Debian swirl",
    "gentoo":    "Gentoo",
    "apple":     "classic Apple",
    "puffy":     "OpenBSD's Puffy",
    "freebsd":   "FreeBSD",
    "ubuntu":    "Ubuntu",
    "rhel":      "Red Hat Enterprise Linux",
    "slackware": "Slackware",
}


# Palette slot for each $n where a logo's marks assume fixed colors (Tux: white body,
# black outline, yellow beak), so the shapes keep their contrast once tinted.
SLOTS = {"tux": (2, 0, 1)}


def text_palette(hue):
    """Colors for $1…$9: accent, +55° secondary, their light and deep shades, neutrals."""
    return [hsv(hue, .62, .98), hsv(hue + 55, .55, .95), hsv(hue, .30, 1.0),
            hsv(hue, .75, .70), hsv(hue + 55, .30, 1.0), hsv(hue + 55, .70, .70),
            (200, 202, 212), (110, 115, 130), hsv(hue + 180, .50, .95)]


def band_colors(hue, n=6):
    """n horizontal bands sweeping from the secondary hue down past the accent."""
    return [hsv(hue + 55 - i * 95 / max(1, n - 1), .60, .97) for i in range(n)]


def render_text(src, hue, bands=False, slots=None):
    """fastfetch-format text -> (colored lines padded to one width, width).
    A color carries over line ends, as in fastfetch."""
    rows = src.rstrip("\n").split("\n")
    pal, strips = text_palette(hue), band_colors(hue)
    if slots:
        pal = [pal[i] for i in slots] + pal[len(slots):]
    parsed, color = [], 0
    for row in rows:
        segs, buf, j = [], "", 0
        start = color
        while j < len(row):
            ch, nxt = row[j], row[j + 1] if j + 1 < len(row) else ""
            if ch == "$" and nxt == "$":
                buf += "$"
                j += 2
            elif ch == "$" and nxt in "123456789" and nxt:
                if buf:
                    segs.append((color, buf))
                    buf = ""
                color = int(nxt) - 1
                j += 2
            else:
                buf += ch
                j += 1
        if buf:
            segs.append((color, buf))
        parsed.append((start, segs))
    width = max((sum(len(t) for _, t in segs) for _, segs in parsed), default=0)
    out = []
    for i, (start, segs) in enumerate(parsed):
        vis = sum(len(t) for _, t in segs)
        if bands:
            body = fg(strips[i * len(strips) // len(parsed)]) + "".join(t for _, t in segs)
        else:
            body = fg(pal[start]) + "".join(fg(pal[c]) + t for c, t in segs)
        out.append(body + RESET + " " * (width - vis))
    return out, width


# ── registry ──────────────────────────────────────────────────────────────

def discover():
    """name -> (kind, source, description); user files override bundled ones."""
    found = {n: ("pixel", fn, d) for n, (fn, d) in PIXEL.items()}
    bundled = _txt_names(BUNDLED)
    for n in [n for n in DESCRIPTIONS if n in bundled] + sorted(set(bundled) - set(DESCRIPTIONS)):
        found[n] = ("text", os.path.join(BUNDLED, n + ".txt"), DESCRIPTIONS.get(n, n))
    for n in sorted(_txt_names(USER_DIR)):
        found[n] = ("text", os.path.join(USER_DIR, n + ".txt"), "custom")
    return found


def _txt_names(d):
    try:
        return [f[:-4] for f in os.listdir(d) if f.endswith(".txt")]
    except OSError:
        return []


def refresh():
    global LOGOS
    LOGOS = discover()
    return LOGOS


LOGOS = discover()
DEFAULT = "planet"


def lines(name, hue, bands=False):
    """(lines, width) for one logo; every line is padded to width columns."""
    kind, src, _ = LOGOS[name]
    if kind == "pixel":
        return render(src(hue)), W
    with open(src, encoding="utf-8") as f:
        return render_text(f.read(), hue, bands, SLOTS.get(name))


# ── selection ─────────────────────────────────────────────────────────────

def pool(cfg):
    """Names `random` may roll: the configured pool's known names, else all."""
    names = [n for n in cfg.get("logo_pool", []) if n in LOGOS]
    return names or list(LOGOS)


def choose(cfg, rng=random):
    """The logo for this launch: the fixed choice, or a roll from the pool."""
    name = cfg.get("logo", DEFAULT)
    if name == "random":
        return rng.choice(pool(cfg))
    return name if name in LOGOS else DEFAULT


# ── CLI ───────────────────────────────────────────────────────────────────

def _acc(hue):
    return fg(hsv(hue, .62, .98))


def _unknown(names):
    bad = [n for n in names if n not in LOGOS]
    if bad:
        print(f" unknown logo: {', '.join(bad)}  (have: {', '.join(LOGOS)})")
    return bad


def cmd_list(cfg):
    acc, cur, members = _acc(cfg["accent"]), cfg.get("logo", DEFAULT), pool(cfg)
    restricted = bool([n for n in cfg.get("logo_pool", []) if n in LOGOS])
    bands = "on" if cfg.get("logo_bands") else "off"
    print()
    print(f"  {acc}logos{RESET}  (current: {acc}{cur}{RESET}"
          f"{DIM} · random pool: {len(members)} of {len(LOGOS)} · bands: {bands}{RESET})")
    for name, (_, _, desc) in LOGOS.items():
        mark = f"{acc}●{RESET}" if name == cur else " "
        tag = f"{acc}*{RESET}" if restricted and name in members else " "
        print(f"   {mark}{tag} {acc}{name:<10}{RESET} {DIM}{desc}{RESET}")
    print()
    print(f"  {DIM} bedazzle logo <name|random>          pick one, or roll each launch{RESET}")
    print(f"  {DIM} bedazzle logo pool [all|add|rm] …    limit what random rolls (* = in pool){RESET}")
    print(f"  {DIM} bedazzle logo bands on|off           rainbow-stripe the text logos{RESET}")
    print(f"  {DIM} bedazzle logo gallery                preview them all{RESET}")
    print(f"  {DIM} add your own: {USER_DIR}/<name>.txt{RESET}")
    print()


def cmd_pool(cfg, args):
    current = [n for n in cfg.get("logo_pool", []) if n in LOGOS]
    if not args:
        print(f" random pool: {', '.join(pool(cfg))}" + ("" if current else "  (all)"))
        return 0
    op, names = (args[0], args[1:]) if args[0] in ("add", "rm", "all") else ("set", args)
    if _unknown(names):
        return 1
    if op == "all":
        new = []
    elif op == "add":
        new = current + [n for n in names if n not in current]
    elif op == "rm":
        new = [n for n in (current or list(LOGOS)) if n not in names]
        if not new:
            print(" pool would be empty — use 'bedazzle logo pool all' for every logo")
            return 1
    else:
        new = list(dict.fromkeys(names))
    cfg["logo_pool"] = [] if sorted(new) == sorted(LOGOS) else new
    adconf.save(cfg)
    print(f" random pool -> {', '.join(pool(cfg))}" + ("" if cfg["logo_pool"] else "  (all)"))
    return 0


def cmd_bands(cfg, args):
    if not args or args[0] not in ("on", "off"):
        print(" usage: bedazzle logo bands on|off")
        return 1
    cfg["logo_bands"] = args[0] == "on"
    adconf.save(cfg)
    print(f" bands -> {args[0]}")
    return 0


def cmd_gallery(cfg):
    """Logos packed left to right by their own widths, a label under each."""
    hue, acc, members, cur = cfg["accent"], _acc(cfg["accent"]), pool(cfg), cfg.get("logo", DEFAULT)
    bands = cfg.get("logo_bands", False)
    gap, avail = 4, shutil.get_terminal_size((80, 24)).columns - 2
    row, used = [], 0
    rows = []
    for n in LOGOS:
        art, w = lines(n, hue, bands)
        if row and used + w > avail:
            rows.append(row)
            row, used = [], 0
        row.append((n, art, w))
        used += w + gap
    if row:
        rows.append(row)
    print()
    for row in rows:
        height = max(len(a) for _, a, _ in row)
        for i in range(height):
            print("  " + (" " * gap).join(a[i] if i < len(a) else " " * w for _, a, w in row))
        labels = []
        for n, _, w in row:
            text = ("● " if n == cur else "") + n
            labels.append(f"{acc if n in members else DIM}{text.center(w)}{RESET}")
        print("  " + (" " * gap).join(labels))
        print()
    return 0


def main(argv):
    cfg = adconf.load()
    if not argv or argv[0] in ("list", "ls"):
        cmd_list(cfg)
        return 0
    cmd, args = argv[0], argv[1:]
    if cmd == "pool":
        return cmd_pool(cfg, args)
    if cmd == "bands":
        return cmd_bands(cfg, args)
    if cmd == "gallery":
        return cmd_gallery(cfg)
    if cmd == "show" and args:
        if _unknown(args[:1]):
            return 1
        print()
        for ln in lines(args[0], cfg["accent"], cfg.get("logo_bands", False))[0]:
            print("  " + ln)
        print()
        return 0
    if cmd == "random" or cmd in LOGOS:
        cfg["logo"] = cmd
        adconf.save(cfg)
        note = f"  {DIM}(rolls from: {', '.join(pool(cfg))}){RESET}" if cmd == "random" else ""
        print(f" logo -> {_acc(cfg['accent'])}{cmd}{RESET}{note}")
        return 0
    _unknown([cmd])
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
