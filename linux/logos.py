#!/usr/bin/env python3
"""
logos.py — the pixel images beside the fetch panel, and `bedazzle logo`.

Every logo is a function hue -> grid: H rows of W cells, each an (r, g, b)
tuple or None for transparent. render() turns a grid into half-block lines
(two pixel rows per text row), so a logo never deals with escape codes.
Colors come from the accent hue, so per-machine accents carry over.

Usage:
  logos.py                          list logos, the current choice, the pool
  logos.py <name|random>            pick one, or roll from the pool each launch
  logos.py pool [all | add|rm <names…> | <names…>]
  logos.py gallery                  preview every logo side by side
  logos.py show <name>              print one logo
"""

import colorsys
import math
import os
import random
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import adconf  # noqa: E402

W, H = 23, 14                 # pixels; fetch.py pads its left column to W
E = "\x1b["
RESET = E + "0m"
DIM = E + "2m"


def hsv(h, s, v):
    r, g, b = colorsys.hsv_to_rgb((h % 360) / 360.0, s, v)
    return int(r * 255), int(g * 255), int(b * 255)


def ramp(hue):
    """Four shades at one hue, lightest first — the shared logo palette."""
    return hsv(hue, .30, 1.0), hsv(hue, .55, .95), hsv(hue, .70, .72), hsv(hue, .80, .45)


def blank():
    return [[None] * W for _ in range(H)]


def stars(grid, color=(90, 95, 120)):
    """Sparse fixed starfield in the cells a logo left empty."""
    for y in range(H):
        for x in range(W):
            if grid[y][x] is None and (x * 7 + y * 13) % 41 == 0:
                grid[y][x] = color
    return grid


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
                parts.append(f"{RESET}{E}38;2;{t[0]};{t[1]};{t[2]}m▀")
            elif t is None:
                parts.append(f"{RESET}{E}38;2;{b[0]};{b[1]};{b[2]}m▄")
            else:
                parts.append(f"{E}38;2;{t[0]};{t[1]};{t[2]};48;2;{b[0]};{b[1]};{b[2]}m▀")
        lines.append("".join(parts) + RESET)
    return lines


# ── logos ─────────────────────────────────────────────────────────────────

def planet(hue):
    cx, cy, r = 11.0, 6.5, 5.2
    c1, c2, c3, c4 = ramp(hue)
    ring1, ring2 = hsv(hue + 55, .55, 1.0), hsv(hue + 55, .65, .65)
    grid = blank()
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
            grid[y][x] = px
    return stars(grid)


def synthwave(hue):
    """Striped sun setting over a perspective grid floor."""
    top, bot = hsv(hue + 55, .55, 1.0), hsv(hue, .75, .95)
    floor, line, rim = hsv(hue, .80, .16), hsv(hue, .70, .55), hsv(hue + 55, .45, 1.0)
    cx, cy, r, horizon = 11.0, 8.0, 7.0, 8
    grid = blank()
    for y in range(horizon):
        t = max(0.0, min(1.0, (y - (cy - r)) / (horizon - (cy - r))))
        col = tuple(int(a + (b - a) * t) for a, b in zip(top, bot))
        for x in range(W):
            dx, dy = (x - cx) * 0.92, y + 0.5 - cy
            if dx * dx + dy * dy <= r * r and y not in (4, 6):
                grid[y][x] = col
    for y in range(horizon, H):
        for x in range(W):
            grid[y][x] = rim if y == horizon else line if y in (horizon + 2, horizon + 5) else floor
        if y > horizon:
            vy = horizon - 2                  # vanishing point, just above the horizon
            for k in range(-2, 3):
                x = round(cx + k * 7.0 * (y - vy) / (H - 1 - vy))
                if 0 <= x < W:
                    grid[y][x] = line
    return stars(grid)


def blackhole(hue):
    """Event horizon, a tilted accretion disk, and its lensed far side."""
    c1, c2, c3, c4 = ramp(hue)
    shades = (c1, c2, c3, c4)
    shadow = (12, 10, 18)
    cx, cy, rs = 11.0, 7.0, 3.4
    grid = blank()
    for y in range(H):
        for x in range(W):
            dx, dy = (x - cx) * 0.92, y - cy
            d = (dx * dx + dy * dy) ** 0.5
            ex, ey = (x - cx) / 11.5, (y - cy) / 1.1
            e = ex * ex + ey * ey
            # brighter on the approaching (left) side
            disk = shades[min(3, max(0, int(e * 4) - (1 if x < cx else 0)))]
            px = disk if e <= 1.0 else None
            if rs <= d < rs + (1.4 if y < cy else 0.7):      # lensed ring, fat on top
                px = c1 if d < rs + 0.5 else c2 if y < cy else c3
            if d < rs:
                px = disk if y == cy else shadow
            grid[y][x] = px
    return stars(grid)


def scope(hue):
    """Oscilloscope: bezel, graticule, and a phosphor sine trace."""
    c1, c2, c3, _ = ramp(hue)
    frame, frame_hi = (58, 62, 74), (92, 97, 112)
    bg, grat = hsv(hue, .55, .16), hsv(hue, .45, .34)
    glow = hsv(hue, .70, .48)
    x0, x1, y0, y1 = 2, 16, 1, 10
    grid = blank()
    for y in range(H - 1):
        for x in range(W):
            corner = (x in (0, W - 1)) and (y in (0, H - 2))
            if not corner:
                grid[y][x] = frame_hi if y == 0 else frame
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            on_grat = (x - x0) % 4 == 0 and (y - y0) % 3 == 0
            mid = x == (x0 + x1) // 2 or y == (y0 + y1 + 1) // 2
            grid[y][x] = grat if on_grat or (mid and (x + y) % 2 == 0) else bg
    prev = None
    for x in range(x0, x1 + 1):
        yy = round((y0 + y1) / 2 - 3.6 * math.sin(2 * math.pi * (x - x0) / 10))
        lo, hi = (yy, yy) if prev is None else (min(prev, yy), max(prev, yy))
        for y in range(lo, hi + 1):
            grid[y][x] = c1
        for y in (lo - 1, hi + 1):
            if y0 <= y <= y1 and grid[y][x] in (bg, grat):
                grid[y][x] = glow
        prev = yy
    for y, col in ((2, c2), (3, c2), (6, hsv(hue + 55, .55, .9)), (7, hsv(hue + 55, .55, .9))):
        grid[y][19] = grid[y][20] = col
    for x in (3, 5, 7):
        grid[11][x] = (120, 125, 140)
    grid[11][9] = c3
    grid[10][19] = (126, 231, 135)
    return grid


def torus(hue, a=1.15, b=0.35):
    """Shaded donut, projected with a z-buffer (the donut.c method)."""
    c1, c2, c3, c4 = ramp(hue)
    deep = hsv(hue, .85, .28)
    r1, r2, k2 = 0.8, 2.1, 5.0
    k1 = (H / 2 - 0.5) * k2 / (r1 + r2) * 0.95
    cx, cy = W / 2 - 0.5, H / 2 - 0.5
    ca, sa, cb, sb = math.cos(a), math.sin(a), math.cos(b), math.sin(b)
    zbuf = [[0.0] * W for _ in range(H)]
    grid = blank()
    for i in range(64):
        th = 2 * math.pi * i / 64
        ct, st = math.cos(th), math.sin(th)
        for j in range(160):
            ph = 2 * math.pi * j / 160
            cp, sp = math.cos(ph), math.sin(ph)
            ox, oy = r2 + r1 * ct, r1 * st
            x = ox * (cb * cp + sa * sb * sp) - oy * ca * sb
            y = ox * (sb * cp - sa * cb * sp) + oy * ca * cb
            ooz = 1 / (k2 + ca * ox * sp + oy * sa)
            px, py = int(cx + k1 * ooz * x / 0.92 + 0.5), int(cy - k1 * ooz * y + 0.5)
            if 0 <= px < W and 0 <= py < H and ooz > zbuf[py][px]:
                zbuf[py][px] = ooz
                lum = (cp * ct * sb - ca * ct * sp - sa * st
                       + cb * (ca * st - ct * sa * sp))
                grid[py][px] = (c1 if lum > 0.95 else c2 if lum > 0.5 else
                                c3 if lum > 0.05 else c4 if lum > -0.5 else deep)
    return stars(grid)


# Hand-drawn logos: rows are left halves mirrored about the last column, so
# each string is (W + 1) // 2 wide. Overlays are (row, col, key) after mirroring.
def _pixmap(rows, palette, overlays=()):
    grid = blank()
    for y, half in enumerate(rows):
        for x, ch in enumerate(half + half[-2::-1]):
            grid[y][x] = palette.get(ch)
    for y, x, ch in overlays:
        grid[y][x] = palette[ch]
    return grid


def mushroom(hue):
    c1, c2, c3, c4 = ramp(hue)
    palette = {"1": c1, "2": c2, "3": c3, "4": c4,
               "w": (240, 236, 228), "s": (226, 214, 194), "S": (176, 164, 148),
               "g": hsv(hue + 55, .60, .55), "G": hsv(hue + 55, .50, .80)}
    rows = ["............",
            "........4332",
            ".....4432211",
            "...443221111",
            "..4432111111",
            ".44321111111",
            ".43322111111",
            ".44444333333",
            "........Ssss",
            "........Ssss",
            "........Ssss",
            ".......SSsss",
            "..G..g.gggGG",
            "gggggggggggg"]
    spots = [(2, 8, "w"), (2, 9, "w"), (3, 5, "w"), (3, 6, "w"), (4, 5, "w"),
             (3, 14, "w"), (3, 15, "w"), (4, 15, "w"), (4, 11, "w"), (5, 10, "w"),
             (5, 11, "w"), (5, 18, "w"), (6, 18, "w")]
    return _pixmap(rows, palette, spots)


LOGOS = {
    "planet":    (planet,    "ringed planet"),
    "synthwave": (synthwave, "striped sun over a grid floor"),
    "blackhole": (blackhole, "event horizon and accretion disk"),
    "scope":     (scope,     "oscilloscope with a sine trace"),
    "torus":     (torus,     "shaded donut"),
    "mushroom":  (mushroom,  "spotted mushroom"),
}
DEFAULT = "planet"


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


def lines(name, hue):
    return render(LOGOS[name][0](hue))


# ── CLI ───────────────────────────────────────────────────────────────────

def _acc(hue):
    r, g, b = hsv(hue, .62, .98)
    return f"{E}38;2;{r};{g};{b}m"


def _unknown(names):
    bad = [n for n in names if n not in LOGOS]
    if bad:
        print(f" unknown logo: {', '.join(bad)}  (have: {', '.join(LOGOS)})")
    return bad


def cmd_list(cfg):
    acc, cur, members = _acc(cfg["accent"]), cfg.get("logo", DEFAULT), pool(cfg)
    restricted = bool([n for n in cfg.get("logo_pool", []) if n in LOGOS])
    print()
    print(f"  {acc}logos{RESET}  (current: {acc}{cur}{RESET}"
          f"{DIM} · random pool: {len(members)} of {len(LOGOS)}{RESET})")
    for name, (_, desc) in LOGOS.items():
        mark = f"{acc}●{RESET}" if name == cur else " "
        tag = f"{acc}*{RESET}" if restricted and name in members else " "
        print(f"   {mark}{tag} {acc}{name:<10}{RESET} {DIM}{desc}{RESET}")
    print()
    print(f"  {DIM} bedazzle logo <name|random>          pick one, or roll each launch{RESET}")
    print(f"  {DIM} bedazzle logo pool [all|add|rm] …    limit what random rolls (* = in pool){RESET}")
    print(f"  {DIM} bedazzle logo gallery                preview them all{RESET}")
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


def cmd_gallery(cfg):
    hue, acc, members, cur = cfg["accent"], _acc(cfg["accent"]), pool(cfg), cfg.get("logo", DEFAULT)
    gap = 3
    per_row = max(1, (shutil.get_terminal_size((80, 24)).columns - 2) // (W + gap))
    names = list(LOGOS)
    print()
    for i in range(0, len(names), per_row):
        batch = names[i:i + per_row]
        art = [lines(n, hue) for n in batch]
        for row in range(len(art[0])):
            print("  " + (" " * gap).join(a[row] for a in art))
        labels = []
        for n in batch:
            mark = "● " if n == cur else ""
            color = acc if n in members else DIM
            labels.append(f"{color}{(mark + n).center(W)}{RESET}")
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
    if cmd == "gallery":
        return cmd_gallery(cfg)
    if cmd == "show" and args:
        if _unknown(args[:1]):
            return 1
        print()
        for ln in lines(args[0], cfg["accent"]):
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
