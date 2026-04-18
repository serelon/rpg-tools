"""Regression baseline: lock current namegen behavior before refactoring."""
import random
import unittest
from pathlib import Path

import namegen


class NamegenBaseline(unittest.TestCase):
    """Verify current behavior continues to work after every change."""

    @classmethod
    def setUpClass(cls):
        # Load fixtures
        fixtures_root = Path(__file__).parent / "fixtures"
        namegen.discover_namesets(fixtures_root)

    def setUp(self):
        random.seed(42)  # Deterministic generation

    def test_simple_nameset_loads(self):
        self.assertIn(":simple-test", namegen.custom_namesets)

    def test_aggregate_nameset_loads(self):
        self.assertIn(":aggregate-test", namegen.custom_namesets)
        self.assertEqual(
            namegen.custom_namesets[":aggregate-test"].get("type"), "aggregate"
        )

    def test_grouped_nameset_loads(self):
        self.assertIn(":grouped-test", namegen.custom_namesets)
        self.assertIn("nameGroups", namegen.custom_namesets[":grouped-test"])

    def test_simple_generation_produces_two_words(self):
        names = namegen.generate_from_nameset("simple-test", count=1)
        self.assertEqual(len(names), 1)
        self.assertEqual(len(names[0].split()), 2)

    def test_simple_generation_count(self):
        names = namegen.generate_from_nameset("simple-test", count=5)
        self.assertEqual(len(names), 5)

    def test_simple_gender_filter_female(self):
        for _ in range(20):
            names = namegen.generate_from_nameset("simple-test", count=1, gender="female")
            first = names[0].split()[0]
            self.assertIn(first, ("Alice", "Sam"))

    def test_simple_gender_filter_male(self):
        for _ in range(20):
            names = namegen.generate_from_nameset("simple-test", count=1, gender="male")
            first = names[0].split()[0]
            self.assertIn(first, ("Bob", "Sam"))

    def test_aggregate_generation(self):
        names = namegen.generate_from_aggregate("aggregate-test", count=3)
        self.assertEqual(len(names), 3)

    def test_grouped_generation(self):
        names = namegen.generate_from_nameset_with_groups("grouped-test", count=3)
        self.assertEqual(len(names), 3)

    def test_grouped_force_group(self):
        names = namegen.generate_from_nameset_with_groups("grouped-test", count=5, group="alpha")
        for n in names:
            self.assertEqual(n.split()[0], "Anna")

    def test_format_string_simple(self):
        cats = {
            "firstName": [{"name": "X"}],
            "lastName": [{"name": "Y"}],
        }
        result = namegen.build_name_from_format("{firstName} {lastName}", cats)
        self.assertEqual(result, "X Y")

    def test_format_string_optional_section(self):
        cats = {"firstName": [{"name": "X"}]}
        # Optional with no available content collapses
        result = namegen.build_name_from_format("{firstName}[ {missing}]", cats)
        self.assertEqual(result, "X")

    def test_random_pattern(self):
        result = namegen.generate_pattern("AAA")
        self.assertEqual(len(result), 3)
        self.assertTrue(result.isupper())
        self.assertTrue(result.isalpha())

    def test_random_range(self):
        result = namegen.generate_range(1, 10)
        self.assertTrue(1 <= int(result) <= 10)


if __name__ == "__main__":
    unittest.main()
