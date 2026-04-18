"""Circular extends detection."""
import io
import unittest
from contextlib import redirect_stderr
from pathlib import Path

import namegen


class TestCircularExtends(unittest.TestCase):
    def test_circular_extends_detected(self):
        # Re-discover with a separate fixture set containing a cycle
        fixtures_root = Path(__file__).parent / "fixtures-extends-cycle"
        buf = io.StringIO()
        with redirect_stderr(buf):
            namegen.discover_namesets(fixtures_root)
        # The error message should mention circular extends
        self.assertIn("Circular extends detected", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
