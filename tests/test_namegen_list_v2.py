"""Briefer list output, grouped by namespace, with filters."""
import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import namegen


class TestListV2(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Use the namespaces fixture set which has:
        # - root (":simple-test")
        # - "metropolitan" namespace ("metropolitan:english")
        # - "test" namespace ("test:alpha", "test:beta", "override:gamma-override", "test:delta-hidden")
        fixtures_root = Path(__file__).parent / "fixtures-namespaces"
        namegen.discover_namesets(fixtures_root)

    def test_list_groups_by_namespace(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            namegen.list_namesets()
        out = buf.getvalue()
        # Should have "metropolitan" and "test" group headers
        self.assertIn("metropolitan", out)
        self.assertIn("test", out)

    def test_list_brief_no_per_nameset_detail(self):
        # Brief should NOT include the verbose Setting:/Description: lines
        buf = io.StringIO()
        with redirect_stdout(buf):
            namegen.list_namesets()
        self.assertNotIn("Description:", buf.getvalue())
        self.assertNotIn("Setting:", buf.getvalue())

    def test_list_verbose_includes_detail(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            namegen.list_namesets(verbose=True)
        out = buf.getvalue()
        # verbose should show more detail. At least one of these markers should appear:
        # (any nameset with a name, description, type, or sources will produce verbose output)
        # Just verify the output is significantly longer
        buf2 = io.StringIO()
        with redirect_stdout(buf2):
            namegen.list_namesets(verbose=False)
        self.assertGreater(len(out), len(buf2.getvalue()))

    def test_hidden_count_displayed_when_hidden_present(self):
        # In fixtures-namespaces, "test" namespace has delta-hidden
        buf = io.StringIO()
        with redirect_stdout(buf):
            namegen.list_namesets()
        out = buf.getvalue()
        # The "test" namespace header should mention hidden count
        # Look for pattern like "test (3 visible, 1 hidden)" or similar
        self.assertIn("hidden", out.lower())

    def test_filter_by_setting(self):
        # No fixtures have a setting field that we know of, so this just verifies no crash
        buf = io.StringIO()
        with redirect_stdout(buf):
            namegen.list_namesets(setting_filter="Nonexistent Campaign")
        # Output should be empty or just the header (no namesets match)
        # Just verify no crash
        out = buf.getvalue()
        self.assertNotIn("english", out)  # metropolitan:english has no setting field

    def test_filter_by_type_aggregate(self):
        # Most fixtures don't have type=aggregate; this verifies filter doesn't crash and excludes non-aggregates
        buf = io.StringIO()
        with redirect_stdout(buf):
            namegen.list_namesets(type_filter="aggregate")
        out = buf.getvalue()
        # The simple-test, alpha, beta etc. should NOT appear
        self.assertNotIn("simple-test", out)
        self.assertNotIn("alpha", out)


if __name__ == "__main__":
    unittest.main()
