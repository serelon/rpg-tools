"""Base calendar class for in-world date handling."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class DateValue:
    """Represents a parsed in-world date."""
    raw: str
    components: dict
    sort_key: tuple

    def __lt__(self, other: 'DateValue') -> bool:
        return self.sort_key < other.sort_key

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DateValue):
            return False
        return self.sort_key == other.sort_key


class Calendar(ABC):
    """Abstract base class for calendar systems."""

    @abstractmethod
    def parse(self, date_str: str) -> Optional[DateValue]:
        """Parse a date string into a DateValue.

        Returns None if the string cannot be parsed.
        """
        pass

    @abstractmethod
    def format(self, date: DateValue) -> str:
        """Format a DateValue back to a string."""
        pass

    @abstractmethod
    def validate(self, date_str: str) -> bool:
        """Check if a date string is valid for this calendar."""
        pass

    def compare(self, a: str, b: str) -> int:
        """Compare two date strings. Returns -1, 0, or 1."""
        date_a = self.parse(a)
        date_b = self.parse(b)

        if date_a is None or date_b is None:
            return 0

        if date_a < date_b:
            return -1
        elif date_a == date_b:
            return 0
        else:
            return 1
