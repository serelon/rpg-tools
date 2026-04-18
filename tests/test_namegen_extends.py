"""Inheritance via extends."""
import random
import unittest
from pathlib import Path

import namegen


class TestExtends(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures_root = Path(__file__).parent / "fixtures-extends"
        namegen.discover_namesets(fixtures_root)

    def test_child_inherits_parent_categories(self):
        child = namegen.custom_namesets["test:child"]
        first_names = [e["name"] for e in child["nameCategories"]["firstName"]]
        self.assertIn("Alpha", first_names)  # inherited
        self.assertIn("Beta", first_names)   # inherited
        self.assertIn("Gamma", first_names)  # added
        self.assertNotIn("ToRemove", first_names)  # removed

    def test_child_inherits_parent_lastnames(self):
        child = namegen.custom_namesets["test:child"]
        last_names = [e["name"] for e in child["nameCategories"]["lastName"]]
        self.assertIn("Original", last_names)

    def test_child_overrides_design(self):
        child = namegen.custom_namesets["test:child"]
        self.assertEqual(child["design"]["convention"], "Child convention")

    def test_child_inherits_tags_when_not_overridden(self):
        child = namegen.custom_namesets["test:child"]
        # child doesn't declare tags; should inherit parent's
        self.assertIn("base", child.get("tags", []))

    def test_grandchild_inherits_through_chain(self):
        grand = namegen.custom_namesets["test:grandchild"]
        first_names = [e["name"] for e in grand["nameCategories"]["firstName"]]
        self.assertIn("Alpha", first_names)
        self.assertIn("Gamma", first_names)
        self.assertNotIn("ToRemove", first_names)
        # grandchild overrides tags
        self.assertEqual(grand["tags"], ["specialized"])

    def test_child_can_be_generated_from(self):
        random.seed(42)
        names = namegen.generate_from_nameset("test:child", count=5)
        self.assertEqual(len(names), 5)


if __name__ == "__main__":
    unittest.main()
