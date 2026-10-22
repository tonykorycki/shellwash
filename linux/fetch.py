#!/usr/bin/env python3
"""
fetch.py — fastfetch-style system panel for Linux and macOS, in your accent hue.

The PowerShell `fetch` used Windows CIM/WMI; this is the native port:
system facts from /proc, /sys and os-release (or sysctl / vm_stat / pmset
on macOS), a pixel logo from logos.py tinted to your bedazzle accent,
memory/disk bars, and the 16-color palette strip. Run on demand (bedazzle
theme startup, or `fetch`).

  fetch.py [--login] [--logo <name>] [--gallery]

Static facts are cached in bedazzle.cache.json so repeat calls are instant.
"""

import colorsys
import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import time

import adconf
import logos

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CACHE = os.path.join(ROOT, "bedazzle.cache.json")
IS_MAC = sys.platform == "darwin"
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


def _run(args, timeout=3):
    """Capture a command's stdout, or "" if it is missing / slow / angry."""
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip() if r.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def _sysctl(key):
    return _run(["sysctl", "-n", key], timeout=2)


def os_pretty():
    if IS_MAC:
        ver = platform.mac_ver()[0]
        return f"macOS {ver}".strip() if ver else "macOS"
    for line in _read("/etc/os-release").splitlines():
        if line.startswith("PRETTY_NAME="):
            return line.split("=", 1)[1].strip().strip('"')
    return platform.system()


def cpu_name():
    if IS_MAC:
        # Apple Silicon reports "Apple M2 Pro" here too, not just Intel parts.
        return _sysctl("machdep.cpu.brand_string") or platform.machine() or "unknown"
    for line in _read("/proc/cpuinfo").splitlines():
        if line.lower().startswith("model name"):
            return " ".join(line.split(":", 1)[1].split())
    return platform.processor() or "unknown"


def gpu_name():
    if IS_MAC:
        # On Apple Silicon the GPU is the SoC, so the CPU string already has
        # the answer — worth special-casing, because this runs on the login
        # path and system_profiler takes seconds.
        chip = _sysctl("machdep.cpu.brand_string")
        if chip.startswith("Apple"):
            return chip
        # Intel Macs need the real lookup. It only runs once (the result is
        # cached in bedazzle.cache.json) — but if the cache is unwritable it
        # runs every login, hence the tight timeout.
        for line in _run(["system_profiler", "-detailLevel", "mini",
                          "SPDisplaysDataType"], timeout=4).splitlines():
            if "Chipset Model:" in line:
                return line.split(":", 1)[1].strip()[:48]
        return ""
    out = _run(["lspci"])
    for line in out.splitlines():
        low = line.lower()
        if "vga" in low or "3d controller" in low or "display" in low:
            return line.split(": ", 1)[-1].strip()[:48]
    return ""


def host_model():
    if IS_MAC:
        # e.g. "MacBookPro18,3" — the identifier, same as neofetch shows
        # before its marketing-name lookup table.
        return _sysctl("hw.model") or platform.node()
    name = _read("/sys/devices/virtual/dmi/id/product_name")
    vendor = _read("/sys/devices/virtual/dmi/id/sys_vendor")
    combo = f"{vendor} {name}".strip()
    return combo or platform.node()


def _uptime_secs():
    if IS_MAC:
        # kern.boottime prints "{ sec = 1724500000, usec = 12345 } Thu Aug …"
        m = re.search(r"sec\s*=\s*(\d+)", _sysctl("kern.boottime"))
        return time.time() - int(m.group(1)) if m else None
    try:
        return float(_read("/proc/uptime").split()[0])
    except (ValueError, IndexError):
        return None


def uptime_txt():
    secs = _uptime_secs()
    if secs is None or secs < 0:
        return "?"
    d, rem = divmod(int(secs), 86400)
    h, rem = divmod(rem, 3600)
    m = rem // 60
    return (f"{d}d " if d else "") + f"{h}h {m}m"


def _mem_gib_mac():
    total = int(_sysctl("hw.memsize") or 0) / 2 ** 30
    out = _run(["vm_stat"], timeout=2)
    if not total or not out:
        return 0.0, total
    page = 4096
    m = re.search(r"page size of (\d+) bytes", out)
    if m:
        page = int(m.group(1))
    pages = {}
    for line in out.splitlines():
        m = re.match(r'"?([^":]+)"?:\s+(\d+)\.', line)
        if m:
            pages[m.group(1).strip().lower()] = int(m.group(2))
    # Activity Monitor's "Memory Used" = active + wired + compressed.
    used_pages = (pages.get("pages active", 0)
                  + pages.get("pages wired down", 0)
                  + pages.get("pages occupied by compressor", 0))
    return min(used_pages * page / 2 ** 30, total), total


def mem_gib():
    if IS_MAC:
        return _mem_gib_mac()
    total = avail = 0
    for line in _read("/proc/meminfo").splitlines():
        if line.startswith("MemTotal:"):
            total = int(line.split()[1]) / 1048576
        elif line.startswith("MemAvailable:"):
            avail = int(line.split()[1]) / 1048576
    return total - avail, total


def battery_pct():
    if IS_MAC:
        # "-InternalBattery-0 (id=…)	87%; discharging; 4:12 remaining"
        m = re.search(r"(\d+)%", _run(["pmset", "-g", "batt"], timeout=2))
        return int(m.group(1)) if m else None
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
        if os.path.exists(wf) and time.time() - os.path.getmtime(wf) < 7200:
            return _read(wf)
    except OSError:
        pass
    return ""


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
    if "--gallery" in sys.argv:
        logos.main(["gallery"])
        return
    cfg = adconf.load()
    logo_name = logos.choose(cfg)
    if "--logo" in sys.argv:
        i = sys.argv.index("--logo")
        logo_name = sys.argv[i + 1] if i + 1 < len(sys.argv) else ""
        if logo_name not in logos.LOGOS:
            print(f" unknown logo '{logo_name}' (have: {', '.join(logos.LOGOS)})")
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

    logo, logo_w = logos.lines(logo_name, accent_hue(), cfg.get("logo_bands", False))
    n = max(len(logo), len(rows))
    print()
    for i in range(n):
        left = logo[i] if i < len(logo) else " " * logo_w
        if i < len(rows):
            k, v = rows[i]
            right = f"{acc}{k.ljust(9)}{RESET}{v}" if k else v
        else:
            right = ""
        print(f"  {left}  {right}")
    print()


if __name__ == "__main__":
    main()
