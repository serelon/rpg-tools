"""Parsing utilities for era strings, session numbers, etc."""

import re


def parse_era(era_str: str) -> int:
    """Parse era string to sortable integer (negative for BCE).

    Handles formats like: "15000 BCE", "500 CE", "3000 BC", "~1200 CE"
    Returns 0 for unparseable strings.
    """
    if not era_str:
        return 0

    # Strip approximate markers
    era = era_str.strip().lstrip('~').strip()

    # Match patterns like "15000 BCE", "500 CE", "3000 BC"
    match = re.match(r'(\d+)\s*(BCE|BC|CE|AD)?', era, re.IGNORECASE)
    if not match:
        return 0

    year = int(match.group(1))
    suffix = (match.group(2) or 'CE').upper()

    if suffix in ('BCE', 'BC'):
        return -year
    return year


def parse_session(session_str: str) -> int:
    """Parse session string to integer.

    Handles formats: s01, session-01, 01, Session 1, etc.
    Returns 0 for unparseable strings.
    """
    if not session_str:
        return 0

    # Extract first sequence of digits
    match = re.search(r'(\d+)', session_str)
    if match:
        return int(match.group(1))
    return 0
