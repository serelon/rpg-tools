"""pool.py weighted draws: profiles tilt odds, the pool stays shared and depletes."""

import json
import os
import random
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import pool  # noqa: E402


class WeightedDraw(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        (root / "pools").mkdir()
        (root / "pools" / "moral.json").write_text(json.dumps({
            "id": "moral",
            "tokens": [{"token": "Dark", "count": 50}, {"token": "Decent", "count": 50}, "Joker"],
            "settings": {"draw_mode": "pop_top"},
            "weights": {"young": {"Dark": 0, "Decent": 1}},
        }))
        self.cwd = os.getcwd()
        os.chdir(root)
        self.old_state = pool.STATE_DIR
        pool.STATE_DIR = root / "state"
        pool.cmd_create("moral")

    def tearDown(self):
        pool.STATE_DIR = self.old_state
        os.chdir(self.cwd)
        self.tmp.cleanup()

    def test_weight_zero_never_drawn_and_pool_depletes(self):
        random.seed(1)
        pool.cmd_draw("moral", 40, profile="young")
        left = pool.load_state("moral")["tokens"]
        self.assertEqual(len(left), 101 - 40)
        self.assertEqual(left.count("Dark"), 50)          # weight 0: untouched
        self.assertEqual(left.count("Decent") + left.count("Joker"), 11)

    def test_unlisted_token_weighs_one(self):
        self.assertEqual(pool.weighted_index(["Joker"], {"Dark": 0}), 0)
        self.assertIsNone(pool.weighted_index(["Dark"], {"Dark": 0}))

    def test_unknown_profile_exits(self):
        with self.assertRaises(SystemExit):
            pool.cmd_draw("moral", 1, profile="nope")


if __name__ == "__main__":
    unittest.main()
