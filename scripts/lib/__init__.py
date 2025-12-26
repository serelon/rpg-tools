"""Shared library for RPG tools."""

from .parsers import parse_era, parse_session
from .discovery import discover_data
from .lookup import find_item, find_items_by_field
from .changelog import Changelog, ChangeEntry, load_changelog
from .persistence import save_item, find_source_file, delete_item_file
from .validation import (
    ValidationError,
    validate_positive_int,
    validate_id,
    validate_dice_sides,
    validate_dice_notation_chars,
    validate_keep_drop_value,
    validate_involvement,
    validate_character_reference,
    validate_date_format,
    validate_tag,
    VALID_INVOLVEMENTS,
)

__all__ = [
    'parse_era',
    'parse_session',
    'discover_data',
    'find_item',
    'find_items_by_field',
    'Changelog',
    'ChangeEntry',
    'load_changelog',
    'save_item',
    'find_source_file',
    'delete_item_file',
    'ValidationError',
    'validate_positive_int',
    'validate_id',
    'validate_dice_sides',
    'validate_dice_notation_chars',
    'validate_keep_drop_value',
    'validate_involvement',
    'validate_character_reference',
    'validate_date_format',
    'validate_tag',
    'VALID_INVOLVEMENTS',
]
