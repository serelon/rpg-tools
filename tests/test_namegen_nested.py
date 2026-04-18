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
    """Graceful degradation: missing source warns and skips, all-missing fails cleanly."""

    @classmethod
    def setUpClass(cls):
        fixtures_root = Path(__file__).parent / "fixtures-aggregates"
        namegen.discover_namesets(fixtures_root)

    def setUp(self):
        random.seed(42)

    def test_missing_source_does_not_crash(self):
        # broken-aggregate has one valid source (alpha-leaf) and one broken
        # All produced names should come from the valid source
        for _ in range(20):
            names = namegen.generate_from_aggregate("test:broken-aggregate", count=1)
            self.assertEqual(len(names), 1)
            self.assertIn("Aleph", names[0])

    def test_missing_source_warns_to_stderr(self):
        buf = io.StringIO()
        with redirect_stderr(buf):
            namegen.generate_from_aggregate("test:broken-aggregate", count=5)
        # At least some calls will pick the ghost source and warn
        self.assertIn("nonexistent-source", buf.getvalue())
        self.assertIn("not found", buf.getvalue())

    def test_all_sources_missing_returns_empty_or_handles_gracefully(self):
        # No source resolves; should not raise UnboundLocalError
        # Acceptable behavior: empty list, or list with empty strings, or warn and return [].
        # The test just checks: no crash.
        buf = io.StringIO()
        with redirect_stderr(buf):
            try:
                names = namegen.generate_from_aggregate("test:all-missing-aggregate", count=2)
            except UnboundLocalError:
                self.fail("generate_from_aggregate should handle all-missing sources without UnboundLocalError")
            # All-missing is a degenerate case; document whatever the result is
            # but assert it didn't crash.
        self.assertIn("not found", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
