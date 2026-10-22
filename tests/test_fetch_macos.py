#!/usr/bin/env python3
"""
Fixture tests for the macOS system-fact parsers in linux/fetch.py.

These run anywhere — the point is to pin the parsing of sysctl / vm_stat /
pmset output without needing a Mac. The fixtures below are verbatim output
shapes from the real tools; if a parser regresses, these fail.

    python3 -m unittest discover tests -v
    python3 tests/test_fetch_macos.py

What these DO cover: the string/number handling once output is in hand.
What these CANNOT cover: whether the real tools on a real Mac actually emit
these shapes. Run tests/macos-smoke.sh on a Mac to confirm that half.
"""

import os
import sys
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "linux"))
import fetch  # noqa: E402


# ── fixtures: verbatim shapes from the real tools ─────────────────────────

# Apple Silicon: 16 KiB pages. Note the quoted "Translation faults" line and
# the trailing period on every count — both have tripped naive parsers.
VM_STAT_ARM = """Mach Virtual Memory Statistics: (page size of 16384 bytes)
Pages free:                               33087.
Pages active:                            458213.
Pages inactive:                          441097.
Pages speculative:                        12934.
Pages throttled:                              0.
Pages wired down:                        189440.
Pages purgeable:                           4310.
"Translation faults":                 921394812.
Pages copy-on-write:                   28174419.
Pages zero filled:                    501384712.
Pages reactivated:                      3918241.
Pages purged:                           1928471.
File-backed pages:                       304918.
Anonymous pages:                         607326.
Pages stored in compressor:              913274.
Pages occupied by compressor:            201839.
Decompressions:                         8912734.
Compressions:                          12938471.
Pageins:                                4918234.
Pageouts:                                 19283.
Swapins:                                      0.
Swapouts:                                     0.
"""

# Intel: 4 KiB pages — the page-size line must actually be read, not assumed.
VM_STAT_INTEL = """Mach Virtual Memory Statistics: (page size of 4096 bytes)
Pages free:                              200123.
Pages active:                           1500000.
Pages inactive:                         1100000.
Pages speculative:                        50000.
Pages throttled:                              0.
Pages wired down:                        800000.
Pages purgeable:                          20000.
"Translation faults":                 123456789.
Pages stored in compressor:              300000.
Pages occupied by compressor:            120000.
Swapins:                                      0.
Swapouts:                                     0.
"""

PMSET_DISCHARGING = (
    "Now drawing from 'Battery Power'\n"
    " -InternalBattery-0 (id=4653155)\t87%; discharging; 4:12 remaining present: true"
)
PMSET_CHARGING = (
    "Now drawing from 'AC Power'\n"
    " -InternalBattery-0 (id=4653155)\t64%; charging; 1:03 remaining present: true"
)
PMSET_CHARGED = (
    "Now drawing from 'AC Power'\n"
    " -InternalBattery-0 (id=4653155)\t100%; charged; 0:00 remaining present: true"
)
# Mac mini / Mac Studio / Mac Pro — no battery at all.
PMSET_DESKTOP = "Now drawing from 'AC Power'"

SYSTEM_PROFILER_INTEL = """Graphics/Displays:

    Radeon Pro 5500M:

      Chipset Model: Radeon Pro 5500M
      Type: GPU
      Bus: PCIe
      VRAM (Dynamic, Max): 4 GB
"""


class MacFactsTest(unittest.TestCase):
    """Each test installs a fake macOS environment, then asserts the parse."""

    def setUp(self):
        self._real = (fetch.IS_MAC, fetch._run, fetch._sysctl)
        fetch.IS_MAC = True
        self.sysctl = {}
        self.cmds = {}
        self.calls = []
        fetch._sysctl = lambda k: self.sysctl.get(k, "")

        def fake_run(args, timeout=3):
            self.calls.append(args[0])
            return self.cmds.get(args[0], "")

        fetch._run = fake_run

    def tearDown(self):
        fetch.IS_MAC, fetch._run, fetch._sysctl = self._real

    # ── memory ────────────────────────────────────────────────────────────

    def test_mem_apple_silicon_16k_pages(self):
        self.sysctl["hw.memsize"] = str(32 * 2 ** 30)
        self.cmds["vm_stat"] = VM_STAT_ARM
        used, total = fetch.mem_gib()
        # Activity Monitor's "Memory Used" = active + wired + compressed
        expect = (458213 + 189440 + 201839) * 16384 / 2 ** 30
        self.assertAlmostEqual(used, expect, places=6)
        self.assertAlmostEqual(total, 32.0, places=6)

    def test_mem_intel_4k_pages(self):
        self.sysctl["hw.memsize"] = str(16 * 2 ** 30)
        self.cmds["vm_stat"] = VM_STAT_INTEL
        used, total = fetch.mem_gib()
        expect = (1500000 + 800000 + 120000) * 4096 / 2 ** 30
        self.assertAlmostEqual(used, expect, places=6)
        self.assertAlmostEqual(total, 16.0, places=6)

    def test_mem_used_never_exceeds_total(self):
        """A bogus/absent hw.memsize must not render a >100% bar."""
        self.sysctl["hw.memsize"] = str(1 * 2 ** 30)   # implausibly small
        self.cmds["vm_stat"] = VM_STAT_ARM
        used, total = fetch.mem_gib()
        self.assertLessEqual(used, total)

    def test_mem_falls_back_to_4k_pages_without_header(self):
        """If the 'page size of N bytes' header is missing, the default must be
        the conservative 4096 — assuming 16384 would report 4x the real usage."""
        self.sysctl["hw.memsize"] = str(64 * 2 ** 30)
        self.cmds["vm_stat"] = "\n".join(
            ln for ln in VM_STAT_ARM.splitlines() if "page size" not in ln)
        used, _ = fetch.mem_gib()
        expect = (458213 + 189440 + 201839) * 4096 / 2 ** 30
        self.assertAlmostEqual(used, expect, places=6)

    def test_mem_survives_missing_tools(self):
        used, total = fetch.mem_gib()          # no sysctl, no vm_stat
        self.assertEqual((used, total), (0.0, 0.0))

    def test_mem_bar_fraction_is_safe_when_total_zero(self):
        """main() divides by max(tot, 1) — guard the contract mem_gib relies on."""
        used, total = fetch.mem_gib()
        self.assertEqual(fetch.bar(used / max(total, 1)).count("█"), 0)

    # ── battery ───────────────────────────────────────────────────────────

    def test_battery_discharging(self):
        self.cmds["pmset"] = PMSET_DISCHARGING
        self.assertEqual(fetch.battery_pct(), 87)

    def test_battery_charging(self):
        self.cmds["pmset"] = PMSET_CHARGING
        self.assertEqual(fetch.battery_pct(), 64)

    def test_battery_charged_full(self):
        self.cmds["pmset"] = PMSET_CHARGED
        self.assertEqual(fetch.battery_pct(), 100)

    def test_battery_desktop_has_none(self):
        """No battery must yield None (row omitted), never 0 or a junk number."""
        self.cmds["pmset"] = PMSET_DESKTOP
        self.assertIsNone(fetch.battery_pct())

    def test_battery_missing_pmset(self):
        self.assertIsNone(fetch.battery_pct())

    # ── uptime ────────────────────────────────────────────────────────────

    def test_uptime_from_boottime(self):
        boot = int(time.time()) - (86400 + 2 * 3600 + 3 * 60)
        self.sysctl["kern.boottime"] = (
            "{ sec = %d, usec = 132498 } Wed Aug 27 09:11:22 2026" % boot)
        self.assertEqual(fetch.uptime_txt(), "1d 2h 3m")

    def test_uptime_matches_sec_not_usec(self):
        """'usec' also contains 'sec' — the regex must not latch onto it."""
        boot = int(time.time()) - 3600
        self.sysctl["kern.boottime"] = "{ sec = %d, usec = 999999 }" % boot
        self.assertEqual(fetch.uptime_txt(), "1h 0m")

    def test_uptime_under_a_day_omits_days(self):
        self.sysctl["kern.boottime"] = "{ sec = %d, usec = 0 }" % (
            int(time.time()) - (5 * 3600 + 30 * 60))
        self.assertEqual(fetch.uptime_txt(), "5h 30m")

    def test_uptime_missing_sysctl(self):
        self.assertEqual(fetch.uptime_txt(), "?")

    # ── cpu / gpu / host ──────────────────────────────────────────────────

    def test_cpu_apple_silicon(self):
        self.sysctl["machdep.cpu.brand_string"] = "Apple M2 Pro"
        self.assertEqual(fetch.cpu_name(), "Apple M2 Pro")

    def test_cpu_intel(self):
        self.sysctl["machdep.cpu.brand_string"] = \
            "Intel(R) Core(TM) i9-9880H CPU @ 2.30GHz"
        self.assertIn("i9-9880H", fetch.cpu_name())

    def test_gpu_apple_silicon_skips_system_profiler(self):
        """The login path must not pay for system_profiler on ARM Macs."""
        self.sysctl["machdep.cpu.brand_string"] = "Apple M2 Pro"
        self.assertEqual(fetch.gpu_name(), "Apple M2 Pro")
        self.assertNotIn("system_profiler", self.calls)

    def test_gpu_intel_uses_system_profiler(self):
        self.sysctl["machdep.cpu.brand_string"] = "Intel(R) Core(TM) i9-9880H"
        self.cmds["system_profiler"] = SYSTEM_PROFILER_INTEL
        self.assertEqual(fetch.gpu_name(), "Radeon Pro 5500M")
        self.assertIn("system_profiler", self.calls)

    def test_gpu_absent_is_empty_not_crash(self):
        self.sysctl["machdep.cpu.brand_string"] = "Intel(R) Core(TM) i9"
        self.assertEqual(fetch.gpu_name(), "")

    def test_host_model(self):
        self.sysctl["hw.model"] = "Mac14,9"
        self.assertEqual(fetch.host_model(), "Mac14,9")

    def test_host_falls_back_to_hostname(self):
        self.assertTrue(fetch.host_model())      # never empty

    # ── no crashes with nothing available ─────────────────────────────────

    def test_every_fact_survives_a_bare_environment(self):
        """Worst case: sandboxed shell where none of the tools answer."""
        for fn in (fetch.os_pretty, fetch.cpu_name, fetch.gpu_name,
                   fetch.host_model, fetch.uptime_txt, fetch.mem_gib,
                   fetch.battery_pct, fetch.terminal_name):
            fn()   # must not raise


class LinuxRegressionTest(unittest.TestCase):
    """The macOS work must not have disturbed the Linux path."""

    @unittest.skipUnless(sys.platform.startswith("linux"), "linux only")
    def test_linux_facts_still_real(self):
        self.assertTrue(fetch.os_pretty())
        self.assertTrue(fetch.cpu_name())
        used, total = fetch.mem_gib()
        self.assertGreater(total, 0, "/proc/meminfo parse regressed")
        self.assertLessEqual(used, total)
        self.assertNotEqual(fetch.uptime_txt(), "?")


if __name__ == "__main__":
    unittest.main(verbosity=2)
