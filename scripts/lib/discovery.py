"""Unified data file discovery for campaign tools."""

import json
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable


#: Subfolder names excluded from recursive discovery. ``archive/`` is the
#: established convention for shelving data without deleting it (e.g.
#: ``memories/archive/sophie-arc/``); dot- and underscore-prefixed folders
#: are treated as hidden/scratch.
_EXCLUDED_DIR_NAMES = {"archive"}


def _dir_files(data_dir: Path, file_pattern: str) -> List[Path]:
    """Collect data files under a data-type directory, recursively.

    Subfolders are organizational (e.g. ``characters/ice-age/``,
    ``characters/crew/``) and their contents load as first-class data.
    Folders named ``archive`` (or prefixed with ``.``/``_``) are skipped,
    as are ``.``/``_``-prefixed files (sidecar metadata such as a cluster's
    ``_cluster.json`` bundle module lives beside the data without loading).
    """
    results: List[Path] = []
    for p in sorted(data_dir.rglob(file_pattern)):
        if p.name.startswith((".", "_")):
            continue
        parts = p.relative_to(data_dir).parts[:-1]
        if any(part in _EXCLUDED_DIR_NAMES or part.startswith((".", "_"))
               for part in parts):
            continue
        results.append(p)
    return results


def discover_data(
    data_type: str,
    search_root: Path,
    *,
    file_pattern: str = "*.json",
    loose_pattern: Optional[str] = None,
    multi_collection_key: Optional[str] = None,
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
        multi_collection_key: Optional key name for multi-item file shape. When
                              provided, files may be a dict with this key
                              containing a list of items, plus an optional
                              top-level ``namespace`` field. Returned dict is
                              keyed by ``f"{namespace}:{id}"`` (qualified keys).
                              When None, returned dict is keyed by bare IDs
                              (legacy behavior; required for non-namegen tools).
        on_warning: Optional callback for warning messages. If None, prints to stderr.

    Returns:
        Dict mapping item IDs to their data dictionaries.

    Search order:
        1. {search_root}/{data_type}/
        2. Parent directories: {parent}/{data_type}/
        3. campaigns/*/{data_type}/
        4. tools/data/{data_type}/
        5. /mnt/skills/user/rpg-tools/tools/data/{data_type}/
        6. /mnt/user-data/uploads/{data_type}/
        7. /mnt/user-data/uploads/{loose_pattern} (if provided)
        8. /home/claude/*/{data_type}/
    """
    if on_warning is None:
        def on_warning(msg: str) -> None:
            print(msg, file=sys.stderr)

    items: Dict[str, Dict[str, Any]] = {}
    data_paths: List[Path] = []

    # 1. Look in {data_type}/ relative to search root
    data_dir = search_root / data_type
    if data_dir.exists():
        data_paths.extend(_dir_files(data_dir, file_pattern))

    # 2. Check parent directories if nothing found yet
    if not data_paths:
        for parent in [search_root.parent, search_root.parent.parent]:
            data_dir = parent / data_type
            if data_dir.exists():
                data_paths.extend(_dir_files(data_dir, file_pattern))
                break

    # 3. Look in campaigns/*/{data_type}/ (check search_root and ancestors)
    campaigns_found = False
    for root in [search_root] + list(search_root.parents):
        campaigns_dir = root / "campaigns"
        if campaigns_dir.exists():
            campaigns_found = True
            for campaign_dir in campaigns_dir.iterdir():
                if campaign_dir.is_dir():
                    type_dir = campaign_dir / data_type
                    if type_dir.exists():
                        data_paths.extend(_dir_files(type_dir, file_pattern))
            break
    # Also check from cwd if different from search_root
    if not campaigns_found:
        cwd = Path.cwd()
        for root in [cwd] + list(cwd.parents):
            campaigns_dir = root / "campaigns"
            if campaigns_dir.exists():
                for campaign_dir in campaigns_dir.iterdir():
                    if campaign_dir.is_dir():
                        type_dir = campaign_dir / data_type
                        if type_dir.exists():
                            data_paths.extend(_dir_files(type_dir, file_pattern))
                break

    # 4. Look in tools/data/{data_type}/
    tools_data = search_root / "tools" / "data" / data_type
    if tools_data.exists():
        data_paths.extend(_dir_files(tools_data, file_pattern))

    # 5. Look in skill mount (Claude.ai skill environment)
    skill_data = Path("/mnt/skills/user/rpg-tools/tools/data") / data_type
    if skill_data.exists():
        data_paths.extend(_dir_files(skill_data, file_pattern))

    # 6. Look in user uploads (Claude.ai environment)
    uploads_data = Path("/mnt/user-data/uploads") / data_type
    if uploads_data.exists():
        data_paths.extend(_dir_files(uploads_data, file_pattern))

    # 7. Check for loose files in uploads root
    if loose_pattern:
        uploads_root = Path("/mnt/user-data/uploads")
        if uploads_root.exists():
            data_paths.extend(uploads_root.glob(loose_pattern))

    # 8. Look in /home/claude/*/{data_type}/ (extracted bundles)
    home_claude = Path("/home/claude")
    if home_claude.exists():
        for subdir in home_claude.iterdir():
            if subdir.is_dir():
                type_dir = subdir / data_type
                if type_dir.exists():
                    data_paths.extend(_dir_files(type_dir, file_pattern))

    # De-duplicate discovered paths: the same file is often found via more
    # than one search step (e.g. cwd inside a campaign + the campaigns/* scan),
    # which previously produced spurious "duplicate ID" warnings against itself.
    seen_paths = set()
    unique_paths: List[Path] = []
    for path in data_paths:
        key = path.resolve()
        if key not in seen_paths:
            seen_paths.add(key)
            unique_paths.append(path)
    data_paths = unique_paths

    # Track sources for duplicate detection
    item_sources: Dict[str, Path] = {}

    # Load all discovered files
    for path in data_paths:
        try:
            with open(path, encoding='utf-8-sig') as f:
                data = json.load(f)

                # Determine file-level namespace and items-to-process
                file_namespace = ""
                if (
                    multi_collection_key
                    and isinstance(data, dict)
                    and isinstance(data.get(multi_collection_key), list)
                ):
                    # Multi-collection file: explode into entries with file-level
                    # namespace context
                    file_namespace = data.get("namespace", "") or ""
                    items_to_process = data[multi_collection_key]
                else:
                    # Legacy: list-of-items, or single-item dict
                    items_to_process = data if isinstance(data, list) else [data]

                for item in items_to_process:
                    bare_id = item.get("id", f"{path.stem}-{len(items)}")
                    if multi_collection_key:
                        # Per-item namespace overrides file-level namespace
                        item_namespace = item.get("namespace", file_namespace) or ""
                        item_key = f"{item_namespace}:{bare_id}"
                    else:
                        item_key = bare_id
                    if item_key in items:
                        on_warning(f"Warning: Duplicate ID '{item_key}' found in {path.name} "
                                  f"(already loaded from {item_sources[item_key].name})")
                    items[item_key] = item
                    item_sources[item_key] = path
        except Exception as e:
            on_warning(f"Warning: Could not load {data_type} file {path}: {e}")

    if not items:
        on_warning(f"Warning: No {data_type} files found in {data_type}/")

    return items
