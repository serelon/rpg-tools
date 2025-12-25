"""Loose date handling for narrative dates like 'three days after the festival'."""

from dataclasses import dataclass
from typing import Optional

from .base import DateValue


@dataclass
class LooseDate:
    """A narrative/loose date that can't be precisely sorted."""
    text: str
    anchor: Optional[str] = None  # Reference point if any

    def to_date_value(self) -> DateValue:
        """Convert to DateValue with minimal sort key."""
        return DateValue(
            raw=self.text,
            components={"loose": True, "text": self.text, "anchor": self.anchor},
            sort_key=(float('inf'),)  # Sorts after all precise dates
        )


def parse_loose_date(text: str) -> LooseDate:
    """Parse a loose date string."""
    # Could add heuristics here to extract anchors
    # For now, just wrap the text
    return LooseDate(text=text)


def is_loose_date(date_str: str) -> bool:
    """Check if a string looks like a loose date rather than structured."""
    if not date_str:
        return False
    # If it contains narrative words, it's probably loose
    narrative_markers = [
        "before", "after", "during", "following", "prior",
        "days", "weeks", "months", "years",
        "the", "when", "while"
    ]
    lower = date_str.lower()
    return any(marker in lower for marker in narrative_markers)
