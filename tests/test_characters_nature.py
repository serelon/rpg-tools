"""characters.py shows a minimal profile's `nature` (what someone is) on one line."""

import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "characters.py"
spec = importlib.util.spec_from_file_location("characters", SCRIPT)
characters = importlib.util.module_from_spec(spec)
spec.loader.exec_module(characters)


class NatureLine(unittest.TestCase):
    def test_dict_renders_in_order_and_skips_empty(self):
        char = {"name": "Ulf", "minimal": {"role": "Man-at-arms",
                "nature": {"kind": "ghoul", "clan": "", "bond": "Bound to Geirr"}}}
        out = characters.format_minimal(char)
        self.assertIn("**Nature:** kind: ghoul · bond: Bound to Geirr", out)

    def test_plain_string_passes_through(self):
        char = {"name": "X", "minimal": {"nature": "mortal"}}
        self.assertIn("**Nature:** mortal", characters.format_minimal(char))

    def test_absent_nature_adds_nothing(self):
        char = {"name": "X", "minimal": {"role": "r"}}
        self.assertNotIn("Nature", characters.format_minimal(char))


if __name__ == "__main__":
    unittest.main()
