"""Slot policies: inherit / independent / mix / forced."""
import random
import unittest
from pathlib import Path

import namegen


JA_FIRST = {"Hiroshi", "Yuki"}
JA_LAST = {"Yamamoto", "Tanaka"}
DE_FIRST = {"Hans", "Greta"}
DE_LAST = {"Mueller", "Schmidt"}


class TestSlotPolicies(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures_root = Path(__file__).parent / "fixtures-aggregates"
        namegen.discover_namesets(fixtures_root)

    def setUp(self):
        random.seed(42)

    def test_independent_produces_cross_mix(self):
        # fully-mixed should produce names with first and last from different sources sometimes
        cross_mix_seen = False
        for _ in range(100):
            names = namegen.generate_from_aggregate("test:fully-mixed", count=1)
            parts = names[0].split()
            if len(parts) != 2:
                continue
            first, last = parts
            if (first in JA_FIRST and last in DE_LAST) or (first in DE_FIRST and last in JA_LAST):
                cross_mix_seen = True
                break
        self.assertTrue(cross_mix_seen, "independent policy should produce cross-mix names")

    def test_mix_rate_produces_some_inherit_some_independent(self):
        # diaspora-test with mix rate 0.5 should produce a mix
        cross_mix_count = 0
        coherent_count = 0
        for _ in range(200):
            names = namegen.generate_from_aggregate("test:diaspora-test", count=1)
            parts = names[0].split()
            if len(parts) != 2:
                continue
            first, last = parts
            first_ja = first in JA_FIRST
            last_de = last in DE_LAST
            first_de = first in DE_FIRST
            last_ja = last in JA_LAST
            if (first_ja and last_de) or (first_de and last_ja):
                cross_mix_count += 1
            elif (first_ja and last_ja) or (first_de and last_de):
                coherent_count += 1
        # Both should appear; with rate 0.5 each should be substantial
        self.assertGreater(cross_mix_count, 30, f"expected some cross-mix, got {cross_mix_count}")
        self.assertGreater(coherent_count, 30, f"expected some coherent, got {coherent_count}")

    def test_forced_pins_slot_to_named_source(self):
        # forced-last should always have a Japanese last name regardless of first
        for _ in range(50):
            names = namegen.generate_from_aggregate("test:forced-last", count=1)
            parts = names[0].split()
            if len(parts) != 2:
                continue
            first, last = parts
            self.assertIn(last, JA_LAST, f"forced lastName should always be from japanese-test, got {last}")


if __name__ == "__main__":
    unittest.main()
