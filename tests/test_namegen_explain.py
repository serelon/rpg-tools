"""--explain flag dumps assembly trace."""
import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import namegen


class TestExplain(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures_root = Path(__file__).parent / "fixtures-aggregates"
        namegen.discover_namesets(fixtures_root)

    def test_explain_aggregate_shows_source_pick(self):
        # Generate from diaspora-test (slot-aware aggregate) with explain on
        # The trace should mention the source pick
        buf = io.StringIO()
        with redirect_stderr(buf):
            namegen.generate_from_aggregate("test:diaspora-test", count=1, explain=True)
        out = buf.getvalue().lower()
        self.assertIn("source", out)

    def test_explain_simple_nameset(self):
        # Generate from a leaf nameset with explain on
        # Should mention the format used
        buf = io.StringIO()
        with redirect_stderr(buf):
            namegen.generate_from_nameset("test:alpha-leaf", count=1, explain=True)
        out = buf.getvalue().lower()
        # At minimum: should mention the nameset name or format
        self.assertTrue(
            "format" in out or "alpha-leaf" in out or "nameset" in out,
            f"Expected explain output, got: {out!r}"
        )


if __name__ == "__main__":
    unittest.main()
