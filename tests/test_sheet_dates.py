"""Tests for sheetlib.dates (spec S6)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))

from sheetlib import dates  # noqa: E402


class TestDateRegex(unittest.TestCase):
    def test_valid_forms(self):
        self.assertEqual(dates.parse("1130"), (1130, None, None))
        self.assertEqual(dates.parse("1130-10"), (1130, 10, None))
        self.assertEqual(dates.parse("1130-10-31"), (1130, 10, 31))

    def test_signed_and_zero_years(self):
        self.assertEqual(dates.parse("0"), (0, None, None))
        self.assertEqual(dates.parse("-500"), (-500, None, None))
        self.assertEqual(dates.parse("+2300-01"), (2300, 1, None))
        self.assertEqual(dates.parse("123456"), (123456, None, None))

    def test_invalid(self):
        for bad in ["", "1130-1", "1130-13", "1130-00", "1130-01-32", "1130-01-00",
                    "1234567", "~10th Thirdmonth", "1130/10", "1130-10-01T", None, 1130]:
            self.assertIsNone(dates.parse(bad), bad)
            self.assertFalse(dates.is_valid(bad))

    def test_no_trailing_newline_or_non_ascii_digits(self):
        for bad in ["1130\n", "1130-10\n", "١١٣١", "1130-١٠",
                    " 1130", "1130 "]:
            self.assertIsNone(dates.parse(bad), repr(bad))


class TestSortKey(unittest.TestCase):
    def test_vaguer_sorts_first(self):
        self.assertLess(dates.sort_key("1130"), dates.sort_key("1130-01"))
        self.assertLess(dates.sort_key("1130-01"), dates.sort_key("1130-01-01"))
        self.assertLess(dates.sort_key("1130-12-31"), dates.sort_key("1131"))

    def test_negative_years(self):
        self.assertLess(dates.sort_key("-500"), dates.sort_key("0"))
        self.assertLess(dates.sort_key("0"), dates.sort_key("1"))

    def test_at_end(self):
        self.assertEqual(dates.at_end("1130"), (1130, 12, 31))
        self.assertEqual(dates.at_end("1130-10"), (1130, 10, 31))
        self.assertEqual(dates.at_end("1130-10-05"), (1130, 10, 5))
        # span-inclusive: everything in 1130 is within --at 1130
        self.assertLessEqual(dates.sort_key("1130-12-31"), dates.at_end("1130"))
        self.assertGreater(dates.sort_key("1131"), dates.at_end("1130"))


class TestYears(unittest.TestCase):
    def test_years(self):
        self.assertEqual(dates.years("1140"), 1140)
        self.assertAlmostEqual(dates.years("1140-07"), 1140.5)
        self.assertAlmostEqual(dates.years("1140-01-32".replace("32", "31")), 1140 + 30 / 372)
        self.assertAlmostEqual(dates.years("1165") - dates.years("1140"), 25.0)

    def test_years_of_at_end(self):
        self.assertAlmostEqual(dates.years_of_key(dates.at_end("1130")), 1130 + 11 / 12 + 30 / 372)


if __name__ == "__main__":
    unittest.main()
