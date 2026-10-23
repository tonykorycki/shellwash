#!/usr/bin/env python3
"""
Tests for the parts of linux/fetch.py that keep the panel on screen: the
lspci GPU-name tidy-up and the ANSI-aware truncation that stops long rows
from wrapping into the logo column.

    python3 -m unittest discover tests -v
"""

import os
import re
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "linux"))
import fetch  # noqa: E402


ANSI = re.compile(r"\x1b\[[0-9;]*m")


class GpuPretty(unittest.TestCase):
    def test_lspci_names(self):
        cases = {
            "ASPEED Technology, Inc. ASPEED Graphics Family (rev 52)":
                "ASPEED Graphics Family",
            "Intel Corporation Raptor Lake-P [Iris Xe Graphics] (rev 04)":
                "Intel Iris Xe Graphics",
            "NVIDIA Corporation GA102 [GeForce RTX 3090] (rev a1)":
                "NVIDIA GeForce RTX 3090",
            "Advanced Micro Devices, Inc. [AMD/ATI] Navi 21 "
            "[Radeon RX 6800/6800 XT / 6900 XT] (rev c1)":
                "AMD Radeon RX 6800/6800 XT / 6900 XT",
            "Matrox Electronics Systems Ltd. G200eR2 (rev 01)":
                "Matrox G200eR2",
            "Some Vendor Thing 9000":
                "Some Vendor Thing 9000",
        }
        for raw, want in cases.items():
            self.assertEqual(fetch.gpu_pretty(raw), want, raw)

    def test_old_caches_cut_at_48_chars(self):
        # Caches written before gpu_pretty hold the raw name sliced to 48.
        self.assertEqual(
            fetch.gpu_pretty("ASPEED Technology, Inc. ASPEED Graphics Family ("),
            "ASPEED Graphics Family")
        self.assertEqual(
            fetch.gpu_pretty("Intel Corporation Raptor Lake-P [Iris Xe Graphic"),
            "Intel Raptor Lake-P")

    def test_idempotent(self):
        for s in ("ASPEED Graphics Family", "Intel Iris Xe Graphics",
                  "Apple M2 Pro", ""):
            self.assertEqual(fetch.gpu_pretty(fetch.gpu_pretty(s)),
                             fetch.gpu_pretty(s))


class Fit(unittest.TestCase):
    def test_short_strings_untouched(self):
        self.assertEqual(fetch.fit("hello", 10), "hello")
        self.assertEqual(fetch.fit("hello", 5), "hello")

    def test_truncates_with_ellipsis(self):
        out = fetch.fit("hello world", 8)
        self.assertEqual(ANSI.sub("", out), "hello w…")

    def test_escapes_cost_nothing_and_color_is_reset(self):
        s = f"{fetch.fg(1, 2, 3)}abcdef{fetch.RESET}ghij"
        self.assertEqual(fetch.fit(s, 10), s)
        out = fetch.fit(s, 5)
        self.assertEqual(ANSI.sub("", out), "abcd…")
        self.assertTrue(out.endswith(fetch.RESET))

    def test_wide_chars_count_double(self):
        out = fetch.fit("☀️ 漢字漢字", 6)
        self.assertLessEqual(fetch.vis_width(out), 6)

    def test_bar_row_measures_its_cells(self):
        self.assertEqual(fetch.vis_width(fetch.bar(.5)), 12)

    def test_zero_width(self):
        self.assertEqual(ANSI.sub("", fetch.fit("abc", 0)), "")


if __name__ == "__main__":
    unittest.main()
