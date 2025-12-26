"""Persistence utilities for saving and deleting campaign data items."""

import json
from pathlib import Path
from typing import Dict, Any, Optional


def save_item(data_type: str, item: Dict[str, Any], search_root: Path) -> Path:
    """Save item to canonical location {data_type}/{id}.json.

    Args:
        data_type: The type of data (e.g., "characters", "locations").
        item: The item dict to save (must have "id" field).
        search_root: The root directory for saving.

    Returns:
        Path to the saved file.
    """
    item_id = item.get("id")
    if not item_id:
        raise ValueError("Item must have an 'id' field")

    data_dir = search_root / data_type
    data_dir.mkdir(exist_ok=True)

    path = data_dir / f"{item_id}.json"
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(item, f, indent=2)

    return path


def find_source_file(
    data_type: str,
    item_id: str,
    search_root: Path
) -> Optional[Path]:
    """Locate the source file for an item.

    Tries canonical path first, then scans directory.

    Args:
        data_type: The type of data (e.g., "characters", "locations").
        item_id: The item ID to find.
        search_root: The root directory to search.

    Returns:
        Path to the file, or None if not found.
    """
    data_dir = search_root / data_type

    # Try canonical path first
    canonical = data_dir / f"{item_id}.json"
    if canonical.exists():
        return canonical

    # Scan directory for file containing this ID
    if data_dir.exists():
        for path in data_dir.glob("*.json"):
            try:
                with open(path, encoding='utf-8-sig') as f:
                    data = json.load(f)
                    # Handle single item
                    if isinstance(data, dict) and data.get("id") == item_id:
                        return path
                    # Handle array of items
                    if isinstance(data, list):
                        for item in data:
                            if item.get("id") == item_id:
                                return path
            except (OSError, json.JSONDecodeError):
                pass

    return None


def delete_item_file(
    data_type: str,
    item_id: str,
    search_root: Path
) -> bool:
    """Delete an item's source file.

    Args:
        data_type: The type of data (e.g., "characters", "locations").
        item_id: The item ID to delete.
        search_root: The root directory to search.

    Returns:
        True if deleted, False if not found.
    """
    path = find_source_file(data_type, item_id, search_root)
    if path:
        path.unlink()
        return True
    return False
