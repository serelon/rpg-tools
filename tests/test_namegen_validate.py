"""Validate command for nameset linting."""
import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import namegen


class TestValidate(unittest.TestCase):
    def test_broken_aggregate_ref_reported(self):
        # fixtures-aggregates has test:broken-aggregate referencing nonexistent-source
        fixtures_root = Path(__file__).parent / "fixtures-aggregates"
        namegen.discover_namesets(fixtures_root)
        out_buf = io.StringIO()
        with redirect_stdout(out_buf):
            errors, warnings = namegen.validate_all()
        self.assertTrue(any("nonexistent-source" in e for e in errors),
                        f"Expected 'nonexistent-source' in errors: {errors}")

    def test_legacy_format_field_warns(self):
        # The simple-test fixture uses legacy "format" field
        fixtures_root = Path(__file__).parent / "fixtures"
        namegen.discover_namesets(fixtures_root)
        out_buf = io.StringIO()
        with redirect_stdout(out_buf):
            errors, warnings = namegen.validate_all()
        self.assertTrue(any("legacy" in w.lower() or "format" in w.lower() for w in warnings),
                        f"Expected legacy format warning: {warnings}")

    def test_validate_returns_tuple(self):
        fixtures_root = Path(__file__).parent / "fixtures"
        namegen.discover_namesets(fixtures_root)
        out_buf = io.StringIO()
        with redirect_stdout(out_buf):
            result = namegen.validate_all()
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)


if __name__ == "__main__":
    unittest.main()
