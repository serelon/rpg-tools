"""Offset calendar - simple renamed/renumbered Gregorian-style dates."""

import re
from typing import Optional, Dict, Any

from .base import Calendar, DateValue


class OffsetCalendar(Calendar):
    """Calendar with configurable format and epoch name.

    Supports formats like:
    - "Y3.D45" (Year 3, Day 45)
    - "Year 3, Day 45"
    - Custom patterns via config

    Config options:
        format: Format string with {year} and {day} placeholders
        epoch: Name of the epoch (e.g., "After Founding")
        year_prefix: Prefix for year (default: "Y")
        day_prefix: Prefix for day (default: "D")
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.year_prefix = self.config.get("year_prefix", "Y")
        self.day_prefix = self.config.get("day_prefix", "D")
        self.epoch = self.config.get("epoch", "")

        # Build regex pattern for parsing
        yp = re.escape(self.year_prefix)
        dp = re.escape(self.day_prefix)
        self.pattern = re.compile(
            rf'{yp}(-?\d+)\.?{dp}(\d+)',
            re.IGNORECASE
        )
        # Also match "Year X, Day Y" style
        self.verbose_pattern = re.compile(
            r'Year\s+(-?\d+),?\s*Day\s+(\d+)',
            re.IGNORECASE
        )

    def parse(self, date_str: str) -> Optional[DateValue]:
        """Parse a date string like 'Y3.D45' or 'Year 3, Day 45'."""
        if not date_str:
            return None

        # Try compact format first
        match = self.pattern.match(date_str.strip())
        if not match:
            match = self.verbose_pattern.match(date_str.strip())

        if not match:
            return None

        year = int(match.group(1))
        day = int(match.group(2))

        return DateValue(
            raw=date_str,
            components={"year": year, "day": day},
            sort_key=(year, day)
        )

    def format(self, date: DateValue) -> str:
        """Format a date back to string."""
        year = date.components.get("year", 0)
        day = date.components.get("day", 0)
        return f"{self.year_prefix}{year}.{self.day_prefix}{day}"

    def validate(self, date_str: str) -> bool:
        """Check if date string is valid."""
        return self.parse(date_str) is not None


def create_calendar(config: Optional[Dict[str, Any]] = None) -> OffsetCalendar:
    """Factory function to create an offset calendar."""
    return OffsetCalendar(config)
