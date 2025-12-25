"""Modular calendar system for in-world dates."""

from .base import Calendar, DateValue
from .offset import OffsetCalendar, create_calendar as create_offset_calendar

# Registry of calendar types
CALENDAR_TYPES = {
    "offset": create_offset_calendar,
}


def create_calendar(calendar_type: str, config: dict = None) -> Calendar:
    """Create a calendar of the specified type."""
    if calendar_type not in CALENDAR_TYPES:
        raise ValueError(f"Unknown calendar type: {calendar_type}. "
                        f"Available: {list(CALENDAR_TYPES.keys())}")
    return CALENDAR_TYPES[calendar_type](config)


__all__ = ['Calendar', 'DateValue', 'OffsetCalendar', 'create_calendar']
