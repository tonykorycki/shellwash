#!/usr/bin/env python3
"""
bgfx.py — a tiny metaballs lava lamp that lives in the corner of your
terminal while you keep working. Spawned by the `lava` shell command,
it shares the console and repaints a small dimmed panel in the top-right
~10x per second, saving and restoring the cursor around each paint so
your prompt and typing stay where they belong.

Exits on its own when the pidfile is deleted (how `lava off` stops it,
alongside a process kill) or when the console goes away.
"""

import math
import os
import random
import sys
import time

import numpy as np

PXW = 26          # pixel columns (= text columns)
PXH = 14          # pixel rows (= 7 text rows)


def _buddy_in_corner():
    """True if a buddy owns the top-right corner: a pinned pet daemon
    (Windows) or the Linux inline corner buddy (features.sprite on)."""
    here = os.path.dirname(os.path.abspath(__file__))
    if os.path.exists(os.path.join(here, "bedazzle.pet.pid")):
        return True
    try:
        import json
        with open(os.path.join(here, "bedazzle.config.json"), encoding="utf-8-sig") as f:
            return bool(json.load(f).get("features", {}).get("sprite", False))
    except Exception:
        return False


# start below the buddy if one owns the top-right corner
TOP = 8 if _buddy_in_corner() else 2
FPS = 10
DIM = 0.45        # background-y brightness

PIDFILE = None
if "--pidfile" in sys.argv:
    PIDFILE = sys.argv[sys.argv.index("--pidfile") + 1]

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


def make_seeds(n=5):
    return [(random.uniform(0.35, 1.0), random.uniform(0.35, 1.0),
             random.uniform(0, math.tau), random.uniform(0, math.tau),
             random.uniform(0.12, 0.24)) for _ in range(n)]


SEEDS = make_seeds()
Y, X = np.mgrid[-1.0:1.0:complex(0, PXH), -1.6:1.6:complex(0, PXW)]


def frame(t):
    field = np.zeros_like(X)
    for fx, fy, px, py, r in SEEDS:
        bx = math.sin(t * fx + px) * 1.25
        by = math.cos(t * fy + py) * 0.7
        field += r * r / ((X - bx) ** 2 + (Y - by) ** 2 + 1e-4)
    v = np.clip(field * 0.55, 0, 2.2)
    inside = v > 1.0
    glow = np.clip(v, 0, 1) ** 3
    rim = np.clip(1.0 - np.abs(v - 1.0) * 6.0, 0, 1)
    r = glow * 0.15 + inside * np.clip(v - 1.0, 0, 1) * 0.9 + rim
    g = glow * 0.35 + inside * 0.25 + rim * 0.9
    b = glow * 0.85 + inside * 0.55 + rim * 0.4
    buf = np.dstack([
        np.clip(r * 255 * DIM, 0, 255),
        np.clip(g * 255 * DIM, 0, 255),
        np.clip(b * 255 * DIM, 0, 255),
    ]).astype(np.uint8)
    return buf


LUM_THRESHOLD = 26  # below this a pixel counts as empty -> cell stays transparent


def to_runs(buf, prev_mask, row0, col0):
    """Positioned escape-sequence runs. Cells with no lit pixels are left
    alone (true transparency); cells lit last frame but empty now get
    erased so moving blobs clean up their trail. Returns (output, mask)."""
    top = buf[0::2]
    bot = buf[1::2]
    lit_top = top.astype(np.int32).sum(axis=2) > LUM_THRESHOLD
    lit_bot = bot.astype(np.int32).sum(axis=2) > LUM_THRESHOLD
    mask = lit_top | lit_bot
    tl, bl = top.tolist(), bot.tolist()
    out = []
    rows, cols = mask.shape
    for y in range(rows):
        x = 0
        while x < cols:
            if not mask[y][x] and not prev_mask[y][x]:
                x += 1
                continue
            start = x
            parts = []
            while x < cols and (mask[y][x] or prev_mask[y][x]):
                if not mask[y][x]:
                    parts.append("\x1b[0m ")
                else:
                    tr, tg, tb = tl[y][x]
                    br, bg, bb = bl[y][x]
                    if lit_top[y][x] and lit_bot[y][x]:
                        parts.append(f"\x1b[38;2;{tr};{tg};{tb};48;2;{br};{bg};{bb}m▀")
                    elif lit_top[y][x]:
                        parts.append(f"\x1b[0m\x1b[38;2;{tr};{tg};{tb}m▀")
                    else:
                        parts.append(f"\x1b[0m\x1b[38;2;{br};{bg};{bb}m▄")
                x += 1
            out.append(f"\x1b[{row0 + y};{col0 + start}H" + "".join(parts) + "\x1b[0m")
    return "".join(out), mask


def erase_runs(mask, row0, col0):
    out = []
    for y in range(mask.shape[0]):
        xs = np.where(mask[y])[0]
        if xs.size:
            out.append(f"\x1b[{row0 + y};{col0 + xs[0]}H\x1b[0m"
                       + " " * (xs[-1] - xs[0] + 1))
    return "".join(out)


def main():
    enable_vt()
    t0 = time.perf_counter()
    born = time.time()
    last_pid_check = 0.0
    prev_mask = np.zeros((PXH // 2, PXW), dtype=bool)
    last_x0 = None
    while True:
        now = time.perf_counter()
        t = now - t0
        # stop when the pidfile disappears (grace period for startup race)
        if PIDFILE and now - last_pid_check > 1.0:
            last_pid_check = now
            if time.time() - born > 3.0 and not os.path.exists(PIDFILE):
                return
        try:
            cols, _rows = term_size()
        except OSError:
            return
        x0 = max(1, cols - PXW - 1)
        out = ""
        if last_x0 is not None and x0 != last_x0:
            # terminal resized: wipe the panel at its old position
            out += erase_runs(prev_mask, TOP, last_x0)
            prev_mask[:] = False
        last_x0 = x0
        runs, prev_mask = to_runs(frame(t), prev_mask, TOP, x0)
        out += runs
        if out:
            try:
                OUT.write("\x1b7" + out + "\x1b8")  # save/restore cursor
                OUT.flush()
            except OSError:
                return
        time.sleep(max(0.0, 1.0 / FPS - (time.perf_counter() - now)))


if __name__ == "__main__":
    main()
