"""Centralized validation for RPG tools.

Provides reusable validators for IDs, counts, dice notation, dates, and other
common input patterns across all campaign tools.
"""

import re
import sys
from typing import Optional, Set


# Valid involvement levels for log entries
VALID_INVOLVEMENTS: Set[str] = {'defining', 'present', 'mentioned', 'affected'}


class ValidationError(Exception):
    """Raised when validation fails."""
    pass


def validate_positive_int(value: int, name: str, min_val: int = 1) -> int:
    """Validate that value is a positive integer >= min_val.

    Args:
        value: The integer to validate
        name: Name of the parameter (for error messages)
        min_val: Minimum allowed value (default 1)

    Returns:
        The validated value

    Raises:
        ValidationError: If value is less than min_val
    """
    if value < min_val:
        raise ValidationError(f"Error: {name} must be at least {min_val}")
    return value


def validate_id(id_str: str, max_length: int = 100) -> str:
    """Validate an ID string for use as a filename.

    Args:
        id_str: The ID to validate
        max_length: Maximum allowed length (default 100)

    Returns:
        The validated ID (stripped of whitespace)

    Raises:
        ValidationError: If ID is empty, contains path separators, or is too long
    """
    if not id_str or not id_str.strip():
        raise ValidationError("Error: ID cannot be empty")

    id_str = id_str.strip()

    if len(id_str) > max_length:
        raise ValidationError(f"Error: ID too long (max {max_length} characters)")

    if '/' in id_str or '\\' in id_str:
        raise ValidationError("Error: ID cannot contain path separators (/ or \\)")

    return id_str


def validate_dice_sides(sides: int) -> int:
    """Validate dice sides count.

    Args:
        sides: Number of sides on the die

    Returns:
        The validated sides count

    Raises:
        ValidationError: If sides < 1
    """
    if sides < 1:
        raise ValidationError("Error: Dice must have at least 1 side")
    return sides


def validate_dice_notation_chars(notation: str) -> str:
    """Validate that dice notation doesn't contain invalid number formats.

    Rejects floats (2.5d6), hex (0x10d6), and scientific notation (1e2d6).

    Args:
        notation: The dice notation string

    Returns:
        The validated notation

    Raises:
        ValidationError: If notation contains invalid number formats
    """
    # Check for float notation before 'd'
    if re.search(r'\d+\.\d+d', notation.lower()):
        raise ValidationError(f"Error: Invalid dice notation '{notation}' - use whole numbers only")

    # Check for hex notation (0x)
    if '0x' in notation.lower():
        raise ValidationError(f"Error: Invalid dice notation '{notation}' - hex notation not supported")

    # Check for scientific notation before 'd'
    if re.search(r'\d+e\d+d', notation.lower()):
        raise ValidationError(f"Error: Invalid dice notation '{notation}' - scientific notation not supported")

    return notation


def validate_keep_drop_value(value: Optional[int], mod_type: str) -> int:
    """Validate keep/drop modifier value.

    Args:
        value: The modifier value (None means default to 1)
        mod_type: The modifier type (kh, kl, dh, dl)

    Returns:
        The validated value (defaults to 1 if None)

    Raises:
        ValidationError: If value is less than 1
    """
    if value is None:
        return 1
    if value < 1:
        raise ValidationError(f"Error: Cannot keep/drop fewer than 1 die")
    return value


def validate_involvement(level: str) -> str:
    """Validate character involvement level for log entries.

    Args:
        level: The involvement level string

    Returns:
        The validated level (lowercased)

    Raises:
        ValidationError: If level is not one of the valid options
    """
    level_lower = level.lower()
    if level_lower not in VALID_INVOLVEMENTS:
        valid = ', '.join(sorted(VALID_INVOLVEMENTS))
        raise ValidationError(f"Error: Invalid involvement '{level}'. Use: {valid}")
    return level_lower


def validate_character_reference(ref: str) -> str:
    """Validate a character reference (id or id:involvement).

    Args:
        ref: The character reference string

    Returns:
        The validated reference

    Raises:
        ValidationError: If the reference format is invalid
    """
    if not ref or not ref.strip():
        raise ValidationError("Error: Character reference cannot be empty")

    ref = ref.strip()

    # Check for format with involvement
    if ':' in ref:
        parts = ref.split(':', 1)
        char_id = parts[0].strip()
        involvement = parts[1].strip() if len(parts) > 1 else ""

        if not char_id:
            raise ValidationError("Error: Character ID cannot be empty")

        if involvement:
            validate_involvement(involvement)

    return ref


def validate_date_format(date_str: str) -> str:
    """Validate date format (Y#.D# pattern).

    Args:
        date_str: The date string to validate

    Returns:
        The validated date string

    Raises:
        ValidationError: If the format doesn't match Y#.D# or contains invalid values
    """
    if not date_str or not date_str.strip():
        raise ValidationError("Error: Date cannot be empty")

    date_str = date_str.strip()

    # Match Y#.D# format (e.g., Y1.D1, Y10.D365)
    match = re.match(r'^Y(\d+)\.D(\d+)$', date_str, re.IGNORECASE)
    if not match:
        raise ValidationError(f"Error: Invalid date format '{date_str}'. Use Y#.D# (e.g., Y1.D15)")

    year = int(match.group(1))
    day = int(match.group(2))

    if year < 1:
        raise ValidationError(f"Error: Year must be at least 1, got {year}")

    if day < 1:
        raise ValidationError(f"Error: Day must be at least 1, got {day}")

    return date_str


def validate_tag(tag: str) -> str:
    """Validate a tag string.

    Args:
        tag: The tag string to validate

    Returns:
        The validated tag

    Raises:
        ValidationError: If the tag is empty
    """
    if not tag or not tag.strip():
        raise ValidationError("Error: --tag cannot be empty")
    return tag.strip()


def exit_on_validation_error(func):
    """Decorator that catches ValidationError and exits with message."""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ValidationError as e:
            print(str(e), file=sys.stderr)
            sys.exit(1)
    return wrapper
