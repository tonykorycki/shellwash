#!/usr/bin/env python3
"""
Tests for linux/logos.py: the pixel grid, the fastfetch-format text parser,
discovery and overrides, the per-launch choice, and the `bedazzle logo` CLI
against a throwaway config file and logo directory.

    python3 -m unittest discover tests -v
"""

import contextlib
import io
import json
import os
import random
import re
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "linux"))
import adconf  # noqa: E402
import logos  # noqa: E402


ANSI = re.compile(r"\x1b\[[0-9;]*m")


def visible(line):
    return ANSI.sub("", line)


class Pixel(unittest.TestCase):
    def test_planet_is_a_full_grid_of_rgb_or_none(self):
        for hue in (0.0, 215.0, 359.9):
            grid = logos.planet(hue)
            self.assertEqual(len(grid), logos.H)
            for row in grid:
                self.assertEqual(len(row), logos.W)
                for px in row:
                    self.assertTrue(px is None or all(0 <= c <= 255 for c in px))

    def test_render_packs_two_pixel_rows_per_line(self):
        out, width = logos.lines("planet", 215.0)
        self.assertEqual((len(out), width), ((logos.H + 1) // 2, logos.W))


class Text(unittest.TestCase):
    def test_dollar_escape_and_color_marks_are_not_printed(self):
        out, width = logos.render_text("$1ab$2$$c\n$3d", 215.0)
        self.assertEqual([visible(l) for l in out], ["ab$c", "d   "])
        self.assertEqual(width, 4)

    def test_lone_dollar_and_unknown_mark_stay_literal(self):
        out, _ = logos.render_text("a$ b$xc$", 0.0)
        self.assertEqual(visible(out[0]), "a$ b$xc$")

    def test_color_carries_over_line_ends(self):
        pal = logos.text_palette(100.0)
        out, _ = logos.render_text("$2a\nb", 100.0)
        r, g, b = pal[1]
        self.assertTrue(out[1].startswith(f"\x1b[38;2;{r};{g};{b}m"))

    def test_slots_remap_marks_to_palette_entries(self):
        pal = logos.text_palette(100.0)
        out, _ = logos.render_text("$1a", 100.0, slots=(2, 0, 1))
        r, g, b = pal[2]
        self.assertIn(f"38;2;{r};{g};{b}m", out[0])

    def test_bands_color_each_row_and_ignore_marks(self):
        out, _ = logos.render_text("\n".join(f"$2row{i}" for i in range(6)), 0.0, bands=True)
        firsts = {re.match(r"\x1b\[38;2;([0-9;]+)m", l).group(1) for l in out}
        self.assertEqual(len(firsts), 6)
        self.assertTrue(all(l.count("38;2") == 1 for l in out))

    def test_every_bundled_text_logo_renders_square(self):
        for name, (kind, _, _) in logos.LOGOS.items():
            if kind != "text":
                continue
            for bands in (False, True):
                out, width = logos.lines(name, 215.0, bands)
                self.assertGreater(len(out), 3, name)
                self.assertLessEqual(width, 48, f"{name} too wide for the panel")
                self.assertEqual({len(visible(l)) for l in out}, {width}, name)


class Discovery(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self._orig = logos.USER_DIR
        logos.USER_DIR = self.tmp

    def tearDown(self):
        logos.USER_DIR = self._orig
        logos.refresh()
        shutil.rmtree(self.tmp)

    def test_user_file_adds_and_overrides(self):
        for name, art in (("mine", "$1hi"), ("arch", "$1over")):
            with open(os.path.join(self.tmp, name + ".txt"), "w") as f:
                f.write(art)
        found = logos.refresh()
        self.assertEqual(found["mine"][2], "custom")
        self.assertEqual(found["arch"][1], os.path.join(self.tmp, "arch.txt"))
        self.assertEqual(visible(logos.lines("arch", 0.0)[0][0]), "over")

    def test_planet_lists_first_then_bundled_order(self):
        names = list(logos.refresh())
        self.assertEqual(names[0], "planet")
        bundled = [n for n in logos.DESCRIPTIONS if n in names]
        self.assertEqual(names[1:1 + len(bundled)], bundled)


class Choose(unittest.TestCase):
    def test_fixed_choice(self):
        self.assertEqual(logos.choose({"logo": "gentoo"}), "gentoo")

    def test_unknown_name_falls_back(self):
        self.assertEqual(logos.choose({"logo": "nope"}), logos.DEFAULT)

    def test_random_rolls_only_from_the_pool(self):
        cfg = {"logo": "random", "logo_pool": ["gentoo", "arch", "gone"]}
        rolls = {logos.choose(cfg, random.Random(i)) for i in range(60)}
        self.assertEqual(rolls, {"gentoo", "arch"})

    def test_empty_or_stale_pool_means_all(self):
        self.assertEqual(logos.pool({"logo_pool": []}), list(logos.LOGOS))
        self.assertEqual(logos.pool({"logo_pool": ["gone"]}), list(logos.LOGOS))


class Cli(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        with open(self.path, "w") as f:
            json.dump({"accent": 140.0, "theme": "p10k"}, f)
        self._orig = adconf.CONFIG
        adconf.CONFIG = self.path

    def tearDown(self):
        adconf.CONFIG = self._orig
        os.unlink(self.path)

    def run_cli(self, *argv):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            rc = logos.main(list(argv))
        return rc, out.getvalue()

    def saved(self):
        with open(self.path) as f:
            return json.load(f)

    def test_pick_and_random_persist(self):
        self.assertEqual(self.run_cli("gentoo")[0], 0)
        self.assertEqual(self.saved()["logo"], "gentoo")
        self.run_cli("random")
        self.assertEqual(self.saved()["logo"], "random")

    def test_unknown_name_is_rejected_unchanged(self):
        rc, out = self.run_cli("nope")
        self.assertEqual(rc, 1)
        self.assertIn("unknown logo", out)
        self.assertNotIn("logo", self.saved())

    def test_pool_set_add_rm_all(self):
        self.run_cli("pool", "arch", "gentoo")
        self.assertEqual(self.saved()["logo_pool"], ["arch", "gentoo"])
        self.run_cli("pool", "add", "planet", "arch")
        self.assertEqual(self.saved()["logo_pool"], ["arch", "gentoo", "planet"])
        self.run_cli("pool", "rm", "gentoo")
        self.assertEqual(self.saved()["logo_pool"], ["arch", "planet"])
        self.run_cli("pool", "all")
        self.assertEqual(self.saved()["logo_pool"], [])

    def test_rm_from_all_and_refuse_empty(self):
        self.run_cli("pool", "rm", "slackware")
        self.assertEqual(sorted(self.saved()["logo_pool"]),
                         sorted(n for n in logos.LOGOS if n != "slackware"))
        self.run_cli("pool", "planet")
        rc, out = self.run_cli("pool", "rm", "planet")
        self.assertEqual(rc, 1)
        self.assertEqual(self.saved()["logo_pool"], ["planet"])

    def test_pool_of_everything_is_stored_as_empty(self):
        self.run_cli("pool", *logos.LOGOS)
        self.assertEqual(self.saved()["logo_pool"], [])

    def test_other_config_writes_keep_logo_keys(self):
        self.run_cli("arch")
        self.run_cli("pool", "arch", "planet")
        adconf.main(["set", "accent", "200"])
        cfg = self.saved()
        self.assertEqual((cfg["logo"], cfg["logo_pool"]), ("arch", ["arch", "planet"]))

    def test_bands_toggle_persists(self):
        self.assertEqual(self.run_cli("bands", "on")[0], 0)
        self.assertIs(self.saved()["logo_bands"], True)
        self.run_cli("bands", "off")
        self.assertIs(self.saved()["logo_bands"], False)
        self.assertEqual(self.run_cli("bands", "maybe")[0], 1)

    def test_list_and_gallery_print(self):
        self.assertEqual(self.run_cli()[0], 0)
        rc, out = self.run_cli("gallery")
        self.assertEqual(rc, 0)
        for name in logos.LOGOS:
            self.assertIn(name, out)


if __name__ == "__main__":
    unittest.main()
