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

    def test_grouped_nameset_format_validates_against_implicit_categories(self):
        # grouped-test uses nameGroups; format references {firstName} {lastName}
        # which are the implicit categories. Should produce no "undefined category" warnings
        # for that nameset.
        fixtures_root = Path(__file__).parent / "fixtures"
        namegen.discover_namesets(fixtures_root)
        out_buf = io.StringIO()
        with redirect_stdout(out_buf):
            errors, warnings = namegen.validate_all()
        grouped_warnings = [w for w in warnings if ":grouped-test" in w and "undefined category" in w]
        self.assertEqual(grouped_warnings, [],
                         f"Grouped nameset shouldn't have undefined-category warnings: {grouped_warnings}")

    def test_grouped_nameset_with_bad_format_placeholder_warns(self):
        # If a grouped nameset's format references something other than firstName/lastName,
        # the validator should warn.
        fixtures_root = Path(__file__).parent / "fixtures-validate-grouped"
        namegen.discover_namesets(fixtures_root)
        out_buf = io.StringIO()
        with redirect_stdout(out_buf):
            errors, warnings = namegen.validate_all()
        bad_warnings = [w for w in warnings if "epithet" in w]
        self.assertTrue(bad_warnings,
                        f"Expected warning about undefined 'epithet' in grouped nameset: {warnings}")

    def test_empty_aggregate_sources_error(self):
        fixtures_root = Path(__file__).parent / "fixtures-validate-empty"
        namegen.discover_namesets(fixtures_root)
        out_buf = io.StringIO()
        with redirect_stdout(out_buf):
            errors, warnings = namegen.validate_all()
        self.assertTrue(any("empty-aggregate" in e and "no sources" in e for e in errors),
                        f"Expected empty-sources error: {errors}")

    def test_empty_nameGroups_error(self):
        fixtures_root = Path(__file__).parent / "fixtures-validate-empty"
        namegen.discover_namesets(fixtures_root)
        out_buf = io.StringIO()
        with redirect_stdout(out_buf):
            errors, warnings = namegen.validate_all()
        self.assertTrue(any("empty-grouped" in e and "empty nameGroups" in e for e in errors),
                        f"Expected empty-nameGroups error: {errors}")

    def test_no_categories_error(self):
        fixtures_root = Path(__file__).parent / "fixtures-validate-empty"
        namegen.discover_namesets(fixtures_root)
        out_buf = io.StringIO()
        with redirect_stdout(out_buf):
            errors, warnings = namegen.validate_all()
        self.assertTrue(any("empty-simple" in e and "no nameCategories" in e for e in errors),
                        f"Expected no-nameCategories error: {errors}")

    def test_namespace_typo_warning(self):
        fixtures_root = Path(__file__).parent / "fixtures-validate-typo"
        namegen.discover_namesets(fixtures_root)
        out_buf = io.StringIO()
        with redirect_stdout(out_buf):
            errors, warnings = namegen.validate_all()
        typo_warnings = [w for w in warnings if "look similar" in w]
        self.assertTrue(typo_warnings,
                        f"Expected namespace typo warning: {warnings}")
        self.assertTrue(
            any("metropolitan" in w and "metropoliton" in w for w in typo_warnings),
            f"Expected pair mentioning metropolitan/metropoliton: {typo_warnings}",
        )


if __name__ == "__main__":
    unittest.main()
