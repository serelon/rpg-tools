"""Variable-depth chain syntax {...}*N-M."""
import random
import unittest

import namegen


class TestChainParsing(unittest.TestCase):
    def test_chain_parses_to_repeat_token(self):
        # "{X}{ Y}*0-3" -> placeholder X, repeat group with min=0, max=3
        tokens = namegen.parse_format("{firstName}{ tessek}*0-3")
        self.assertEqual(tokens[0]["type"], "placeholder")
        self.assertEqual(tokens[1]["type"], "repeat")
        self.assertEqual(tokens[1]["min"], 0)
        self.assertEqual(tokens[1]["max"], 3)

    def test_chain_with_nested_placeholder_parses(self):
        # Inner content has a placeholder
        tokens = namegen.parse_format("{firstName}{, {firstName} tessek}*1-3")
        self.assertEqual(tokens[1]["type"], "repeat")
        self.assertEqual(tokens[1]["min"], 1)
        self.assertEqual(tokens[1]["max"], 3)
        # The repeat group's inner content should parse as 3 sub-tokens: literal ", ", placeholder firstName, literal " tessek"
        inner = tokens[1]["content"]
        self.assertGreaterEqual(len(inner), 2)


class TestChainBuilding(unittest.TestCase):
    def setUp(self):
        random.seed(42)

    def test_chain_repeats_within_bounds(self):
        # Inner content is " tessek"; the chain repeats it 0-3 times
        # When repeated 0 times, no "tessek" in result
        # When repeated 3 times, "tessek tessek tessek" in result
        cats = {
            "firstName": [{"name": "X"}],
        }
        for _ in range(20):
            result = namegen.build_name_from_format("{firstName}{ tessek}*0-3", cats)
            count = result.count("tessek")
            self.assertTrue(0 <= count <= 3, f"Got {count} tesseks in: {result}")

    def test_chain_with_inner_placeholder(self):
        cats = {
            "firstName": [{"name": "X"}],
        }
        # Should produce: "X" + (0 to 2 repeats of " mom-X")
        for _ in range(20):
            result = namegen.build_name_from_format("{firstName}{ mom-{firstName}}*0-2", cats)
            mom_count = result.count("mom-")
            self.assertTrue(0 <= mom_count <= 2)


if __name__ == "__main__":
    unittest.main()
