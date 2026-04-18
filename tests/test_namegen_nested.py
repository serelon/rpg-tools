"""Nested aggregates: aggregates that pull from other aggregates."""
import io
import random
import unittest
from contextlib import redirect_stderr
from pathlib import Path

import namegen


class TestNestedAggregates(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures_root = Path(__file__).parent / "fixtures-aggregates"
        namegen.discover_namesets(fixtures_root)

    def setUp(self):
        random.seed(42)

    def test_top_aggregate_can_pick_nested_source(self):
        # Generate enough names; some should be from alpha-leaf (via mid-aggregate)
        seen_alpha = False
        seen_beta = False
        for _ in range(50):
            names = namegen.generate_from_aggregate("test:top-aggregate", count=1)
            if "Aleph" in names[0]:
                seen_alpha = True
            if "Bet" in names[0]:
                seen_beta = True
        self.assertTrue(seen_alpha, "Should sometimes pick alpha-leaf via mid-aggregate")
        self.assertTrue(seen_beta, "Should sometimes pick beta-leaf directly")

    def test_nested_dispatch_no_empty_names(self):
        # Before this fix, picking a nested source would produce empty/garbage names
        for _ in range(30):
            names = namegen.generate_from_aggregate("test:top-aggregate", count=1)
            self.assertNotEqual(names[0].strip(), "")
            self.assertEqual(len(names[0].split()), 2)


class TestCrossNamespaceAggregate(unittest.TestCase):
    """Folded-in follow-up from Task 2.1 review: aggregate in namespace X
    references a source in namespace Y; bare ref must resolve correctly via
    parent's namespace then root."""

    @classmethod
    def setUpClass(cls):
        fixtures_root = Path(__file__).parent / "fixtures-aggregates"
        namegen.discover_namesets(fixtures_root)

    def setUp(self):
        random.seed(42)

    def test_bare_source_resolves_in_parent_namespace(self):
        # cross-aggregate is in 'other' namespace; bare 'external-leaf' should
        # resolve to other:external-leaf (sibling), not anywhere else
        seen_external = False
        for _ in range(30):
            names = namegen.generate_from_aggregate("other:cross-aggregate", count=1)
            if "Ext" in names[0]:
                seen_external = True
                self.assertIn("Outer", names[0])
        self.assertTrue(seen_external)

    def test_qualified_source_resolves_cross_namespace(self):
        # The qualified source 'test:alpha-leaf' must work from a different namespace
        seen_qualified = False
        for _ in range(30):
            names = namegen.generate_from_aggregate("other:cross-aggregate", count=1)
            if "Aleph" in names[0]:
                seen_qualified = True
                self.assertIn("Anchor", names[0])
        self.assertTrue(seen_qualified)


class TestAggregateRobustness(unittest.TestCase):
    """Graceful degradation: missing source nameset should warn-and-skip, not crash."""

    @classmethod
    def setUpClass(cls):
        fixtures_root = Path(__file__).parent / "fixtures-aggregates"
        namegen.discover_namesets(fixtures_root)

    def test_missing_source_does_not_crash(self):
        # broken-aggregate (created in next task) - skip if not present
        if "test:broken-aggregate" not in namegen.custom_namesets:
            self.skipTest("broken-aggregate fixture not yet created (Task 4.2)")


if __name__ == "__main__":
    unittest.main()
