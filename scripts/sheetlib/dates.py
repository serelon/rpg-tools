"""Partial ISO dates for the sheet ledger (spec S6).

A date is ``YYYY``, ``YYYY-MM`` or ``YYYY-MM-DD`` with an optional sign on
the year (astronomical years: 0 exists, ``-500`` is 501 BCE). Dates are
bookkeeping for when a sheet changes, not story timestamps.
"""
import re

# ASCII digits only, whole string only (no trailing newline via ``$``).
DATE_RE = re.compile(r"([+-]?[0-9]{1,6})(?:-([0-9]{2})(?:-([0-9]{2}))?)?")


def parse(text):
    """Return ``(year, month|None, day|None)`` or ``None`` if invalid."""
    if not isinstance(text, str):
        return None
    m = DATE_RE.fullmatch(text)
    if not m:
        return None
    year = int(m.group(1))
    month = int(m.group(2)) if m.group(2) is not None else None
    day = int(m.group(3)) if m.group(3) is not None else None
    if month is not None and not 1 <= month <= 12:
        return None
    if day is not None and not 1 <= day <= 31:
        return None
    return (year, month, day)


def is_valid(text):
    return parse(text) is not None


def sort_key(text):
    """Sort key: vaguer sorts before contained (1130 < 1130-01 < 1130-01-01)."""
    y, m, d = parse(text)
    return (y, m or 0, d or 0)


def at_end(text):
    """Upper bound for ``--at``: missing parts filled high (span-inclusive)."""
    y, m, d = parse(text)
    return (y, m if m is not None else 12, d if d is not None else 31)


def years_of_key(key):
    """Fractional years for a ``(y, m, d)`` tuple (0 parts treated as 1)."""
    y, m, d = key
    return y + (max(m, 1) - 1) / 12 + (max(d, 1) - 1) / 372


def years(text):
    """Fractional years for a date string: Y + (M-1)/12 + (D-1)/372."""
    y, m, d = parse(text)
    return years_of_key((y, m or 0, d or 0))
