"""Hidden flag behavior in list."""
import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import namegen


class TestHiddenFlag(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures_root = Path(__file__).parent / "fixtures-namespaces"
        namegen.discover_namesets(fixtures_root)

    def test_hidden_excluded_by_default(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            namegen.list_namesets()
        self.assertNotIn("delta-hidden", buf.getvalue())

    def test_hidden_shown_with_all_flag(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            namegen.list_namesets(show_hidden=True)
        self.assertIn("delta-hidden", buf.getvalue())

    def test_hidden_can_still_be_referenced_directly(self):
        # Even when not in list, generate should work
        names = namegen.generate_from_nameset("test:delta-hidden", count=1)
        self.assertEqual(len(names), 1)


if __name__ == "__main__":
    unittest.main()
