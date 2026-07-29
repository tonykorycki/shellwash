#!/usr/bin/env python3
"""
fetch.py — fastfetch-style system panel for Linux, in your accent hue.

The PowerShell `fetch` used Windows CIM/WMI; this is the native port:
system facts from /proc, /sys and os-release, a math-generated pixel
planet tinted to your bedazzle accent, memory/disk bars, and the 16-color
palette strip. Run on demand (bedazzle theme startup, or `fetch`).

Static facts are cached in bedazzle.cache.json so repeat calls are instant.
"""

import colorsys
import json
import os
import platform
import shutil
import socket
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CACHE = os.path.join(ROOT, "bedazzle.cache.json")
E = "\x1b["
RESET = E + "0m"
DIM = E + "2m"
BOLD = E + "1m"


def accent_hue():
    try:
        with open(os.path.join(ROOT, "bedazzle.config.json"), encoding="utf-8-sig") as f:
            return float(json.load(f).get("accent", 215.0))
    except Exception:
        return 215.0


def fg(r, g, b):
    return f"{E}38;2;{int(r)};{int(g)};{int(b)}m"


def hsv(h, s, v):
    r, g, b = colorsys.hsv_to_rgb((h % 360) / 360.0, s, v)
    return int(r * 255), int(g * 255), int(b * 255)


# ── system facts ──────────────────────────────────────────────────────────

def _read(path, default=""):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return default


def os_pretty():
    for line in _read("/etc/os-release").splitlines():
        if line.startswith("PRETTY_NAME="):
            return line.split("=", 1)[1].strip().strip('"')
    return platform.system()


def cpu_name():
    for line in _read("/proc/cpuinfo").splitlines():
        if line.lower().startswith("model name"):
            return " ".join(line.split(":", 1)[1].split())
    return platform.processor() or "unknown"


def gpu_name():
    try:
        import subprocess
        out = subprocess.run(["lspci"], capture_output=True, text=True, timeout=3).stdout
        for line in out.splitlines():
            low = line.lower()
            if "vga" in low or "3d controller" in low or "display" in low:
                return line.split(": ", 1)[-1].strip()[:48]
    except Exception:
        pass
    return ""


def host_model():
    name = _read("/sys/devices/virtual/dmi/id/product_name")
    vendor = _read("/sys/devices/virtual/dmi/id/sys_vendor")
    combo = f"{vendor} {name}".strip()
    return combo or platform.node()


def uptime_txt():
    try:
        secs = float(_read("/proc/uptime").split()[0])
    except (ValueError, IndexError):
        return "?"
    d, rem = divmod(int(secs), 86400)
    h, rem = divmod(rem, 3600)
    m = rem // 60
    return (f"{d}d " if d else "") + f"{h}h {m}m"


def mem_gib():
    total = avail = 0
    for line in _read("/proc/meminfo").splitlines():
        if line.startswith("MemTotal:"):
            total = int(line.split()[1]) / 1048576
        elif line.startswith("MemAvailable:"):
            avail = int(line.split()[1]) / 1048576
    return total - avail, total


def battery_pct():
    base = "/sys/class/power_supply"
    try:
        for name in sorted(os.listdir(base)):
            if name.startswith("BAT"):
                cap = _read(os.path.join(base, name, "capacity"))
                if cap.isdigit():
                    return int(cap)
    except OSError:
        pass
    return None


def local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 1))  # no packet sent; just picks the default-route iface
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return ""


def terminal_name():
    if os.environ.get("KITTY_WINDOW_ID"):
        return "kitty"
    if os.environ.get("WEZTERM_PANE"):
        return "WezTerm"
    if os.environ.get("GNOME_TERMINAL_SCREEN"):
        return "GNOME Terminal"
    return os.environ.get("TERM_PROGRAM") or os.environ.get("TERM", "?")


def load_static():
    try:
        with open(CACHE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        pass
    st = {"os": os_pretty(), "kernel": platform.release(), "cpu": cpu_name(),
          "gpu": gpu_name(), "host": host_model()}
    try:
        with open(CACHE, "w", encoding="utf-8") as f:
            json.dump(st, f)
    except OSError:
        pass
    return st


def weather():
    wf = os.path.join(ROOT, "bedazzle.weather.txt")
    try:
        import time
        if os.path.exists(wf) and time.time() - os.path.getmtime(wf) < 7200:
            return _read(wf)
    except OSError:
        pass
    return ""


# ── pixel planet (generated, tinted to accent) ─────────────────────────────

def planet_lines():
    hue = accent_hue()
    W, H = 23, 14
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
    lines = []
    for y in range(0, H, 2):
        parts = []
        for x in range(W):
            t = grid[y][x]
            b = grid[y + 1][x] if y + 1 < H else None
            if t is None and b is None:
                parts.append(RESET + " ")
            elif b is None:
                parts.append(f"{RESET}{fg(*t)}▀")
            elif t is None:
                parts.append(f"{RESET}{fg(*b)}▄")
            else:
                parts.append(f"{E}38;2;{t[0]};{t[1]};{t[2]};48;2;{b[0]};{b[1]};{b[2]}m▀")
        lines.append("".join(parts) + RESET)
    return lines


def bar(frac, width=12):
    frac = max(0.0, min(1.0, frac))
    fill = round(frac * width)
    col = fg(126, 231, 135) if frac < .7 else fg(255, 223, 92) if frac < .85 else fg(248, 81, 73)
    return f"{col}{'█' * fill}{E}38;2;70;74;90m{'░' * (width - fill)}{RESET}"


def fetch_enabled():
    try:
        with open(os.path.join(ROOT, "bedazzle.config.json"), encoding="utf-8-sig") as f:
            return bool(json.load(f).get("features", {}).get("fetch", True))
    except Exception:
        return True


def main():
    # --login: only print if the 'fetch' feature is on (honors the toggle).
    # This is invoked from the TOP of .zshrc, before p10k's instant prompt,
    # so a login banner never trips the "console output" warning.
    if "--login" in sys.argv and not fetch_enabled():
        return
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    acc_rgb = hsv(accent_hue(), .62, .98)
    acc = fg(*acc_rgb)
    st = load_static()
    user = f"{acc}{os.environ.get('USER', 'user')}{RESET}{DIM}@{RESET}{acc}{socket.gethostname()}{RESET}"
    used, tot = mem_gib()
    du = shutil.disk_usage("/")

    rows = [("", user),
            ("", f"{DIM}{'-' * (len(os.environ.get('USER', 'user')) + len(socket.gethostname()) + 1)}{RESET}"),
            ("os", st["os"]), ("kernel", st["kernel"]), ("uptime", uptime_txt()),
            ("shell", os.path.basename(os.environ.get("SHELL", "zsh"))),
            ("term", terminal_name()), ("host", st["host"]),
            ("cpu", st["cpu"]), ]
    if st.get("gpu"):
        rows.append(("gpu", st["gpu"]))
    rows.append(("memory", f"{bar(used / max(tot, 1))}  {used:.1f} / {tot:.1f} GiB"))
    rows.append(("disk", f"{bar(du.used / du.total)}  {du.used // 2**30} / {du.total // 2**30} GB"))
    ip = local_ip()
    if ip:
        rows.append(("ip", ip))
    wx = weather()
    if wx:
        rows.append(("weather", wx))
    bat = battery_pct()
    if bat is not None:
        rows.append(("battery", f"{bat}%"))
    rows.append(("", ""))
    rows.append(("", "".join(f"{E}4{i}m   " for i in range(8)) + RESET))
    rows.append(("", "".join(f"{E}10{i}m   " for i in range(8)) + RESET))

    logo = planet_lines()
    n = max(len(logo), len(rows))
    print()
    for i in range(n):
        left = logo[i] if i < len(logo) else " " * 23
        if i < len(rows):
            k, v = rows[i]
            right = f"{acc}{k.ljust(9)}{RESET}{v}" if k else v
        else:
            right = ""
        print(f"  {left}  {right}")
    print()


if __name__ == "__main__":
    main()
