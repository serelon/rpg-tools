"""Tests for namespace-aware nameset loading and reference resolution."""
import unittest
from pathlib import Path

import namegen


class TestNamespaceLoading(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures_root = Path(__file__).parent / "fixtures-namespaces"
        namegen.discover_namesets(fixtures_root)

    def test_unqualified_nameset_lands_in_root_namespace(self):
        # simple-test was created without a namespace field -> root
        self.assertIn(":simple-test", namegen.custom_namesets)

    def test_namespaced_nameset_loads_with_qualified_key(self):
        self.assertIn("metropolitan:english", namegen.custom_namesets)

    def test_multi_nameset_file_explodes(self):
        # multi-test.json declares namespace "test" with 3 namesets inside
        self.assertIn("test:alpha", namegen.custom_namesets)
        self.assertIn("test:beta", namegen.custom_namesets)
        # third entry overrides namespace to "override"
        self.assertNotIn("test:gamma-override", namegen.custom_namesets)
        self.assertIn("override:gamma-override", namegen.custom_namesets)


class TestReferenceResolution(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures_root = Path(__file__).parent / "fixtures-namespaces"
        namegen.discover_namesets(fixtures_root)

    def test_qualified_reference_resolves(self):
        result = namegen.resolve_nameset_ref("metropolitan:english", current_namespace="other")
        self.assertEqual(result, "metropolitan:english")

    def test_bare_reference_resolves_in_current_namespace_first(self):
        # "english" exists in metropolitan; from current_namespace=metropolitan it should resolve there
        result = namegen.resolve_nameset_ref("english", current_namespace="metropolitan")
        self.assertEqual(result, "metropolitan:english")

    def test_bare_reference_falls_back_to_root(self):
        # "simple-test" only exists in root; resolution from any namespace should find it
        result = namegen.resolve_nameset_ref("simple-test", current_namespace="metropolitan")
        self.assertEqual(result, ":simple-test")

    def test_unresolvable_reference_returns_none(self):
        result = namegen.resolve_nameset_ref("nonexistent", current_namespace="metropolitan")
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
