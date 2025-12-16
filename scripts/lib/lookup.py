"""Item lookup utilities for finding items by ID or name."""

import sys
from typing import Dict, Any, Optional, List


def find_item(
    items: Dict[str, Dict[str, Any]],
    name: str,
    type_label: str = "Item",
    *,
    exit_on_missing: bool = True,
    show_available: bool = True
) -> Optional[Dict[str, Any]]:
    """Find an item by ID or name (case-insensitive).

    Args:
        items: Dictionary of items keyed by ID.
        name: The ID or name to search for.
        type_label: Human-readable type name for error messages (e.g., "Character").
        exit_on_missing: If True, exits with error when not found. If False, returns None.
        show_available: If True, shows available items in error message.

    Returns:
        The matching item dict, or None if not found and exit_on_missing is False.
    """
    name_lower = name.lower()

    for item in items.values():
        if (item.get("id", "").lower() == name_lower or
            item.get("name", "").lower() == name_lower or
            item.get("title", "").lower() == name_lower):
            return item

    if exit_on_missing:
        print(f"Error: {type_label} '{name}' not found", file=sys.stderr)
        if show_available:
            available = list(items.keys())[:10]
            suffix = "..." if len(items) > 10 else ""
            print(f"Available: {', '.join(available)}{suffix}", file=sys.stderr)
        sys.exit(1)

    return None


def find_items_by_field(
    items: Dict[str, Dict[str, Any]],
    field: str,
    value: str,
    *,
    case_insensitive: bool = True,
    partial_match: bool = False
) -> List[Dict[str, Any]]:
    """Find all items where a field matches a value.

    Args:
        items: Dictionary of items keyed by ID.
        field: The field name to match (supports dot notation for nested fields).
        value: The value to match against.
        case_insensitive: If True, matches are case-insensitive.
        partial_match: If True, matches if value is contained in field value.

    Returns:
        List of matching items.
    """
    results = []
    search_value = value.lower() if case_insensitive else value

    for item in items.values():
        # Support dot notation for nested fields
        field_value = item
        for part in field.split('.'):
            if isinstance(field_value, dict):
                field_value = field_value.get(part)
            else:
                field_value = None
                break

        if field_value is None:
            continue

        # Handle list fields (e.g., tags)
        if isinstance(field_value, list):
            for v in field_value:
                compare_value = str(v).lower() if case_insensitive else str(v)
                if partial_match:
                    if search_value in compare_value:
                        results.append(item)
                        break
                else:
                    if compare_value == search_value:
                        results.append(item)
                        break
        else:
            compare_value = str(field_value).lower() if case_insensitive else str(field_value)
            if partial_match:
                if search_value in compare_value:
                    results.append(item)
            else:
                if compare_value == search_value:
                    results.append(item)

    return results
