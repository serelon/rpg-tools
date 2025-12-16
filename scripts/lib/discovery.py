"""Unified data file discovery for campaign tools."""

import json
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable


def discover_data(
    data_type: str,
    search_root: Path,
    *,
    file_pattern: str = "*.json",
    loose_pattern: Optional[str] = None,
    on_warning: Optional[Callable[[str], None]] = None
) -> Dict[str, Dict[str, Any]]:
    """Discover and load JSON data files of a given type.

    Args:
        data_type: The type of data (e.g., "characters", "locations", "memories",
                   "stories", "namesets"). Used to find the appropriate directory.
        search_root: Starting directory for search (usually repo root or cwd).
        file_pattern: Glob pattern for files within the data directory.
        loose_pattern: Optional pattern for loose files in uploads root
                       (e.g., "*-stories.json").
        on_warning: Optional callback for warning messages. If None, prints to stderr.

    Returns:
        Dict mapping item IDs to their data dictionaries.

    Search order:
        1. {search_root}/{data_type}/
        2. Parent directories: {parent}/{data_type}/
        3. campaigns/*/{data_type}/
        4. tools/data/{data_type}/
        5. /mnt/user-data/uploads/{data_type}/
        6. /mnt/user-data/uploads/{loose_pattern} (if provided)
        7. /home/claude/*/{data_type}/
    """
    if on_warning is None:
        def on_warning(msg: str) -> None:
            print(msg, file=sys.stderr)

    items: Dict[str, Dict[str, Any]] = {}
    data_paths: List[Path] = []

    # 1. Look in {data_type}/ relative to search root
    data_dir = search_root / data_type
    if data_dir.exists():
        data_paths.extend(data_dir.glob(file_pattern))

    # 2. Check parent directories if nothing found yet
    if not data_paths:
        for parent in [search_root.parent, search_root.parent.parent]:
            data_dir = parent / data_type
            if data_dir.exists():
                data_paths.extend(data_dir.glob(file_pattern))
                break

    # 3. Look in campaigns/*/{data_type}/
    campaigns_dir = search_root / "campaigns"
    if campaigns_dir.exists():
        for campaign_dir in campaigns_dir.iterdir():
            if campaign_dir.is_dir():
                type_dir = campaign_dir / data_type
                if type_dir.exists():
                    data_paths.extend(type_dir.glob(file_pattern))

    # 4. Look in tools/data/{data_type}/
    tools_data = search_root / "tools" / "data" / data_type
    if tools_data.exists():
        data_paths.extend(tools_data.glob(file_pattern))

    # 5. Look in user uploads (Claude.ai environment)
    uploads_data = Path("/mnt/user-data/uploads") / data_type
    if uploads_data.exists():
        data_paths.extend(uploads_data.glob(file_pattern))

    # 6. Check for loose files in uploads root
    if loose_pattern:
        uploads_root = Path("/mnt/user-data/uploads")
        if uploads_root.exists():
            data_paths.extend(uploads_root.glob(loose_pattern))

    # 7. Look in /home/claude/*/{data_type}/ (extracted bundles)
    home_claude = Path("/home/claude")
    if home_claude.exists():
        for subdir in home_claude.iterdir():
            if subdir.is_dir():
                type_dir = subdir / data_type
                if type_dir.exists():
                    data_paths.extend(type_dir.glob(file_pattern))

    # Load all discovered files
    for path in data_paths:
        try:
            with open(path, encoding='utf-8') as f:
                data = json.load(f)
                # Handle both single item and array of items
                if isinstance(data, list):
                    for item in data:
                        item_id = item.get("id", f"{path.stem}-{len(items)}")
                        items[item_id] = item
                else:
                    item_id = data.get("id", path.stem)
                    items[item_id] = data
        except Exception as e:
            on_warning(f"Warning: Could not load {data_type} file {path}: {e}")

    if not items:
        on_warning(f"Warning: No {data_type} files found in {data_type}/")

    return items
