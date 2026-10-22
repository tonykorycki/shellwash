#!/usr/bin/env python3
"""
Tests for linux/logos.py: every logo's grid shape, the per-launch choice,
and the `bedazzle logo` CLI against a throwaway config file.

    python3 -m unittest discover tests -v
"""

import contextlib
import io
import json
import os
import random
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "linux"))
import adconf  # noqa: E402
import logos  # noqa: E402


class Grids(unittest.TestCase):
    def test_every_logo_is_a_full_grid_of_rgb_or_none(self):
        for name, (fn, _) in logos.LOGOS.items():
            for hue in (0.0, 140.0, 215.0, 330.0, 359.9):
                grid = fn(hue)
                self.assertEqual(len(grid), logos.H, name)
                drawn = 0
                for row in grid:
                    self.assertEqual(len(row), logos.W, name)
                    for px in row:
                        if px is None:
                            continue
                        drawn += 1
                        self.assertEqual(len(px), 3, name)
                        self.assertTrue(all(isinstance(c, int) and 0 <= c <= 255 for c in px), name)
                self.assertGreater(drawn, logos.W * logos.H // 5, f"{name} is nearly empty")

    def test_render_packs_two_pixel_rows_per_line(self):
        self.assertEqual(len(logos.lines("planet", 215.0)), (logos.H + 1) // 2)


class Choose(unittest.TestCase):
    def test_fixed_choice(self):
        self.assertEqual(logos.choose({"logo": "torus"}), "torus")

    def test_unknown_name_falls_back(self):
        self.assertEqual(logos.choose({"logo": "nope"}), logos.DEFAULT)

    def test_random_rolls_only_from_the_pool(self):
        cfg = {"logo": "random", "logo_pool": ["scope", "torus", "gone"]}
        rolls = {logos.choose(cfg, random.Random(i)) for i in range(60)}
        self.assertEqual(rolls, {"scope", "torus"})

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
        self.assertEqual(self.run_cli("scope")[0], 0)
        self.assertEqual(self.saved()["logo"], "scope")
        self.run_cli("random")
        self.assertEqual(self.saved()["logo"], "random")

    def test_unknown_name_is_rejected_unchanged(self):
        rc, out = self.run_cli("nope")
        self.assertEqual(rc, 1)
        self.assertIn("unknown logo", out)
        self.assertNotIn("logo", self.saved())

    def test_pool_set_add_rm_all(self):
        self.run_cli("pool", "torus", "scope")
        self.assertEqual(self.saved()["logo_pool"], ["torus", "scope"])
        self.run_cli("pool", "add", "planet", "torus")
        self.assertEqual(self.saved()["logo_pool"], ["torus", "scope", "planet"])
        self.run_cli("pool", "rm", "scope")
        self.assertEqual(self.saved()["logo_pool"], ["torus", "planet"])
        self.run_cli("pool", "all")
        self.assertEqual(self.saved()["logo_pool"], [])

    def test_rm_from_all_and_refuse_empty(self):
        self.run_cli("pool", "rm", "mushroom")
        self.assertEqual(sorted(self.saved()["logo_pool"]),
                         sorted(n for n in logos.LOGOS if n != "mushroom"))
        self.run_cli("pool", "planet")
        rc, out = self.run_cli("pool", "rm", "planet")
        self.assertEqual(rc, 1)
        self.assertEqual(self.saved()["logo_pool"], ["planet"])

    def test_pool_of_everything_is_stored_as_empty(self):
        self.run_cli("pool", *logos.LOGOS)
        self.assertEqual(self.saved()["logo_pool"], [])

    def test_other_config_writes_keep_logo_keys(self):
        self.run_cli("torus")
        self.run_cli("pool", "torus", "planet")
        adconf.main(["set", "accent", "200"])
        cfg = self.saved()
        self.assertEqual((cfg["logo"], cfg["logo_pool"]), ("torus", ["torus", "planet"]))

    def test_list_and_gallery_print(self):
        self.assertEqual(self.run_cli()[0], 0)
        rc, out = self.run_cli("gallery")
        self.assertEqual(rc, 0)
        for name in logos.LOGOS:
            self.assertIn(name, out)


if __name__ == "__main__":
    unittest.main()
