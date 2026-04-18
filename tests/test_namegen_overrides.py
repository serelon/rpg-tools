"""Per-source overrides on aggregate sources."""
import random
import unittest
from pathlib import Path

import namegen


class TestPerSourceOverrides(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures_root = Path(__file__).parent / "fixtures-aggregates"
        namegen.discover_namesets(fixtures_root)

    def setUp(self):
        random.seed(42)

    def test_override_gender_weights(self):
        # override-test forces male-only via per-source override
        for _ in range(30):
            names = namegen.generate_from_aggregate("test:override-test", count=1)
            first = names[0].split()[0]
            self.assertEqual(first, "Hiroshi")  # only male in japanese-test


if __name__ == "__main__":
    unittest.main()
