#!/usr/bin/env python3
"""
termbg — regenerating pixel-art background for Windows Terminal.

Adapted from the terminal-bg spec (WSL/zsh/kitty) to this machine's
reality: PowerShell + Windows Terminal. The display mechanism is WT's
`backgroundImage` setting, which hot-reloads when settings.json changes.
Alternating PNG filenames (termbg-a/termbg-b) force that reload — writing
the same path never would.

Flow:
  - the Shellwash prompt appends one line per command to termbg.events
    ("ok|<count>|<cwd>") — costs ~1ms, never blocks
  - a background daemon (pythonw, started by `termbg on`) polls the events
    file, advances the active module's persistent state, renders a small
    pixel grid, nearest-neighbor upscales it (chunky pixels on purpose),
    applies the exit-code overlay, writes the PNG, updates settings.json
  - `termbg use <module>` switches visuals without touching the plumbing

Modules: metaballs (default — drifts a step per command), automaton
(Life, cells colored by age), tetris (plays itself in a docked board,
one gravity tick per command), attractor (de Jong, seeded per directory),
truchet (per-command shimmer), contour, moire, subdivision, phyllotaxis.
Overlay: exitcode (red vignette on failure, decays over next commands).

CLI:
  termbg.py once | off | list | status
  termbg.py use <module> | palette <name> | overlay <exitcode|none>
  termbg.py daemon --pidfile <path>
  (--settings <path> targets a specific settings.json, for testing)
"""

import colorsys
import glob
import hashlib
import json
import math
import os
import random
import struct
import subprocess
import sys
import time
import zlib

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(HERE, "termbg.config.json")
STATE_DIR = os.path.join(HERE, "termbg.state")
EVENTS = os.path.join(HERE, "termbg.events")

WT_CANDIDATES = [
    os.path.join(os.environ.get("LOCALAPPDATA", ""),
                 "Packages", "Microsoft.WindowsTerminal_8wekyb3d8bbwe",
                 "LocalState", "settings.json"),
    os.path.join(os.environ.get("LOCALAPPDATA", ""),
                 "Packages", "Microsoft.WindowsTerminalPreview_8wekyb3d8bbwe",
                 "LocalState", "settings.json"),
]

NO_WINDOW = 0x08000000 if os.name == "nt" else 0

# ── config / state ──────────────────────────────────────────────────────

DEFAULT_CONFIG = {
    "module": "metaballs",
    "overlay": "exitcode",
    "palette": "nord",
    "resolution": [1920, 1080],
    "throttle_ms": 900,
    "opacity": 0.4,      # art strength in the PNG (kitty background_tint must be 0)
    "backend": "auto",   # auto | kitty | wt | none
}


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG, "r", encoding="utf-8") as f:
            cfg.update(json.load(f))
    except (OSError, json.JSONDecodeError):
        pass
    return cfg


def save_config(cfg):
    # atomic: the daemon reads this file at any moment
    tmp = CONFIG + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    os.replace(tmp, CONFIG)


def daemon_running():
    return os.path.exists(os.path.join(HERE, "termbg.pid"))


def nudge_daemon():
    """Ask the running daemon to re-render instead of racing it."""
    with open(EVENTS, "a", encoding="utf-8") as f:
        f.write(f"ok|0|{os.getcwd()}\n")


def state_path(name):
    os.makedirs(STATE_DIR, exist_ok=True)
    return os.path.join(STATE_DIR, name + ".json")


def load_state(name):
    try:
        with open(state_path(name), "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(name, st):
    with open(state_path(name), "w", encoding="utf-8") as f:
        json.dump(st, f)


def seed_for(cwd, extra=""):
    return int(hashlib.sha256((cwd.lower() + "|" + extra).encode()).hexdigest(), 16) % (2 ** 32)


# ── palettes ────────────────────────────────────────────────────────────

def _hx(h):
    h = h.lstrip("#")
    return np.array([int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)], dtype=np.float32)


PALETTES = {
    "nord": {
        "bg": "#20242e",
        "ramp": ["#2e3440", "#4c566a", "#5e81ac", "#81a1c1", "#88c0d0", "#eceff4"],
        "accent": "#bf616a",
    },
    "gruvbox": {
        "bg": "#211f1d",
        "ramp": ["#282828", "#504945", "#b57614", "#d79921", "#fabd2f", "#fbf1c7"],
        "accent": "#fb4934",
    },
    "dracula": {
        "bg": "#1e1f29",
        "ramp": ["#282a36", "#44475a", "#6272a4", "#bd93f9", "#ff79c6", "#f8f8f2"],
        "accent": "#ff5555",
    },
    "sunset": {
        "bg": "#1a1423",
        "ramp": ["#241b2f", "#3d2645", "#832161", "#da4167", "#f0a05a", "#ffe9ce"],
        "accent": "#f0544f",
    },
    "neon": {
        "bg": "#0a0a14",
        "ramp": ["#12122b", "#3b1f8f", "#8324e0", "#e02ee0", "#2ee0e0", "#f2f2ff"],
        "accent": "#ff2975",
    },
    "ember": {
        "bg": "#140d0a",
        "ramp": ["#1f130d", "#57250f", "#a63c0a", "#e8600a", "#ffb02e", "#fff3c4"],
        "accent": "#ff4040",
    },
    "catppuccin": {
        "bg": "#1e1e2e",
        "ramp": ["#302d41", "#575268", "#7287fd", "#89b4fa", "#94e2d5", "#f5e0dc"],
        "accent": "#f38ba8",
    },
    "tokyonight": {
        "bg": "#1a1b26",
        "ramp": ["#24283b", "#414868", "#565f89", "#7aa2f7", "#7dcfff", "#c0caf5"],
        "accent": "#f7768e",
    },
    "rosepine": {
        "bg": "#191724",
        "ramp": ["#1f1d2e", "#26233a", "#31748f", "#9ccfd8", "#ebbcba", "#e0def4"],
        "accent": "#eb6f92",
    },
    "everforest": {
        "bg": "#2b3339",
        "ramp": ["#323c41", "#4a555b", "#7a8478", "#a7c080", "#dbbc7f", "#d3c6aa"],
        "accent": "#e67e80",
    },
    "solarized": {
        "bg": "#002b36",
        "ramp": ["#073642", "#586e75", "#268bd2", "#2aa198", "#b58900", "#fdf6e3"],
        "accent": "#dc322f",
    },
}

PALETTE_DESCS = {
    "accent": "follows your bedazzle accent hue — most colorful",
    "nord": "cool arctic blues, muted and calm",
    "gruvbox": "warm retro browns and golds",
    "dracula": "purple and pink on near-black",
    "sunset": "plum through crimson to peach",
    "neon": "electric purple/magenta/cyan — maximum pop",
    "ember": "fire: rust, orange, gold",
    "catppuccin": "soft pastel mocha — easy on the eyes",
    "tokyonight": "deep indigo night with neon blues",
    "rosepine": "muted rose, pine and foam",
    "everforest": "warm forest greens and tans",
    "solarized": "the classic balanced blue-green base",
}


def _accent_palette():
    """Ramp built from the bedazzle accent hue in bedazzle.config.json."""
    hue = 215.0
    try:
        with open(os.path.join(HERE, "bedazzle.config.json"), encoding="utf-8-sig") as f:
            hue = float(json.load(f).get("accent", 215.0))
    except Exception:
        pass
    h = (hue % 360) / 360.0

    def stop(i, v, s):
        r, g, b = colorsys.hsv_to_rgb((h + 0.05 * i / 5) % 1.0, s, v)
        return "#%02x%02x%02x" % (int(r * 255), int(g * 255), int(b * 255))

    ramp = [stop(0, 0.13, 0.55), stop(1, 0.32, 0.80), stop(2, 0.55, 0.95),
            stop(3, 0.78, 0.95), stop(4, 0.92, 0.65), stop(5, 1.00, 0.25)]
    return {"bg": stop(0, 0.08, 0.50), "ramp": ramp, "accent": "#ff5555"}


class Pal:
    def __init__(self, name):
        if name == "accent":
            p = _accent_palette()
        else:
            p = PALETTES.get(name, PALETTES["nord"])
        self.bg = _hx(p["bg"])
        self.ramp = [_hx(c) for c in p["ramp"]]
        self.accent = _hx(p["accent"])

    def __call__(self, t):
        """t in [0,1] (scalar or array) -> rgb float array via ramp interp."""
        t = np.clip(np.asarray(t, dtype=np.float32), 0.0, 1.0)
        n = len(self.ramp) - 1
        idx = np.minimum((t * n).astype(np.int32), n - 1)
        frac = (t * n - idx)[..., None]
        lo = np.stack(self.ramp)[idx]
        hi = np.stack(self.ramp)[np.minimum(idx + 1, n)]
        return lo * (1 - frac) + hi * frac


# ── shared rendering ────────────────────────────────────────────────────

def write_png(path, rgb):
    h, w = rgb.shape[:2]
    raw = b"".join(b"\x00" + rgb[y].tobytes() for y in range(h))

    def chunk(tag, data):
        block = tag + data
        return (struct.pack(">I", len(data)) + block
                + struct.pack(">I", zlib.crc32(block) & 0xFFFFFFFF))

    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n"
                + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(raw, 3))  # fast: smaller decode gap
                + chunk(b"IEND", b""))


def compose(grid, res, bg, blend=None):
    """Nearest-neighbor upscale to resolution — chunky pixels on purpose.
    Uses COVER scaling (fill the whole canvas, crop the overflow) so there
    are never letterbox margins. If `blend` is given (0..1), fade toward bg
    by that factor — bakes 'opacity' into the PNG for image-swap backends
    (kitty) that can't dim a background image themselves."""
    W, H = res
    gh, gw = grid.shape[:2]
    f = max(1, -(-W // gw), -(-H // gh))    # ceil-div on both axes = cover
    img = grid.repeat(f, 0).repeat(f, 1)
    ih, iw = img.shape[:2]
    y0 = max(0, (ih - H) // 2)
    x0 = max(0, (iw - W) // 2)
    canvas = img[y0:y0 + H, x0:x0 + W]
    if canvas.shape[:2] != (H, W):          # safety pad (shouldn't trigger)
        pad = np.empty((H, W, 3), np.uint8)
        pad[:] = bg.astype(np.uint8)
        pad[:canvas.shape[0], :canvas.shape[1]] = canvas
        canvas = pad
    if blend is not None:
        canvas = u8(bg.astype(np.float32) * (1 - blend) + canvas.astype(np.float32) * blend)
    return canvas


def u8(a):
    return np.clip(a, 0, 255).astype(np.uint8)


# ── modules ─────────────────────────────────────────────────────────────
# Each: render(ctx) -> (gh, gw, 3) uint8. ctx has: pal, ok, count, cwd,
# seed, chpwd (bool), rng, state (persisted dict, saved after render).

def mod_metaballs(ctx):
    st = ctx.state
    if "seeds" not in st or ctx.chpwd:
        rng = random.Random(ctx.seed)
        st["seeds"] = [[rng.uniform(0.35, 1.0), rng.uniform(0.35, 1.0),
                        rng.uniform(0, math.tau), rng.uniform(0, math.tau),
                        rng.uniform(0.14, 0.30)] for _ in range(6)]
        st["t"] = rng.uniform(0, 50)
    st["t"] = st.get("t", 0.0) + 0.35          # one step of drift per command
    if not ctx.ok:
        st["t"] += 0.9                          # failures make them flinch
    t = st["t"]
    gw, gh = 160, 90
    y, x = np.mgrid[-1.0:1.0:complex(0, gh), -16 / 9:16 / 9:complex(0, gw)]
    field = np.zeros_like(x)
    for fx, fy, px, py, r in st["seeds"]:
        bx = math.sin(t * fx + px) * 1.4
        by = math.cos(t * fy + py) * 0.75
        field += r * r / ((x - bx) ** 2 + (y - by) ** 2 + 1e-4)
    v = np.clip(field * 0.55, 0, 2.2)
    inside = v > 1.0
    rim = np.clip(1.0 - np.abs(v - 1.0) * 5.0, 0, 1)
    tval = np.clip(v * 0.36, 0, 0.55) + inside * 0.25 + rim * 0.35
    img = ctx.pal(tval)
    return u8(img)


def mod_automaton(ctx):
    st = ctx.state
    gw, gh = 160, 90
    grid = None
    if "grid" in st:
        try:
            grid = np.array(st["grid"], dtype=np.int32)
            if grid.shape != (gh, gw):
                grid = None
        except Exception:
            grid = None
    if grid is None or grid.sum() == 0 or (grid > 0).mean() < 0.015:
        rng = np.random.default_rng(ctx.seed ^ ctx.count)
        grid = (rng.random((gh, gw)) > 0.72).astype(np.int32)
    alive = (grid > 0).astype(np.int32)
    n = sum(np.roll(np.roll(alive, dy, 0), dx, 1)
            for dy in (-1, 0, 1) for dx in (-1, 0, 1) if (dy, dx) != (0, 0))
    born = (alive == 0) & (n == 3)
    survive = (alive == 1) & ((n == 2) | (n == 3))
    grid = np.where(born, 1, np.where(survive, grid + 1, 0))
    st["grid"] = grid.tolist()
    age = np.clip(grid / 22.0, 0, 1)
    img = np.where((grid > 0)[..., None], ctx.pal(0.25 + age * 0.75),
                   ctx.pal(np.zeros((gh, gw))) * 0.9)
    return u8(img)


TETROMINOES = {
    "I": [(0, 0), (0, 1), (0, 2), (0, 3)], "O": [(0, 0), (0, 1), (1, 0), (1, 1)],
    "T": [(0, 0), (0, 1), (0, 2), (1, 1)], "S": [(1, 0), (1, 1), (0, 1), (0, 2)],
    "Z": [(0, 0), (0, 1), (1, 1), (1, 2)], "J": [(0, 0), (1, 0), (1, 1), (1, 2)],
    "L": [(0, 2), (1, 0), (1, 1), (1, 2)],
}
PIECE_IDS = list(TETROMINOES.keys())


def _rot(cells, times):
    for _ in range(times % 4):
        cells = [(c, -r) for r, c in cells]
        minr = min(r for r, _ in cells)
        minc = min(c for _, c in cells)
        cells = [(r - minr, c - minc) for r, c in cells]
    return cells


TET_COLORS = {  # the classic seven
    "I": (80, 215, 230), "O": (240, 208, 70), "T": (168, 105, 220),
    "S": (105, 200, 105), "Z": (225, 95, 90), "J": (95, 130, 225), "L": (235, 150, 65),
}


def mod_tetris(ctx):
    st = ctx.state
    BW, BH = 10, 20
    board = st.get("board")
    if not board or len(board) != BH:
        board = [[0] * BW for _ in range(BH)]
        st["bag"] = []
        st["cur"] = None
    rng = random.Random(st.get("rngstate", ctx.seed))
    spawned = False
    if not st.get("cur"):
        if not st.get("bag"):
            bag = PIECE_IDS[:]
            rng.shuffle(bag)
            st["bag"] = bag
        kind = st["bag"].pop()
        rot = rng.randrange(4)
        w = max(c for _, c in _rot(TETROMINOES[kind], rot)) + 1
        st["cur"] = {"k": kind, "r": rot,
                     "x": rng.randrange(0, BW - w + 1),  # anywhere it fits, full width
                     "y": 0}
        spawned = True
    cur = st["cur"]
    cells = _rot(TETROMINOES[cur["k"]], cur["r"])

    def fits(ox, oy):
        for r, c in cells:
            yy, xx = oy + r, ox + c
            if xx < 0 or xx >= BW or yy >= BH:
                return False
            if yy >= 0 and board[yy][xx]:
                return False
        return True

    if spawned and not fits(cur["x"], cur["y"]):
        board = [[0] * BW for _ in range(BH)]      # spawn blocked: game over
    if fits(cur["x"], cur["y"] + 1):
        cur["y"] += 1                             # one gravity tick per command
    else:
        pid = PIECE_IDS.index(cur["k"]) + 1
        for r, c in cells:
            if 0 <= cur["y"] + r < BH:
                board[cur["y"] + r][cur["x"] + c] = pid
        board = [row for row in board if not all(row)]
        while len(board) < BH:
            board.insert(0, [0] * BW)
        if any(board[0]) or any(board[1]):
            board = [[0] * BW for _ in range(BH)]  # topped out — new game
        st["cur"] = None
    st["board"] = board
    st["rngstate"] = rng.randrange(2 ** 30)

    # render: gradient backdrop, board docked right
    gw, gh = 160, 90
    grad = np.linspace(0.04, 0.16, gh, dtype=np.float32)[:, None].repeat(gw, 1)
    img = ctx.pal(grad)
    cell = 4
    bx0, by0 = gw - BW * cell - 6, (gh - BH * cell) // 2
    img[by0 - 1:by0 + BH * cell + 1, bx0 - 1:bx0 + BW * cell + 1] = ctx.pal(0.18)
    draw = [row[:] for row in board]
    if st.get("cur"):
        c2 = _rot(TETROMINOES[st["cur"]["k"]], st["cur"]["r"])
        for r, c in c2:
            yy, xx = st["cur"]["y"] + r, st["cur"]["x"] + c
            if 0 <= yy < BH and 0 <= xx < BW:
                draw[yy][xx] = PIECE_IDS.index(st["cur"]["k"]) + 1
    for yy in range(BH):
        for xx in range(BW):
            if draw[yy][xx]:
                col = np.array(TET_COLORS[PIECE_IDS[draw[yy][xx] - 1]], np.float32)
                img[by0 + yy * cell:by0 + (yy + 1) * cell - 1,
                    bx0 + xx * cell:bx0 + (xx + 1) * cell - 1] = col
    return u8(img)


def mod_attractor(ctx):
    # key the cache on palette too — the rendered image bakes colors in, so
    # a palette switch must invalidate it (otherwise you get the stale image)
    pal = getattr(ctx, "palname", "nord")
    cache = os.path.join(STATE_DIR, f"attractor-{ctx.seed}-{pal}.npy")
    if os.path.exists(cache) and not ctx.chpwd:
        try:
            return np.load(cache)
        except Exception:
            pass
    rng = random.Random(ctx.seed)
    a, b, c, d = [rng.uniform(-2.5, 2.5) for _ in range(4)]
    n = 4000
    x = np.random.default_rng(ctx.seed).uniform(-1, 1, n)
    y = np.random.default_rng(ctx.seed + 1).uniform(-1, 1, n)
    hist = np.zeros((270, 480), dtype=np.float64)
    for i in range(140):
        x, y = np.sin(a * y) - np.cos(b * x), np.sin(c * x) - np.cos(d * y)
        if i > 15:
            h, _, _ = np.histogram2d(y, x, bins=(270, 480),
                                     range=[[-2.1, 2.1], [-2.1 * 16 / 9, 2.1 * 16 / 9]])
            hist += h
    v = np.log1p(hist)
    v /= max(v.max(), 1e-6)
    img = u8(ctx.pal(v * 0.95))
    os.makedirs(STATE_DIR, exist_ok=True)
    np.save(cache, img)
    return img


def _truchet_tiles(ts):
    yy, xx = np.mgrid[0:ts, 0:ts].astype(np.float32) + 0.5
    r = ts / 2.0
    wdt = ts / 5.0
    a = (np.abs(np.hypot(xx, yy) - r) < wdt) | (np.abs(np.hypot(ts - xx, ts - yy) - r) < wdt)
    b = (np.abs(np.hypot(ts - xx, yy) - r) < wdt) | (np.abs(np.hypot(xx, ts - yy) - r) < wdt)
    return a, b


def mod_truchet(ctx):
    st = ctx.state
    ts, tw, th = 8, 20, 12
    ori = st.get("ori")
    if not ori or ctx.chpwd or len(ori) != th:
        rng = random.Random(ctx.seed)
        ori = [[rng.randrange(2) for _ in range(tw)] for _ in range(th)]
    rng = random.Random((ctx.seed << 8) ^ ctx.count)
    for _ in range(max(1, int(tw * th * 0.04))):   # per-command shimmer
        ori[rng.randrange(th)][rng.randrange(tw)] ^= 1
    st["ori"] = ori
    ta, tb = _truchet_tiles(ts)
    gh, gw = th * ts, tw * ts
    img = np.empty((gh, gw, 3), np.float32)
    base = ctx.pal(0.04)
    arc = ctx.pal(0.62)
    for ty in range(th):
        for tx in range(tw):
            m = ta if ori[ty][tx] == 0 else tb
            tile = np.where(m[..., None], arc, base * (0.92 + 0.08 * ((tx + ty) % 2)))
            img[ty * ts:(ty + 1) * ts, tx * ts:(tx + 1) * ts] = tile
    return u8(img)


def _value_noise(seed, gw, gh, octaves=(6, 12, 24)):
    total = np.zeros((gh, gw), np.float32)
    amp = 1.0
    for i, cells in enumerate(octaves):
        rng = np.random.default_rng(seed + i * 977)
        coarse = rng.random((cells + 1, int(cells * 16 / 9) + 1)).astype(np.float32)
        ys = np.linspace(0, cells - 1e-4, gh)
        xs = np.linspace(0, int(cells * 16 / 9) - 1e-4, gw)
        y0 = ys.astype(int)[:, None]
        x0 = xs.astype(int)[None, :]
        fy = (ys[:, None] - y0)
        fx = (xs[None, :] - x0)
        fy = fy * fy * (3 - 2 * fy)
        fx = fx * fx * (3 - 2 * fx)
        v = (coarse[y0, x0] * (1 - fx) * (1 - fy) + coarse[y0, x0 + 1] * fx * (1 - fy)
             + coarse[y0 + 1, x0] * (1 - fx) * fy + coarse[y0 + 1, x0 + 1] * fx * fy)
        total += v * amp
        amp *= 0.5
    total -= total.min()
    total /= max(total.max(), 1e-6)
    return total


def mod_contour(ctx):
    gw, gh = 320, 180
    v = _value_noise(ctx.seed, gw, gh)
    bands = 9
    band = (v * bands).astype(np.int32)
    edge = np.zeros((gh, gw), bool)
    edge[1:, :] |= band[1:, :] != band[:-1, :]
    edge[:, 1:] |= band[:, 1:] != band[:, :-1]
    img = ctx.pal(0.03 + band / bands * 0.10)
    line = ctx.pal(0.30 + band / bands * 0.55)
    img = np.where(edge[..., None], line, img)
    return u8(img)


def mod_moire(ctx):
    st = ctx.state
    st["p"] = st.get("p", 0.0) + 0.4               # phase drifts per command
    rng = random.Random(ctx.seed)
    gw, gh = 320, 180
    y, x = np.mgrid[-1.0:1.0:complex(0, gh), -16 / 9:16 / 9:complex(0, gw)]
    c1 = (rng.uniform(-0.8, 0.8), rng.uniform(-0.5, 0.5))
    c2 = (rng.uniform(-0.8, 0.8), rng.uniform(-0.5, 0.5))
    d1 = np.hypot(x - c1[0], y - c1[1])
    d2 = np.hypot(x - c2[0], y - c2[1])
    w1 = np.sin(d1 * 28 + st["p"])
    w2 = np.sin(d2 * 31 - st["p"] * 0.7)
    v = (w1 * w2 * 0.5 + 0.5)
    img = ctx.pal(0.04 + np.round(v * 4) / 4 * 0.6)
    return u8(img)


def mod_subdivision(ctx):
    rng = random.Random(ctx.seed)
    gw, gh = 160, 90
    img = np.empty((gh, gw, 3), np.float32)
    rects = [(0, 0, gw, gh)]
    leaves = []
    while rects:
        x, y, w, h = rects.pop()
        if (w < 18 and h < 14) or (w < 8 or h < 6) or rng.random() < 0.12:
            leaves.append((x, y, w, h))
            continue
        if (w > h or (w == h and rng.random() < 0.5)) and w >= 8:
            s = int(w * rng.uniform(0.3, 0.7))
            rects += [(x, y, s, h), (x + s, y, w - s, h)]
        else:
            s = int(h * rng.uniform(0.3, 0.7))
            rects += [(x, y, w, s), (x, y + s, w, h - s)]
    border = ctx.pal(0.0) * 0.7
    for x, y, w, h in leaves:
        img[y:y + h, x:x + w] = ctx.pal(rng.choice([0.05, 0.12, 0.3, 0.5, 0.75, 0.92]))
        img[y:y + h, x] = border
        img[y, x:x + w] = border
    return u8(img)


def mod_phyllotaxis(ctx):
    st = ctx.state
    st["rot"] = st.get("rot", 0.0) + 0.035          # spiral turns per command
    gw, gh = 320, 180
    img = ctx.pal(np.zeros((gh, gw), np.float32) + 0.03)
    yy, xx = np.mgrid[0:gh, 0:gw].astype(np.float32)
    cx, cy = gw / 2, gh / 2
    npts = 420
    golden = math.radians(137.50776)
    for i in range(npts):
        ang = i * golden + st["rot"]
        rad = 3.4 * math.sqrt(i)
        px, py = cx + math.cos(ang) * rad, cy + math.sin(ang) * rad * 0.62
        if not (-4 < px < gw + 4 and -4 < py < gh + 4):
            continue
        size = 1.0 + 2.6 * (i / npts)
        m = (xx - px) ** 2 + (yy - py) ** 2 < size * size
        img[m] = ctx.pal(0.25 + 0.7 * (i / npts))
    return u8(img)


def _git_info(cwd):
    """Branch (cheap file read), dirty count and commit count (subprocess,
    only ever called from the daemon, throttled by the caller)."""
    d = cwd
    root = None
    while d:
        if os.path.exists(os.path.join(d, ".git", "HEAD")):
            root = d
            break
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    if not root:
        return None
    branch = "?"
    try:
        with open(os.path.join(root, ".git", "HEAD"), encoding="utf-8") as f:
            line = f.readline().strip()
        branch = line.split("refs/heads/", 1)[1] if "refs/heads/" in line else line[:7]
    except OSError:
        pass
    dirty, commits = 0, 40
    try:
        out = subprocess.run(["git", "-C", root, "status", "--porcelain", "-uno"],
                             capture_output=True, text=True, timeout=4, creationflags=NO_WINDOW)
        dirty = len([ln for ln in out.stdout.splitlines() if ln.strip()])
    except Exception:
        pass
    try:  # total history size (cap high, not at 400 — big repos should read big)
        out = subprocess.run(["git", "-C", root, "rev-list", "--count", "--max-count=20000", "HEAD"],
                             capture_output=True, text=True, timeout=4, creationflags=NO_WINDOW)
        commits = int(out.stdout.strip() or 40)
    except Exception:
        pass
    recent, tags = 0, 0
    try:  # how ACTIVE the repo is right now -> lit windows
        out = subprocess.run(["git", "-C", root, "rev-list", "--count", "--since=14.days", "HEAD"],
                             capture_output=True, text=True, timeout=4, creationflags=NO_WINDOW)
        recent = int(out.stdout.strip() or 0)
    except Exception:
        pass
    try:  # releases -> stars in the sky
        out = subprocess.run(["git", "-C", root, "tag"],
                             capture_output=True, text=True, timeout=4, creationflags=NO_WINDOW)
        tags = len([t for t in out.stdout.splitlines() if t.strip()])
    except Exception:
        pass
    return {"branch": branch, "dirty": dirty, "commits": commits,
            "recent": recent, "tags": tags, "root": root}


def mod_skyline(ctx):
    st = ctx.state
    now = time.time()
    if ctx.chpwd or st.get("cwd") != ctx.cwd or now - st.get("checked", 0) > 15:
        info = _git_info(ctx.cwd) or {}
        st.update({"checked": now, "cwd": ctx.cwd,
                   "branch": info.get("branch"),
                   "dirty": int(info.get("dirty", 0)),
                   "commits": int(info.get("commits", 0)),
                   "recent": int(info.get("recent", 0)),
                   "tags": int(info.get("tags", 0)),
                   "root": info.get("root")})
    branch = st.get("branch")
    # seed by REPO + branch: everything is on "main", so branch alone would
    # give every repo the identical sky/moon
    ident = f"{(st.get('root') or ctx.cwd).lower()}|{branch or ''}"
    hue = (int(hashlib.sha256(ident.encode()).hexdigest(), 16) % 360) / 360.0
    dirty = st.get("dirty", 0)
    commits = st.get("commits", 0)
    recent = st.get("recent", 0)
    tags = st.get("tags", 0)
    # log scale: a village (few commits) vs a megacity (thousands) must read
    # very differently. mag: 1 commit -> 0, 100 -> 2, 5000 -> ~3.7, 20000 -> 4.3
    mag = math.log10(max(commits, 1))

    gw, gh = 320, 180

    def hsv(hh, s, v):
        r, g, b = colorsys.hsv_to_rgb(hh % 1.0, s, v)
        return np.array([r * 255, g * 255, b * 255], np.float32)

    # sky: repo hue, dark zenith to glowing horizon
    stops_y = [0.0, 0.55, 1.0]
    stops_c = [hsv(hue, 0.55, 0.20), hsv(hue, 0.60, 0.42), hsv(hue + 0.07, 0.50, 0.75)]
    ys = np.linspace(0, 1, gh)
    sky = np.stack([np.interp(ys, stops_y, [c[i] for c in stops_c]) for i in range(3)], axis=1)
    img = sky[:, None, :].repeat(gw, 1)
    # a sun or a moon — which one, where, and its tint are all per-repo
    brng = random.Random(ident)
    sx = brng.randrange(25, gw - 25)
    sy_ = int(gh * brng.uniform(0.12, 0.45))
    sr = brng.randrange(7, 13)
    if brng.random() < 0.5:
        disc_col = hsv(hue + brng.uniform(0.02, 0.10), 0.20, 0.98)      # pale moon
    else:
        disc_col = hsv(brng.uniform(0.06, 0.13), 0.55, 1.00)            # warm sun
    yy, xx = np.mgrid[0:gh, 0:gw]
    disc = (xx - sx) ** 2 + (yy - sy_) ** 2
    img[disc < (sr * 2.6) ** 2] = img[disc < (sr * 2.6) ** 2] * 0.6 + disc_col * 0.4
    img[disc < sr ** 2] = disc_col

    # stars: one per tag/release — a well-released repo has a starry sky
    star_col = hsv(hue, 0.10, 0.95)
    srng = random.Random(f"{ident}|stars")
    for _ in range(min(tags, 70)):
        stx, sty = srng.randrange(gw), srng.randrange(int(gh * 0.5))
        if disc[sty, stx] > (sr * 2.6) ** 2:
            img[sty, stx] = star_col

    # birds: one per uncommitted file, drifting across the sky per command
    bird_col = hsv(hue, 0.35, 0.05)
    for i in range(min(dirty, 24)):
        b = random.Random(f"{ident}|bird{i}")
        speed = b.choice([1, 2]) * b.choice([1, -1])
        bx = (b.randrange(gw) + ctx.count * speed) % gw
        by = int(gh * 0.10 + b.random() * gh * 0.38 + 2.5 * math.sin(ctx.count * 0.6 + i))
        wy = by - 1 if (ctx.count + i) % 2 == 0 else by  # wings flap per command
        for py, px in ((by, bx), (wy, bx - 1), (wy, bx + 1)):
            if 0 <= py < gh and 0 <= px < gw:
                img[py, px] = bird_col

    # buildings: commit count drives BOTH how many towers AND how tall they
    # get (log-scaled) — a huge repo becomes a skyscraper megacity, a tiny
    # one a low village. Lit windows show how ACTIVE the repo is right now.
    total = int(4 + mag * 8)                        # ~4 (new) .. ~38 (20k commits)
    height_scale = min(1.0, 0.32 + 0.16 * mag)      # short town .. towering
    # a real night city is mostly dark with a FEW lit windows — keep it sparse
    # even for very active repos so it never becomes a uniform grid of lights
    lit_frac = min(0.22, recent / 200.0)            # commits in last 14 days
    warm = hsv(0.11, 0.70, 0.95)                      # lit window
    layers = [(0.34, hsv(hue, 0.45, 0.30)),          # far, hazy
              (0.52, hsv(hue, 0.40, 0.16)),          # mid
              (0.72, hsv(hue, 0.30, 0.06))]          # near, near-black
    for li, (base_h, col) in enumerate(layers):
        n = max(3, int(total * (0.6 + 0.25 * li)))
        for _ in range(n):
            w = brng.randrange(10, 34 - 6 * li)
            x0 = brng.randrange(0, gw - w)
            h = int(brng.uniform(0.45, 1.0) * base_h * height_scale * gh)
            if h < 4:
                continue
            top = gh - h
            img[top:gh, x0:x0 + w] = col
            if li >= 1 and h > 16:                   # only LIT windows are drawn —
                wr = random.Random(f"{ident}|w{x0}-{w}-{li}")  # dark ones stay building
                for wyv in range(top + 5, gh - 5, 7):
                    for wxv in range(x0 + 3, x0 + w - 3, 6):
                        if wr.random() < lit_frac:
                            img[wyv:wyv + 2, wxv:wxv + 2] = warm
    return u8(img)


def _hsv_img(hh, s, v):
    r, g, b = colorsys.hsv_to_rgb(hh % 1.0, s, v)
    return np.array([r * 255, g * 255, b * 255], np.float32)


def mod_circadian(ctx):
    """A sky whose colors track the actual time of day; a sun/moon crosses."""
    lt = time.localtime()
    frac = (lt.tm_hour * 60 + lt.tm_min) / 1440.0        # 0..1 through the day
    gw, gh = 320, 180
    # sun altitude: peaks at noon, below horizon at night
    alt = math.sin((frac - 0.25) * math.tau)             # +1 noon, -1 midnight
    day = max(0.0, alt)
    # zenith + horizon colors interpolate dawn->noon->dusk->night
    if alt >= 0:                                          # daytime
        # noon = bright blue; dawn/dusk = warm & dim. Clearly different hours.
        zen = _hsv_img(0.60, 0.60 - 0.25 * day, 0.22 + 0.55 * day)
        hor = _hsv_img(0.09 + 0.46 * day, 0.60 - 0.25 * day, 0.55 + 0.35 * day)
    else:                                                 # night
        night = -alt
        zen = _hsv_img(0.66, 0.55, 0.05 + 0.06 * (1 - night))
        hor = _hsv_img(0.70, 0.45, 0.12 + 0.10 * (1 - night))
    ys = np.linspace(0, 1, gh)[:, None]
    img = (zen[None, None, :] * (1 - ys[..., None]) + hor[None, None, :] * ys[..., None])
    img = np.repeat(img, gw, 1)
    # the disc arcs west across the sky: left at sunrise, right at sunset — so
    # afternoon (sun on the right, descending) never looks like morning.
    yy, xx = np.mgrid[0:gh, 0:gw]
    if alt >= 0:
        prog = (frac - 0.25) / 0.5                        # 0 sunrise .. 1 sunset
    else:
        prog = ((frac - 0.75) % 1.0) / 0.5                # 0 sunset .. 1 sunrise (moon)
    prog = min(1.0, max(0.0, prog))
    sx = int(gw * (0.08 + 0.84 * prog))
    sy = int(gh * (0.82 - 0.58 * abs(alt)))               # high near noon/midnight
    if alt >= 0:
        disc = _hsv_img(0.12, 0.45, 1.0)                 # warm sun
    else:
        disc = _hsv_img(0.62, 0.10, 0.95)                # pale moon
    d2 = (xx - sx) ** 2 + (yy - sy) ** 2
    r = 11
    img[d2 < (r * 2.4) ** 2] = img[d2 < (r * 2.4) ** 2] * 0.6 + disc * 0.4
    img[d2 < r ** 2] = disc
    # a few stars at night
    if alt < -0.05:
        srng = np.random.default_rng(ctx.seed)
        for _ in range(int(60 * -alt)):
            py, px = srng.integers(0, gh // 2), srng.integers(0, gw)
            img[py, px] = np.array([230, 230, 255], np.float32)
    return u8(img)


def mod_pulse(ctx):
    """Metaballs whose energy tracks system load — busy box, angrier lamp."""
    st = ctx.state
    try:
        load = os.getloadavg()[0] / max(1, os.cpu_count() or 1)
    except (OSError, AttributeError):
        load = 0.3
    load = min(1.5, load)
    if "seeds" not in st or ctx.chpwd:
        rng = random.Random(ctx.seed)
        st["seeds"] = [[rng.uniform(0.35, 1.0), rng.uniform(0.35, 1.0),
                        rng.uniform(0, math.tau), rng.uniform(0, math.tau),
                        rng.uniform(0.14, 0.30)] for _ in range(6)]
        st["t"] = rng.uniform(0, 50)
    st["t"] = st.get("t", 0.0) + 0.25 + 0.9 * load        # load speeds the drift
    if not ctx.ok:
        st["t"] += 0.9
    t = st["t"]
    gw, gh = 160, 90
    y, x = np.mgrid[-1.0:1.0:complex(0, gh), -16 / 9:16 / 9:complex(0, gw)]
    field = np.zeros_like(x)
    for fx, fy, px, py, r in st["seeds"]:
        bx = math.sin(t * fx + px) * 1.4
        by = math.cos(t * fy + py) * 0.75
        field += r * r / ((x - bx) ** 2 + (y - by) ** 2 + 1e-4)
    v = np.clip(field * (0.5 + 0.4 * load), 0, 2.2)
    inside = v > 1.0
    rim = np.clip(1.0 - np.abs(v - 1.0) * 5.0, 0, 1)
    # higher load pushes color hotter up the ramp
    tval = np.clip(v * 0.36, 0, 0.55) + inside * (0.25 + 0.35 * load) + rim * 0.35
    return u8(ctx.pal(np.clip(tval, 0, 1)))


def mod_aurora(ctx):
    """Shimmering horizontal light curtains; drifts a step per command."""
    st = ctx.state
    st["t"] = st.get("t", 0.0) + 0.22
    t = st["t"]
    gw, gh = 320, 180
    base = _value_noise(ctx.seed, gw, gh, octaves=(4, 8))
    yy = np.linspace(0, 1, gh)[:, None].repeat(gw, 1)
    xx = np.linspace(0, math.tau * 3, gw)[None, :].repeat(gh, 0)
    curtain = np.sin(xx + t + base * 6.0) * 0.5 + 0.5
    band = np.exp(-((yy - (0.35 + 0.12 * np.sin(xx + t))) ** 2) / 0.06)
    band += 0.6 * np.exp(-((yy - (0.6 + 0.10 * np.cos(xx * 0.7 - t))) ** 2) / 0.04)
    v = np.clip(curtain * band, 0, 1)
    img = ctx.pal(0.15 + 0.8 * v)
    img *= (0.25 + 0.75 * v)[..., None]                   # dark sky between curtains
    return u8(img)


def _git_diff_stat(cwd):
    """(changed_line_count, fingerprint, repo_root). Diff is repo-wide (git
    reports the whole worktree from any subdir), and keying on the ROOT means
    cd-ing between dirs of the same repo doesn't reset the automaton."""
    try:
        out = subprocess.run(["git", "-C", cwd, "diff", "--numstat"],
                             capture_output=True, text=True, timeout=4,
                             creationflags=NO_WINDOW)
        total = 0
        for ln in out.stdout.splitlines():
            for p in ln.split("\t")[:2]:
                if p.isdigit():
                    total += int(p)
        fp = int(hashlib.sha256(out.stdout.encode()).hexdigest(), 16) % (2 ** 31)
    except Exception:
        return 0, 0, ""
    root = ""
    d = cwd
    while d:
        if os.path.exists(os.path.join(d, ".git")):
            root = d
            break
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return total, fp, root


# lively Conway patterns (NOT still-lifes/blocks — those just sit there)
_LIFE_PATTERNS = [
    [(0, 0), (0, 1), (0, 2)],                              # blinker (oscillator)
    [(0, 1), (1, 2), (2, 0), (2, 1), (2, 2)],              # glider (spaceship)
    [(0, 1), (0, 2), (1, 0), (1, 1), (2, 1)],              # r-pentomino (chaotic)
    [(0, 0), (0, 1), (0, 2), (1, 1), (2, 1)],              # T-tetromino
    [(0, 1), (0, 2), (0, 3), (1, 0), (1, 1), (1, 2)],      # toad (oscillator)
]


def mod_gitlife(ctx):
    """Conway's Life whose STARTING population is your git diff: a clean tree
    seeds just a couple of oscillators (calm), and the more lines you've
    changed, the more live patterns it starts with. Seeds are gliders /
    blinkers / r-pentominoes — never still blocks — so it stays in motion.
    Keyed to the repo root, so it only reseeds when the DIFF changes, not on
    every cd within the repo."""
    st = ctx.state
    gw, gh = 160, 90
    changed, fp, root = _git_diff_stat(ctx.cwd)
    ident = root or ctx.cwd
    n_patterns = 2 + min(int(changed), 150) // 4        # 2 (clean) .. ~39 (big diff)
    grid = None
    if "grid" in st and st.get("fp") == fp and st.get("ident") == ident:
        try:
            grid = np.array(st["grid"], dtype=np.int32)
            if grid.shape != (gh, gw):
                grid = None
        except Exception:
            grid = None
    if grid is None or grid.sum() == 0:
        rng = random.Random(fp ^ ctx.seed)
        grid = np.zeros((gh, gw), np.int32)
        for _ in range(n_patterns):
            pat = rng.choice(_LIFE_PATTERNS)
            oy, ox = rng.randrange(gh - 4), rng.randrange(gw - 4)
            for dy, dx in pat:
                grid[oy + dy, ox + dx] = 1
        st["fp"] = fp
        st["ident"] = ident
        st["changed"] = changed
        st["grid"] = grid.tolist()
        age = np.clip(grid / 22.0, 0, 1)                # show fresh seeds this frame
        return u8(np.where((grid > 0)[..., None], ctx.pal(0.30 + age * 0.70),
                           ctx.pal(np.zeros((gh, gw))) * 0.9))
    alive = (grid > 0).astype(np.int32)
    n = sum(np.roll(np.roll(alive, dy, 0), dx, 1)
            for dy in (-1, 0, 1) for dx in (-1, 0, 1) if (dy, dx) != (0, 0))
    born = (alive == 0) & (n == 3)
    survive = (alive == 1) & ((n == 2) | (n == 3))
    grid = np.where(born, 1, np.where(survive, grid + 1, 0))
    st["grid"] = grid.tolist()
    age = np.clip(grid / 22.0, 0, 1)
    img = np.where((grid > 0)[..., None], ctx.pal(0.30 + age * 0.70),
                   ctx.pal(np.zeros((gh, gw))) * 0.9)
    return u8(img)


def _sysload():
    try:
        return min(1.5, os.getloadavg()[0] / max(1, os.cpu_count() or 1))
    except (OSError, AttributeError):
        return 0.3


def mod_storm(ctx):
    """A cute pixel seascape driven by system load: calm sunny sea with
    bobbing little sailboats when idle; as load climbs it clouds over, the
    swell picks up, rain comes in, and lightning cracks when the box is
    slammed. (The chill alternative to the fire.)"""
    load = _sysload()
    s = min(1.0, load)
    gw, gh = 160, 90
    horizon = int(gh * 0.52)
    t = ctx.count

    def hsv(h, sa, v):
        r, g, b = colorsys.hsv_to_rgb(h % 1.0, sa, v)
        return np.array([r * 255, g * 255, b * 255], np.float32)

    img = np.empty((gh, gw, 3), np.float32)
    # sky: pale sunny blue -> dark slate as load rises
    top = hsv(0.58, 0.40 - 0.25 * s, 0.92 - 0.55 * s)
    hor = hsv(0.10 + 0.10 * s, 0.35 - 0.2 * s, 0.98 - 0.5 * s)   # warm horizon when calm
    ys = np.linspace(0, 1, horizon)[:, None]
    img[:horizon] = top[None, None, :] * (1 - ys[..., None]) + hor[None, None, :] * ys[..., None]

    # a sun (calm) that the clouds swallow as it storms
    if s < 0.7:
        yy, xx = np.mgrid[0:horizon, 0:gw]
        sx, sy, sr = int(gw * 0.72), int(horizon * 0.4), 7
        d = (xx - sx) ** 2 + (yy - sy) ** 2
        sun = hsv(0.12, 0.5, 1.0)
        img[:horizon][d < (sr * 2.2) ** 2] = img[:horizon][d < (sr * 2.2) ** 2] * 0.6 + sun * 0.4
        img[:horizon][d < sr ** 2] = sun

    # drifting clouds — more and darker with load
    crng = random.Random(ctx.seed)
    for i in range(2 + int(5 * s)):
        cx = (crng.randrange(gw) + t * (1 + i)) % gw
        cy = int(gh * 0.08 + crng.random() * horizon * 0.45)
        cw, ch = crng.randrange(16, 34), crng.randrange(4, 8)
        cc = hsv(0.6, 0.12, 0.92 - 0.55 * s)
        for dx in range(cw):
            for dy in range(ch):
                if ((dx - cw / 2) / (cw / 2)) ** 2 + ((dy - ch / 2) / (ch / 2)) ** 2 < 1:
                    px, py = (cx + dx) % gw, cy + dy
                    if 0 <= py < horizon:
                        img[py, px] = cc

    # sea: sinusoidal swell, choppier with load
    yy, xx = np.mgrid[horizon:gh, 0:gw].astype(np.float32)
    wave = np.sin(xx * 0.22 + t * 0.5 + yy * 0.35) * (0.4 + 0.6 * s)
    sea = hsv(0.55, 0.55 + 0.15 * s, 0.42 - 0.14 * s)
    img[horizon:] = sea[None, None, :] * (0.75 + 0.25 * wave)[..., None]
    # whitecaps when rough
    if s > 0.3:
        caps = wave > (0.95 - 0.3 * s)
        img[horizon:][caps] = hsv(0.55, 0.15, 0.9)

    # little sailboats bobbing on the swell
    def boat(cx, cy, sail):
        hull = hsv(0.07, 0.6, 0.45)
        for dx in range(-4, 5):
            if 0 <= cx + dx < gw and 0 <= cy < gh:
                img[cy, cx + dx] = hull
            if abs(dx) < 3 and cy + 1 < gh and 0 <= cx + dx < gw:
                img[cy + 1, cx + dx] = hull * 0.8
        for k in range(1, 6):                          # mast
            if 0 <= cy - k < gh and 0 <= cx < gw:
                img[cy - k, cx] = hsv(0.08, 0.4, 0.35)
        for k in range(1, 5):                          # triangular sail
            for dx in range(1, k + 1):
                if 0 <= cy - k < gh and 0 <= cx + dx < gw:
                    img[cy - k, cx + dx] = sail

    for i in range(3):
        srng = random.Random(f"{ctx.seed}|ship{i}")
        bx = (srng.randrange(15, gw - 15) + int(2 * math.sin(t * 0.25 + i))) % (gw - 10) + 5
        by = horizon + 3 + i * 7 + int((0.4 + 1.6 * s) * math.sin(bx * 0.22 + t * 0.5))
        boat(bx, by, hsv(0.0 + 0.33 * i, 0.55, 0.95))

    # rain + lightning when it's really storming
    if s > 0.35:
        rrng = random.Random(t)
        for _ in range(int(160 * s)):
            rx, ry = rrng.randrange(gw), rrng.randrange(gh)
            for k in range(3):
                px, py = rx - k, ry + k
                if 0 <= py < gh and 0 <= px < gw:
                    img[py, px] = hsv(0.6, 0.15, 0.9)
    if s > 0.8 and (t * 3) % 7 == 0:
        img[:horizon] = img[:horizon] * 0.4 + np.array([255, 255, 235], np.float32) * 0.6

    return u8(img)


def _playerctl(*args):
    try:
        r = subprocess.run(["playerctl", *args], capture_output=True, text=True,
                           timeout=2, creationflags=NO_WINDOW)
        return r.stdout.strip() if r.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def _song_colors(title, artist):
    """A 3-stop color ramp derived from the track+artist, so every song has
    its own palette. Returns (low, mid, hi) float rgb arrays."""
    h = (int(hashlib.sha256((title or "silence").encode()).hexdigest(), 16) % 360) / 360.0
    h2 = (int(hashlib.sha256((artist or "?").encode()).hexdigest(), 16) % 360) / 360.0

    def rgb(hh, s, v):
        r, g, b = colorsys.hsv_to_rgb(hh % 1.0, s, v)
        return np.array([r * 255, g * 255, b * 255], np.float32)

    return rgb(h, 0.55, 0.35), rgb(h, 0.80, 0.95), rgb((h + h2) / 2 + 0.08, 0.70, 1.0)


def _album_pixels(url):
    """Download + crush the album art to a chunky 16x16 block grid (cached by
    URL), then hard-edge upscale to 64x64 — Tiny-Tower-style pixelation, not
    just a resize. Needs Pillow."""
    if not url:
        return None
    os.makedirs(STATE_DIR, exist_ok=True)
    cache = os.path.join(STATE_DIR, "album64-" + hashlib.sha256(url.encode()).hexdigest()[:16] + ".npy")
    if os.path.exists(cache):
        try:
            return np.load(cache)
        except Exception:
            pass
    try:
        import io
        import urllib.request
        from PIL import Image
        if url.startswith("file://"):
            with open(urllib.request.url2pathname(url[7:]), "rb") as f:
                data = f.read()
        else:
            req = urllib.request.Request(url, headers={"User-Agent": "termbg"})
            data = urllib.request.urlopen(req, timeout=5).read()
        im = Image.open(io.BytesIO(data)).convert("RGB")
        im = im.resize((32, 32), Image.BOX)      # crush to chunky color blocks
        im = im.resize((64, 64), Image.NEAREST)  # hard-edge upscale, no smoothing
        arr = np.asarray(im, dtype=np.uint8)
        np.save(cache, arr)
        return arr
    except Exception:
        return None


def _album_pattern(img, ax, ay, cell, low, mid, hi, t):
    """No-art fallback: a procedural 16x16 block pattern with a little note
    glyph baked in, so silence still looks like an album cover."""
    for y in range(16):
        for x in range(16):
            v = math.sin(x * 0.7 + y * 0.5) + math.cos(x * 0.4 - y * 0.6 + t * 0.6)
            col = hi if v > 0.9 else (mid if v > -0.2 else mid * 0.55)
            cxr, cyr = abs(x - 8), abs(y - 8)
            if x in (8, 9) and 4 <= y <= 11:
                col = low
            if cyr <= 2 and 1 <= cxr <= 3 and x < 10 and y > 9:
                col = low
            px, py = ax + x * cell, ay + y * cell
            img[py:py + cell, px:px + cell] = col


def _disc(img, cx, cy, r, col):
    """Filled circle — the closest a blocky pixel-art scene gets to round."""
    gh, gw = img.shape[:2]
    x0, x1 = max(0, int(cx - r)), min(gw, int(cx + r) + 1)
    y0, y1 = max(0, int(cy - r)), min(gh, int(cy + r) + 1)
    if x1 <= x0 or y1 <= y0:
        return
    yy, xx = np.mgrid[y0:y1, x0:x1]
    mask = (xx - cx) ** 2 + (yy - cy) ** 2 <= r * r
    img[y0:y1, x0:x1][mask] = col


def _boombox(img, cx, floor_y, pal, hi, beat):
    e, D, S, k = (np.array(pal[c], np.float32) for c in "eDSk")
    w, h = 22, 14
    x, y = round(cx - w / 2), round(floor_y) - h
    img[y - 3:y - 1, x + 4:x + w - 4] = e                     # handle
    img[y - 1:y + h, x - 1:x + w + 1] = e                      # outline
    img[y:y + h, x:x + w] = D                                  # body
    img[y:y + 1, x:x + w] = S                                  # top edge highlight
    glow = hi * (0.45 + 0.55 * beat)
    for sx in (x + 6, x + w - 6):
        _disc(img, sx, y + 8, 4, e)
        _disc(img, sx, y + 8, 3, S)
        _disc(img, sx, y + 8, 1.8, glow)
    img[y + 3:y + 7, x + w // 2 - 2:x + w // 2 + 2] = k        # tape deck
    hi85 = hi * 0.85
    img[y + h - 3:y + h - 2, x + w // 2 - 3:x + w // 2 - 1] = hi85
    img[y + h - 3:y + h - 2, x + w // 2 + 1:x + w // 2 + 3] = hi85


def _plant(img, cx, floor_y, wob, pal):
    O, o, G, g = (np.array(pal[c], np.float32) for c in "OoGg")
    x, y = round(cx), round(floor_y)
    img[y - 6:y, x - 4:x + 5] = O                              # terracotta pot
    img[y - 7:y - 5, x - 5:x + 6] = o                          # rim
    img[y - 14 - wob:y - 5 - wob, x - 1:x + 1] = G             # stem
    img[y - 13 - wob:y - 10 - wob, x - 6:x - 1] = g            # left leaf
    img[y - 16 - wob:y - 13 - wob, x + 1:x + 6] = g            # right leaf
    img[y - 18 - wob:y - 15 - wob, x - 3:x + 1] = g            # top leaf
    img[y - 11 - wob:y - 10 - wob, x - 4:x - 2] = G
    img[y - 14 - wob:y - 13 - wob, x + 2:x + 4] = G


def _notes(img, boom_cx, floor_y, hi, t):
    gh, gw = img.shape[:2]
    for n in range(4):
        prog = (t * 20 + n * 11) % 32
        ny = round(floor_y - 16 - prog)
        nx = round(boom_cx - 2 + 4 * math.sin(prog * 0.35 + n))
        col = hi * (0.35 + 0.6 * (1 - prog / 32))
        if 0 <= ny < gh - 2 and 0 <= nx < gw - 2:
            img[ny:ny + 3, nx:nx + 3] = col
        if 0 <= ny - 3 < gh - 2 and 0 <= nx + 2 < gw - 1:
            img[ny - 3:ny, nx + 2:nx + 3] = col


def _sprite_wh(sprites, name, scale=1):
    rows = sprites.get(name, [])
    w = max((len(r) for r in rows), default=0)
    return w * scale, len(rows) * scale


def _blit_sprite(img, sprites, pal, name, x, y, scale=1):
    rows = sprites.get(name)
    if not rows:
        return
    gh, gw = img.shape[:2]
    for ry, row in enumerate(rows):
        y0, y1 = y + ry * scale, y + (ry + 1) * scale
        if y1 <= 0 or y0 >= gh:
            continue
        for rx, ch in enumerate(row):
            if ch in ". ":
                continue
            col = pal.get(ch)
            if col is None:
                continue
            x0, x1 = x + rx * scale, x + (rx + 1) * scale
            if x1 <= 0 or x0 >= gw:
                continue
            img[max(0, y0):min(gh, y1), max(0, x0):min(gw, x1)] = col


def _jitter(key, span=2):
    """Small deterministic per-item wobble — stable across renders, not
    re-randomized every frame, so the hangout looks hand-placed, not jittery."""
    h = int(hashlib.sha256(key.encode()).hexdigest(), 16)
    return h % (span * 2 + 1) - span


def mod_nowplaying(ctx):
    """Your music, pixel-art first. A crunched 16x16-block album cover sits
    top-right; underneath it a little hangout — a boombox, a few pixel-buddy
    friends, and a potted plant — settles into a shelf-less, smile-curved
    patch of ground (real sprite bitmaps, not faked-unicode glyphs). Needs
    playerctl (MPRIS); Pillow for the album art. Falls back to a
    song-colored block pattern without them."""
    gw, gh = 240, 135
    status = _playerctl("status")
    playing = status == "Playing"
    title = _playerctl("metadata", "xesam:title")
    artist = _playerctl("metadata", "xesam:artist")
    art_url = _playerctl("metadata", "mpris:artUrl")
    try:
        pos = float(_playerctl("position") or 0)
    except ValueError:
        pos = 0.0
    us = _playerctl("metadata", "mpris:length")
    try:
        length = float(us) / 1e6 if us else 0.0
    except ValueError:
        length = 0.0

    low, mid, hi = _song_colors(title, artist)
    t = ctx.count
    img = np.empty((gh, gw, 3), np.float32)
    img[:] = low * 0.28                                    # flat song-tinted backdrop
    # for i, (sx, sy) in enumerate([(26, 30), (60, 20), (40, 64), (88, 46),
    #                                (20, 92), (70, 104), (100, 80)]):
    #     tw = 0.35 + 0.65 * (0.5 + 0.5 * math.sin(t * 1.6 + i))
    #     img[sy, sx] = hi * tw

    # ── album art: crunched to blocks, top-right ──────────────────────────
    ax, ay, cell, size = 138, 14, 4, 64
    beat = (0.5 + 0.5 * math.sin(t * 2.4)) if playing else 0.35
    img[ay - 3:ay + size + 3, ax - 3:ax + size + 3] = hi * (0.5 + 0.45 * beat)  # frame glow
    art = _album_pixels(art_url)
    if art is not None:
        img[ay:ay + size, ax:ax + size] = art.astype(np.float32)
    else:
        _album_pattern(img, ax, ay, cell, low, mid, hi, t if playing else 0)

    # ── the hangout: boombox + buddies + plant, no shelf plank ───────────
    try:
        import pet
        sprites, pal = pet.PIXEL_SPRITES, pet.PIXEL_PALETTE
    except Exception:
        sprites, pal = {}, {}

    if sprites:
        main = "cat"
        try:
            with open(os.path.join(HERE, "bedazzle.config.json"), encoding="utf-8-sig") as f:
                main = json.load(f).get("sprite", "cat")
        except Exception:
            pass
        pool = [n for n in pet.BUDDY_ORDER if n != main]
        random.Random(f"{title}|{artist}").shuffle(pool)   # a new crew per song
        friends = pool[:4]
        row = [{"kind": "boombox", "w": 22},
               {"kind": "buddy", "name": friends[0], "scale": 1},
               {"kind": "buddy", "name": friends[1], "scale": 1},
               {"kind": "buddy", "name": main, "scale": 2},
               {"kind": "buddy", "name": friends[2], "scale": 1},
               {"kind": "buddy", "name": friends[3], "scale": 1},
               {"kind": "plant", "w": 14}]
        for it in row:
            if it["kind"] == "buddy":
                it["w"], it["h"] = _sprite_wh(sprites, it["name"], it["scale"])

        gap = 4
        total = sum(it["w"] for it in row) + gap * (len(row) - 1)
        cx_center = ax + size / 2
        cur = round(min(max(cx_center - total / 2, 8), gw - 8 - total))
        n = len(row) - 1
        floor_base = ay + size + 38                          # tucked under the album

        def bob(ph, amp):
            return round(amp * (0.5 + 0.5 * math.sin(t * 2.8 + ph))) if playing else 0

        boom_cx = cur
        for i, it in enumerate(row):
            cx = cur + it["w"] / 2
            pos = (i / n) * 2 - 1 if n else 0.0
            base = floor_base - 9 * pos * pos + _jitter(f"{it.get('name', it['kind'])}|{i}", span=4)
            if it["kind"] == "boombox":
                boom_cx = cx
                _boombox(img, cx, base, pal, hi, beat)
            elif it["kind"] == "plant":
                _plant(img, cx, base, bob(3.1, 1), pal)
            else:
                y = round(base) - it["h"] - bob(i * 0.9, 3 if it["scale"] == 2 else 2)
                _blit_sprite(img, sprites, pal, it["name"], round(cx - it["w"] / 2), y, it["scale"])
            cur += it["w"] + gap

        if playing:
            _notes(img, boom_cx, floor_base, hi, t)

    # slim progress bar along the very bottom, with a playhead nub
    if length > 0:
        frac = float(np.clip(pos / length, 0, 1))
        img[gh - 4:gh - 1, :] = low * 1.6
        img[gh - 4:gh - 1, :int(gw * frac)] = hi
        nub = int(gw * frac)
        img[gh - 5:gh, max(0, nub - 1):nub + 1] = hi
    return u8(img)


MODULES = {
    "metaballs": mod_metaballs,
    "automaton": mod_automaton,
    "tetris": mod_tetris,
    "skyline": mod_skyline,
    "attractor": mod_attractor,
    "truchet": mod_truchet,
    "contour": mod_contour,
    "moire": mod_moire,
    "subdivision": mod_subdivision,
    "phyllotaxis": mod_phyllotaxis,
    "circadian": mod_circadian,
    "pulse": mod_pulse,
    "storm": mod_storm,
    "aurora": mod_aurora,
    "gitlife": mod_gitlife,
    "nowplaying": mod_nowplaying,
}

MODULE_DESCS = {
    "metaballs": "lava blobs drift one step per command, flinch on failures",
    "automaton": "Conway's Life; cells age cool->hot, reseeds when it dies",
    "tetris": "plays itself in a docked board — one gravity tick per command",
    "skyline": "git city: repo+branch color the sky, commits raise towers, dirty files fly as birds",
    "attractor": "de Jong attractor; each directory gets its own artwork",
    "truchet": "quarter-circle tiles; a few reroll each command (shimmer)",
    "contour": "topographic noise map; unique per directory",
    "moire": "interference rings; phase drifts per command",
    "subdivision": "Mondrian rectangles; unique per directory",
    "phyllotaxis": "sunflower spiral; rotates slowly per command",
    "circadian": "sky tracks the real time of day; a sun/moon crosses it",
    "pulse": "metaballs that get hotter and faster as system load climbs",
    "storm": "cute pixel sea + sailboats; calm when idle, stormy under load",
    "aurora": "shimmering northern-lights curtains; drifts per command",
    "gitlife": "Conway's Life seeded by your git diff — reseeds as you edit",
    "nowplaying": "big pixel album art + your buddy listening in headphones",
}

PER_DIR_MODULES = {"attractor", "contour", "subdivision"}  # only rerender on cd


def overlay_exitcode(img, gstate, ok):
    heat = float(gstate.get("heat", 0.0))
    if not ok:
        heat = 1.0
    if heat > 0.02:
        h, w = img.shape[:2]
        y, x = np.mgrid[-1.0:1.0:complex(0, h), -1.0:1.0:complex(0, w)]
        vig = np.clip(np.maximum(np.abs(x), np.abs(y)) - 0.55, 0, 1) ** 1.5
        red = np.array([200, 40, 40], np.float32)
        img = u8(img.astype(np.float32) * (1 - (vig * heat * 0.55)[..., None])
                 + red * (vig * heat * 0.55)[..., None])
    gstate["heat"] = heat * 0.45
    return img


# ── display backends ──────────────────────────────────────────────────────
# Each backend puts the rendered PNG "behind the text". Windows Terminal
# blends opacity itself (via backgroundImageOpacity); image-swap backends
# like kitty can't, so for those we pre-blend opacity into the PNG in
# compose(). backend_blends() reports which kind a backend is.

def detect_backend():
    if os.environ.get("KITTY_WINDOW_ID") or os.environ.get("TERM", "").startswith("xterm-kitty"):
        return "kitty"
    if _kitty_socket_paths():
        return "kitty"
    if os.environ.get("WT_SESSION") or find_settings():
        return "wt"
    return "none"


def current_backend(cfg):
    b = cfg.get("backend", "auto")
    return detect_backend() if b in (None, "auto") else b


def backend_blends(name):
    return name == "wt"   # WT does its own opacity blend; others get a baked PNG


def _kitty_socket_paths():
    """All candidate kitty listen sockets — refreshed every call.

    The daemon inherits KITTY_LISTEN_ON from whichever tab started it; that
    window may close while others stay open. kitty 0.32+ also suffixes the
    pid (/tmp/kitty-1234) even when listen_on names a fixed path."""
    seen = set()
    paths = []

    def add(addr):
        addr = (addr or "").strip()
        if not addr or addr in seen:
            return
        seen.add(addr)
        paths.append(addr)

    add(os.environ.get("KITTY_LISTEN_ON", ""))
    for path in sorted(glob.glob("/tmp/kitty*")):
        try:
            if os.path.exists(path):
                add(f"unix:{path}")
        except OSError:
            pass
    return paths


def _kitty_run(to, *args):
    cmd = ["kitty", "@", "--to", to] + list(args)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=6)
        return r.returncode == 0, (r.stderr or r.stdout).strip()
    except FileNotFoundError:
        return False, "kitty not found on PATH"
    except (OSError, subprocess.SubprocessError) as exc:
        return False, str(exc)


def _kitty(*args):
    """Run `kitty @ …` on every live listen socket; succeed if any responds."""
    targets = _kitty_socket_paths()
    if targets:
        last_msg = ""
        for to in targets:
            ok, msg = _kitty_run(to, *args)
            if ok:
                return True, ""
            last_msg = msg or last_msg
        return False, last_msg or "kitty remote control unreachable"

    # Foreground kitty tab with no listen_on — `kitty @` works without --to.
    try:
        r = subprocess.run(["kitty", "@"] + list(args),
                           capture_output=True, text=True, timeout=6)
        return r.returncode == 0, (r.stderr or r.stdout).strip()
    except FileNotFoundError:
        return False, "kitty not found on PATH"
    except (OSError, subprocess.SubprocessError) as exc:
        return False, str(exc)


def kitty_set(png_path):
    ok, msg = _kitty("set-background-image", "--layout", "scaled", png_path)
    if not ok:
        low = msg.lower()
        if "remote control" in low or "not allowed" in low or "refused" in low or not msg:
            return ("kitty remote control unreachable — add 'allow_remote_control yes' "
                    "AND 'listen_on unix:/tmp/kitty' to kitty.conf, then fully restart kitty")
        return f"kitty: {msg}"
    return None


def kitty_clear():
    ok, msg = _kitty("set-background-image", "none")
    return None if ok else f"kitty: {msg}"


# ── WT settings plumbing ────────────────────────────────────────────────

def find_settings():
    if "--settings" in sys.argv:
        return sys.argv[sys.argv.index("--settings") + 1]
    for p in WT_CANDIDATES:
        if os.path.isfile(p):
            return p
    return None


def load_settings(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        text = f.read()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        stripped = "\n".join(ln for ln in text.splitlines()
                             if not ln.lstrip().startswith("//"))
        return json.loads(stripped)


def _write_settings(path, cfg):
    # atomic: WT's file watcher must never see a half-written settings.json
    tmp = path + ".termbg-tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=4)
    os.replace(tmp, path)


def wt_set_background(png_path, opacity, bg_hex, gstate):
    path = find_settings()
    if not path:
        return "settings.json not found"
    try:
        cfg = load_settings(path)
    except (OSError, json.JSONDecodeError) as exc:
        return f"could not parse settings.json ({exc})"
    profiles = cfg.get("profiles")
    if not isinstance(profiles, dict):
        return "unsupported settings layout"
    backup = path + ".bak-shellwash"
    legacy = path + ".bak-bedazzle"
    if not os.path.exists(backup) and os.path.exists(legacy):
        backup = legacy
    if not os.path.exists(backup):
        with open(path, "rb") as src, open(backup, "wb") as dst:
            dst.write(src.read())
    d = profiles.setdefault("defaults", {})
    # while the next image decodes, WT paints its background COLOR — match
    # it to the palette so the reload blink is same-colored, not black.
    # The user's true pre-termbg color lives in the backup, not in the live
    # settings (which may already hold a color WE set).
    if "orig_bg" not in gstate:
        orig = "__none__"
        try:
            bak = load_settings(backup)
            orig = bak.get("profiles", {}).get("defaults", {}).get("background", "__none__")
        except (OSError, json.JSONDecodeError):
            pass
        gstate["orig_bg"] = orig
    d["background"] = bg_hex
    d["backgroundImage"] = png_path
    d["backgroundImageOpacity"] = opacity
    d["backgroundImageStretchMode"] = "uniformToFill"
    _write_settings(path, cfg)
    return None


def wt_remove_background(gstate=None):
    path = find_settings()
    if not path:
        return "settings.json not found"
    try:
        cfg = load_settings(path)
    except (OSError, json.JSONDecodeError) as exc:
        return f"could not parse settings.json ({exc})"
    d = cfg.get("profiles", {}).get("defaults", {})
    for k in ("backgroundImage", "backgroundImageOpacity", "backgroundImageStretchMode"):
        d.pop(k, None)
    # restore whatever background color the user had before termbg
    orig = gstate.get("orig_bg") if gstate else None
    if orig and orig != "__none__":
        d["background"] = orig
    else:
        d.pop("background", None)
    if gstate is not None:
        gstate.pop("orig_bg", None)
    _write_settings(path, cfg)
    return None


# ── backend dispatch ──────────────────────────────────────────────────────

def apply_background(cfg, png_path, opacity, bg_hex, gstate):
    backend = current_backend(cfg)
    if backend == "kitty":
        return kitty_set(png_path)
    if backend == "wt":
        return wt_set_background(png_path, opacity, bg_hex, gstate)
    return "no supported terminal backend (set termbg backend, or use kitty/WT)"


def clear_background(cfg, gstate=None):
    backend = current_backend(cfg)
    if backend == "kitty":
        return kitty_clear()
    if backend == "wt":
        return wt_remove_background(gstate)
    return None


# ── render pipeline ─────────────────────────────────────────────────────

class Ctx:
    pass


def render_once(cfg, ok, count, cwd):
    gstate = load_state("global")
    chpwd = gstate.get("cwd") != cwd
    gstate["cwd"] = cwd

    name = cfg["module"]
    fn = MODULES.get(name, mod_metaballs)
    ctx = Ctx()
    ctx.pal = Pal(cfg["palette"])
    ctx.palname = cfg["palette"]
    ctx.ok = ok
    ctx.count = count
    ctx.cwd = cwd
    ctx.chpwd = chpwd
    ctx.seed = seed_for(cwd)
    ctx.state = load_state(name)
    # per-dir modules only need re-rendering on cd — UNLESS the palette
    # changed (their output bakes the palette in) or the overlay is live.
    if name in PER_DIR_MODULES and not chpwd and gstate.get("last_module") == name \
            and gstate.get("last_palette") == cfg["palette"] \
            and gstate.get("last_png") and os.path.exists(gstate.get("last_png", "")) \
            and cfg["overlay"] != "exitcode":
        return None  # nothing would change
    grid = fn(ctx)
    save_state(name, ctx.state)

    # image-swap backends (kitty) can't dim the image themselves, so bake
    # the opacity into the PNG; WT does its own blend, so leave it full.
    backend = current_backend(cfg)
    blend = None if backend_blends(backend) else float(cfg.get("opacity", 0.18))
    img = compose(grid, cfg["resolution"], ctx.pal.bg, blend=blend)
    if cfg.get("overlay") == "exitcode":
        img = overlay_exitcode(img, gstate, ok)

    # unique filename every frame: WT caches background images by path, so
    # reusing paths can resurrect stale frames. Keep the two newest, delete
    # the rest (the previous one may still be on screen mid-swap).
    png = os.path.join(HERE, f"termbg-{int(time.time() * 1000)}.png")
    write_png(png, img)
    bg_hex = "#%02x%02x%02x" % tuple(int(c) for c in ctx.pal.bg)
    err = apply_background(cfg, png, float(cfg.get("opacity", 0.18)), bg_hex, gstate)
    try:
        frames = [os.path.join(HERE, f) for f in os.listdir(HERE)
                  if f.startswith("termbg-") and f.endswith(".png")]
        frames.sort(key=os.path.getmtime, reverse=True)
        for f in frames[2:]:
            os.remove(f)
    except OSError:
        pass
    gstate["last_module"] = name
    gstate["last_palette"] = cfg["palette"]
    gstate["last_png"] = png
    save_state("global", gstate)
    return err


def read_last_event():
    try:
        with open(EVENTS, "r", encoding="utf-8", errors="replace") as f:
            lines = [ln.strip() for ln in f if ln.strip()]
        open(EVENTS, "w").close()
    except OSError:
        return None
    if not lines:
        return None
    parts = lines[-1].split("|", 2)
    if len(parts) != 3:
        return None
    return parts[0] == "ok", int(parts[1] or 0), parts[2]


def daemon(pidfile):
    born = time.time()
    last_render = 0.0
    while True:
        time.sleep(0.10)
        if time.time() - born > 3.0 and not os.path.exists(pidfile):
            return
        ev = read_last_event()
        if ev is None:
            continue
        cfg = load_config()
        throttle = cfg.get("throttle_ms", 900) / 1000.0
        wait = throttle - (time.time() - last_render)
        if wait > 0:
            time.sleep(wait)
        ok, count, cwd = ev
        try:
            render_once(cfg, ok, count, cwd)
        except Exception:
            pass  # a bad frame must never kill the daemon
        last_render = time.time()


# ── CLI ─────────────────────────────────────────────────────────────────

E = "\x1b["
RESET = E + "0m"
DIM = E + "2m"
BOLD = E + "1m"
GREEN = E + "38;2;126;231;135m"
YELLOW = E + "38;2;255;223;92m"
BLUE = E + "38;2;122;162;247m"
GREY = E + "38;2;140;145;160m"


def _swatch(name):
    p = _accent_palette() if name == "accent" else PALETTES[name]
    return "".join(f"{E}38;2;{int(_hx(c)[0])};{int(_hx(c)[1])};{int(_hx(c)[2])}m██"
                   for c in p["ramp"]) + RESET


def pretty_status(cfg):
    running = None
    if "--running" in sys.argv:
        running = sys.argv[sys.argv.index("--running") + 1] == "1"
    if running is True:
        state = f"{GREEN}● running{RESET} {DIM}— evolving with every command{RESET}"
    elif running is False:
        state = f"{YELLOW}● frozen/off{RESET} {DIM}— image (if any) is standing still{RESET}"
    else:
        state = f"{DIM}state unknown — use the 'termbg' shell command{RESET}"

    print()
    print(f"  {BLUE}{BOLD}termbg{RESET} {DIM}— a background that paints itself as you work{RESET}")
    print(f"  {state}")
    print()
    print(f"  {BLUE}now:{RESET} module {BOLD}{cfg['module']}{RESET}"
          f" {DIM}·{RESET} palette {BOLD}{cfg['palette']}{RESET} {_swatch(cfg['palette'])}"
          f" {DIM}·{RESET} overlay {BOLD}{cfg['overlay'] or 'none'}{RESET}"
          f" {DIM}·{RESET} opacity {BOLD}{cfg.get('opacity')}{RESET}")
    print()
    print(f"  {BLUE}modules{RESET} {DIM}(termbg use <name>){RESET}")
    for m in MODULES:
        mark = f"{GREEN}*{RESET}" if m == cfg["module"] else " "
        print(f"   {mark} {BOLD}{m:<12}{RESET}{DIM}{MODULE_DESCS[m]}{RESET}")
    print()
    print(f"  {BLUE}palettes{RESET} {DIM}(termbg palette <name>){RESET}")
    for name in list(PALETTES) + ["accent"]:
        mark = f"{GREEN}*{RESET}" if name == cfg["palette"] else " "
        print(f"   {mark} {_swatch(name)}  {BOLD}{name:<11}{RESET}{DIM} {PALETTE_DESCS[name]}{RESET}")
    print()
    print(f"  {BLUE}overlay{RESET} {DIM}(termbg overlay <name>){RESET}")
    print(f"     {BOLD}exitcode{RESET}    {DIM}red vignette flash when a command fails, fades over"
          f" the next few commands{RESET}")
    print(f"     {BOLD}none{RESET}        {DIM}just the module, no reactions{RESET}")
    print()
    print(f"  {DIM} termbg on              start — background evolves per command{RESET}")
    print(f"  {DIM} termbg freeze          stop evolving, keep the current image{RESET}")
    print(f"  {DIM} termbg off             stop and remove the background{RESET}")
    print(f"  {DIM} termbg once            paint a single fresh frame (no daemon){RESET}")
    print(f"  {DIM} termbg use <module>    switch visual{RESET}")
    print(f"  {DIM} termbg palette <name>  switch colors{RESET}")
    print(f"  {DIM} termbg opacity <0-0.6> how strongly it shows through (now"
          f" {cfg.get('opacity')}){RESET}")
    print()


def _apply(cfg):
    """Repaint after a config change — via the daemon if one is running
    (single writer: the CLI must never render in parallel with it)."""
    if daemon_running():
        nudge_daemon()
        return None
    return render_once(cfg, True, int(time.time()), os.getcwd())


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    # positional args, skipping --flag pairs like "--settings <path>"
    args = []
    skip = False
    for i, a in enumerate(sys.argv[1:], 1):
        if skip:
            skip = False
            continue
        if a.startswith("--"):
            skip = a in ("--pidfile", "--settings", "--running")
            continue
        args.append(a)
    cmd = args[0] if args else "status"
    cfg = load_config()

    if cmd == "daemon":
        pf = sys.argv[sys.argv.index("--pidfile") + 1] if "--pidfile" in sys.argv else None
        daemon(pf)
        return 0
    if cmd == "once":
        if daemon_running():
            nudge_daemon()
            print(f"termbg: asked the daemon for a fresh {cfg['module']} frame")
            return 0
        err = render_once(cfg, True, int(time.time()), os.getcwd())
        print(err if err else f"termbg: rendered one {cfg['module']} frame ({cfg['palette']})")
        return 1 if err else 0
    if cmd == "off":
        gstate = load_state("global")
        err = clear_background(cfg, gstate)
        save_state("global", gstate)
        print(err if err else "termbg: background removed")
        return 1 if err else 0
    if cmd == "use" and len(args) > 1:
        if args[1] not in MODULES:
            print(f"termbg: unknown module — choose from: {', '.join(MODULES)}")
            return 1
        cfg["module"] = args[1]
        save_config(cfg)
        err = _apply(cfg)
        print(err if err else f"termbg: module -> {args[1]} ({MODULE_DESCS[args[1]]})")
        return 0
    if cmd == "palette" and len(args) > 1:
        if args[1] not in PALETTES and args[1] != "accent":
            print(f"termbg: palettes: {', '.join(list(PALETTES) + ['accent'])}")
            return 1
        cfg["palette"] = args[1]
        save_config(cfg)
        err = _apply(cfg)
        print(err if err else f"termbg: palette -> {args[1]}  {_swatch(args[1])}")
        return 0
    if cmd == "opacity" and len(args) > 1:
        try:
            v = max(0.05, min(0.6, float(args[1])))
        except ValueError:
            print("termbg: opacity takes a number, e.g. termbg opacity 0.3")
            return 1
        cfg["opacity"] = v
        save_config(cfg)
        err = _apply(cfg)
        print(err if err else f"termbg: opacity -> {v}")
        return 0
    if cmd == "overlay" and len(args) > 1:
        cfg["overlay"] = "exitcode" if args[1] == "exitcode" else ""
        save_config(cfg)
        print(f"termbg: overlay -> {cfg['overlay'] or 'none'}")
        return 0
    pretty_status(cfg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
