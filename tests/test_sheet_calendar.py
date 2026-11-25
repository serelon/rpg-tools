"""Calendar day arithmetic and the wave-2 builtins (today, day, all, any, has,
span_open, select). Synthetic data only."""
import datetime
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))

from sheetlib.calendar import Calendar, GREGORIAN  # noqa: E402
from sheetlib.expr import DictEnv, Evaluator, ExprError, SheetError, compile_expr  # noqa: E402
from sheet_helpers import SheetDir, codes, ev  # noqa: E402


class TestGregorian(unittest.TestCase):
    def test_matches_datetime(self):
        for d in ("1970-01-01", "2000-02-29", "1130-10-31", "0001-01-01", "2389-12-31"):
            y, m, dd = map(int, d.split("-"))
            ref = (datetime.date(y, m, dd) - datetime.date(1970, 1, 1)).days
            self.assertEqual(GREGORIAN.day(d), ref, d)
            self.assertEqual(GREGORIAN.date(ref), d)

    def test_signed_years_and_year_zero(self):
        n = GREGORIAN.day("0000-03-01")
        self.assertEqual(GREGORIAN.day("-0001-12-31") + 61, n)  # year 0 is a leap year
        self.assertEqual(GREGORIAN.date(GREGORIAN.day("-500-06-15")), "-0500-06-15")

    def test_partial_dates_and_end(self):
        self.assertEqual(GREGORIAN.day("1130"), GREGORIAN.day("1130-01-01"))
        self.assertEqual(GREGORIAN.day("1130", end=True), GREGORIAN.day("1130-12-31"))
        self.assertEqual(GREGORIAN.day("1131-02", end=True), GREGORIAN.day("1131-02-28"))
        self.assertTrue(GREGORIAN.bad_day("1131-02-30"))
        self.assertEqual(GREGORIAN.day("1131-02-30"), GREGORIAN.day("1131-02-28"))

    def test_years(self):
        self.assertAlmostEqual(GREGORIAN.years(GREGORIAN.day("2001") - GREGORIAN.day("2000")),
                               366 / 365.2425)


class TestCustom(unittest.TestCase):
    SPEC = {"months": [{"name": "M%d" % i, "days": 30} for i in range(1, 13)],
            "epoch": "0005-01-01", "format": "{month} {d}, {y} (E+{epoch_days})"}

    def test_lengths_and_roundtrip(self):
        c = Calendar(self.SPEC)
        self.assertEqual(c.year_len, 360)
        self.assertEqual(c.day("0001-02-01") - c.day("0001-01-01"), 30)
        for n in (0, 359, 360, 1799, -1):
            self.assertEqual(c.day(c.date(n)), n)
        self.assertTrue(c.bad_day("0003-02-31"))

    def test_display(self):
        c = Calendar(self.SPEC)
        self.assertEqual(c.display(c.day("0005-03-02")), "M3 2, 5 (E+61)")

    def test_bad_specs(self):
        for bad in ({"months": []}, {"months": [{"days": 0}] * 12}, {"epoch": "soon"},
                    {"format": 3}, "nope"):
            with self.assertRaises(SheetError):
                Calendar(bad)


def evx(src, names=None):
    return Evaluator(DictEnv(names or {})).evaluate(compile_expr(src))


class TestPureBuiltins(unittest.TestCase):
    def test_all_any(self):
        self.assertTrue(evx("all([1, 2, 3])"))
        self.assertFalse(evx("all([1, 0])"))
        self.assertTrue(evx("all([])"))
        self.assertTrue(evx("any([0, None, 2])"))
        self.assertFalse(evx("any([])"))

    def test_select(self):
        self.assertEqual(evx("sum(select([1, 2, 3], [True, False, True]))"), 4)
        with self.assertRaises(ExprError):
            evx("select([1], [1, 2])")

    def test_env_builtins_unavailable_in_dict_env(self):
        for src in ("today()", "day('1130')", "has('x', 'y')", "span_open('x')"):
            with self.assertRaises(ExprError):
                evx(src)


class TestStateBuiltins(unittest.TestCase):
    RULES = {"id": "t", "traits": {"n": {"type": "number"}},
             "lists": {"gear": {}}, "spans": {"trip": {}},
             "derived": {"t": "today()", "age": "today() - day('1130-01-01')",
                         "lamp": "has('gear', 'lamp')", "away": "span_open('trip')",
                         "heavy": "sum(select(list.gear[*].w, list.gear[*].big))"}}

    def setUp(self):
        self.sd = SheetDir(self.RULES, history={"s01": [
            ev("1130-01-01", {"set": "n", "to": 1}),
            ev("1130-01-11", {"gain": "list.gear", "id": "lamp", "entry": {"w": 2, "big": True}},
               {"gain": "list.gear", "id": "pin", "entry": {"w": 5, "big": False}},
               {"start": "trip", "id": "t1"})]})

    def tearDown(self):
        self.sd.cleanup()

    def test_today_latest_and_at(self):
        doc, _ = self.sd.resolve()
        self.assertEqual(doc["derived"]["age"], 10)
        self.assertTrue(doc["derived"]["lamp"])
        self.assertTrue(doc["derived"]["away"])
        self.assertEqual(doc["derived"]["heavy"], 2)
        doc, _ = self.sd.resolve(at="1130-01")
        self.assertEqual(doc["derived"]["age"], 30)  # --at a month = its last day
        doc, _ = self.sd.resolve(at="1130-01-05")
        self.assertFalse(doc["derived"]["lamp"])

    def test_bad_day_warns_but_keeps_event(self):
        self.sd.write_history("s02", [ev("1130-02-30", {"set": "n", "to": 9})])
        doc, res = self.sd.resolve()
        self.assertIn("invalid-event", codes(res))
        self.assertEqual(doc["values"]["n"], 9)

    def test_manifest_calendar(self):
        sd = SheetDir(self.RULES, history={"s01": [ev("0001-01-01", {"set": "n", "to": 1}),
                                                   ev("0002-01-01", {"set": "n", "to": 2})]},
                      manifest={"calendar": {"months": [{"days": 10}] * 12}})
        try:
            doc, _ = sd.resolve()
            self.assertEqual(doc["derived"]["t"] - sd.load().calendar.day("0001-01-01"), 120)
        finally:
            sd.cleanup()


if __name__ == "__main__":
    unittest.main()
