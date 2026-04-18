"""Tests for list/filter CLI behavior."""
import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import namegen


class TestListNamespaceFilter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures_root = Path(__file__).parent / "fixtures-namespaces"
        namegen.discover_namesets(fixtures_root)

    def test_list_filters_by_namespace(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            namegen.list_namesets(namespace_filter="metropolitan")
        out = buf.getvalue()
        self.assertIn("english", out)
        self.assertNotIn("simple-test", out)
        self.assertNotIn("alpha", out)

    def test_list_no_filter_shows_all(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            namegen.list_namesets()
        out = buf.getvalue()
        self.assertIn("english", out)
        self.assertIn("simple-test", out)
        self.assertIn("alpha", out)


if __name__ == "__main__":
    unittest.main()
