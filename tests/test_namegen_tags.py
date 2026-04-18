"""Per-entry tag filtering."""
import random
import unittest
from pathlib import Path

import namegen


class TestPerEntryTags(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures_root = Path(__file__).parent / "fixtures-tags"
        namegen.discover_namesets(fixtures_root)

    def setUp(self):
        random.seed(42)

    def test_filter_single_tag(self):
        for _ in range(30):
            names = namegen.generate_from_nameset("tagged-test", count=1, tag_filter=["patrician"])
            first, last = names[0].split()
            self.assertIn(first, ("Marcus", "Lucia"))
            self.assertEqual(last, "Aurelius")

    def test_filter_no_match_falls_back(self):
        # No entries tagged 'nonexistent' - should not crash, should warn and use unfiltered
        names = namegen.generate_from_nameset("tagged-test", count=1, tag_filter=["nonexistent"])
        self.assertEqual(len(names), 1)

    def test_filter_multi_tag_AND(self):
        for _ in range(30):
            names = namegen.generate_from_nameset("tagged-test", count=1, tag_filter=["patrician", "imperial"])
            first = names[0].split()[0]
            self.assertEqual(first, "Marcus")

    def test_no_filter_uses_all(self):
        seen = set()
        for _ in range(50):
            names = namegen.generate_from_nameset("tagged-test", count=1)
            seen.add(names[0].split()[0])
        # Likely to have seen multiple entries
        self.assertGreater(len(seen), 1)


if __name__ == "__main__":
    unittest.main()
