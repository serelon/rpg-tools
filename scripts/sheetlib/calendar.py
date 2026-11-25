"""Calendars for the sheet ledger: day arithmetic and display.

Storage stays partial ISO (``dates.py``); a calendar only answers "which day
number is this date" and "how is a day shown". The default is the proleptic
Gregorian calendar (signed years, year 0 exists). A sheet may declare its own
in the manifest (or the pack's rules) as ``calendar``::

    {"months": [{"name": "Firstmonth", "days": 30}, ...],   # 12 entries
     "epoch": "2389-03-14",          # day 0 for the {epoch_days} display token
     "format": "L+{epoch_days}d"}    # display: {y} {m} {d} {month} {epoch_days}

Custom calendars have no leap years. ``shortcut: 12 months only (dates.py
validates MM <= 12); widen dates.parse if a campaign needs a 13th month.``
"""
from . import dates
from .expr import SheetError

GREG_MONTHS = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


def _is_leap(y):
    return y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)


def _greg_days(y, m, d):
    """Days since 0000-03-01-ish epoch (Hinnant's days_from_civil), signed years."""
    y -= m <= 2
    era = (y if y >= 0 else y - 399) // 400
    yoe = y - era * 400
    doy = (153 * (m + (-3 if m > 2 else 9)) + 2) // 5 + d - 1
    doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    return era * 146097 + doe - 719468  # 0 = 1970-01-01


def _greg_civil(z):
    z += 719468
    era = (z if z >= 0 else z - 146096) // 146097
    doe = z - era * 146097
    yoe = (doe - doe // 1460 + doe // 36524 - doe // 146096) // 365
    y = yoe + era * 400
    doy = doe - (365 * yoe + yoe // 4 - yoe // 100)
    mp = (5 * doy + 2) // 153
    d = doy - (153 * mp + 2) // 5 + 1
    m = mp + (3 if mp < 10 else -9)
    return (y + (m <= 2), m, d)


class Calendar:
    def __init__(self, spec=None):
        spec = spec or {}
        if not isinstance(spec, dict):
            raise SheetError("calendar must be an object")
        months = spec.get("months")
        self.custom = months is not None
        if self.custom:
            if not isinstance(months, list) or len(months) != 12:
                raise SheetError("calendar.months must list 12 months")
            self.lengths = []
            self.names = []
            for i, mo in enumerate(months):
                if not isinstance(mo, dict) or not isinstance(mo.get("days"), int) \
                        or isinstance(mo.get("days"), bool) or not 1 <= mo["days"] <= 99:
                    raise SheetError("calendar.months[%d] needs days (1-99)" % i)
                self.lengths.append(mo["days"])
                self.names.append(str(mo.get("name") or i + 1))
            self.year_len = sum(self.lengths)
            self._starts = [sum(self.lengths[:i]) for i in range(12)]
        else:
            self.lengths = None
            self.names = list(spec.get("month_names") or [])
            self.year_len = 365.2425
        self.fmt = spec.get("format")
        if self.fmt is not None and not isinstance(self.fmt, str):
            raise SheetError("calendar.format must be a string")
        self.epoch = None
        if spec.get("epoch") is not None:
            if not dates.is_valid(spec["epoch"]):
                raise SheetError("calendar.epoch must be a date, got %r" % (spec["epoch"],))
            self.epoch = self.day(spec["epoch"])

    # -- core
    def month_len(self, y, m):
        if self.custom:
            return self.lengths[m - 1]
        return 29 if m == 2 and _is_leap(y) else GREG_MONTHS[m - 1]

    def day_of(self, y, m, d):
        d = max(1, min(d, self.month_len(y, m)))  # a day past the month counts as its last
        if self.custom:
            return y * self.year_len + self._starts[m - 1] + d - 1
        return _greg_days(y, m, d)

    def day(self, text, end=False):
        """Day number of a partial date: its first day, or its last with ``end``."""
        y, m, d = dates.parse(text)
        return self.day_of_key((y, m or 0, d or 0), end)

    def day_of_key(self, key, end=False):
        y, m, d = key
        if not m:
            m, d = (12, 99) if end else (1, 1)
        elif not d:
            d = 99 if end else 1
        return self.day_of(y, m, d)

    def bad_day(self, text):
        """True when a full date's day is past its month's length."""
        y, m, d = dates.parse(text)
        return d is not None and m is not None and d > self.month_len(y, m)

    def date(self, n):
        """Day number → full ISO date."""
        if self.custom:
            y, r = divmod(n, self.year_len)
            m = max(i for i in range(12) if self._starts[i] <= r) + 1
            y, m, d = int(y), m, int(r - self._starts[m - 1] + 1)
        else:
            y, m, d = _greg_civil(n)
        sign = "-" if y < 0 else ""
        return "%s%04d-%02d-%02d" % (sign, abs(y), m, d)

    def years(self, days):
        return days / self.year_len

    def display(self, n):
        iso = self.date(n)
        if not self.fmt:
            return iso
        y, m, d = dates.parse(iso)
        name = self.names[m - 1] if len(self.names) == 12 else str(m)
        tokens = {"y": y, "m": "%02d" % m, "d": d, "month": name,
                  "epoch_days": n - self.epoch if self.epoch is not None else n}
        try:
            return self.fmt.format(**tokens)
        except (KeyError, IndexError, ValueError):
            return iso


GREGORIAN = Calendar()
