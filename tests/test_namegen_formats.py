"""Named format variants."""
import unittest
from pathlib import Path

import namegen


class TestFormatVariants(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures_root = Path(__file__).parent / "fixtures-formats"
        namegen.discover_namesets(fixtures_root)

    def test_default_format(self):
        names = namegen.generate_from_nameset("multi-format", count=1)
        self.assertEqual(names[0], "Valentina Celestine")

    def test_named_format_formal(self):
        names = namegen.generate_from_nameset("multi-format", count=1, format_name="formal")
        self.assertEqual(names[0], "Princess Valentina Celestine")

    def test_named_format_naval(self):
        names = namegen.generate_from_nameset("multi-format", count=1, format_name="naval")
        self.assertEqual(names[0], "Cadet Celestine")

    def test_optional_section_with_literal_drops_whole_when_unresolved(self):
        # An empty category inside "[ af {station}]" must drop the particle too,
        # not leak "Regina af".
        names = namegen.generate_from_nameset("optional-particle", count=1, format_name="station")
        self.assertEqual(names[0], "Regina")
        names = namegen.generate_from_nameset("optional-particle", count=1, format_name="inscription")
        self.assertEqual(names[0], "Regina Awad")

    def test_unknown_format_warns_and_uses_default(self):
        # Should not crash
        names = namegen.generate_from_nameset("multi-format", count=1, format_name="nonexistent")
        self.assertEqual(names[0], "Valentina Celestine")


if __name__ == "__main__":
    unittest.main()
