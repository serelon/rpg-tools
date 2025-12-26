# Data Tool Architecture

This document describes the architectural patterns used by the campaign data tools (characters, locations, memories, stories, log, campaign). Understanding these patterns is essential for implementing consistent CRUD operations.

## Overview

The tools follow a **read-anywhere, write-canonical** pattern:

- **Read**: Multi-source discovery aggregates data from many locations
- **Write**: New items go to the canonical location (`{cwd}/{data_type}/{id}.json`)
- **Update**: Find the original file, modify in place
- **Delete**: Find the original file, remove it

---

## Discovery Pattern

All data tools use `scripts/lib/discovery.py` to find JSON data files. Discovery searches multiple locations and merges results into a single in-memory dictionary.

### Search Order

```
1. {cwd}/{data_type}/           # Primary: current working directory
2. {parent}/{data_type}/        # Fallback: parent directories (if #1 empty)
3. campaigns/*/{data_type}/     # Multi-campaign support
4. tools/data/{data_type}/      # Legacy/bundled data
5. /mnt/user-data/uploads/{data_type}/   # Claude.ai uploads
6. /mnt/user-data/uploads/{loose_pattern}  # Loose files (e.g., *-stories.json)
7. /home/claude/*/{data_type}/  # Extracted skill bundles
```

### ID Extraction

Each item gets an ID from (in priority order):
1. The `id` field in the JSON
2. For single-item files: the filename (without `.json` extension)
3. For items in an array: a generated ID if `id` is missing (e.g., `filename-0`)

### Merge Behavior

- Items from all locations are merged into one dictionary
- If the same ID appears in multiple locations, **last wins** (later in search order overrides earlier)
- This allows local overrides of bundled data

### File Formats

Discovery handles two JSON structures:

```jsonc
// Single item (one per file)
{
  "id": "kira-voss",
  "name": "Kira Voss",
  ...
}

// Array of items (multiple per file)
[
  { "id": "memory-001", ... },
  { "id": "memory-002", ... }
]
```

---

## Canonical Write Pattern

When creating new items or saving changes, tools write to the **canonical location** relative to the current working directory.

### Bundle Structure

```
campaign-bundle/
├── characters/
│   ├── kira-voss.json
│   └── dex.json
├── locations/
│   ├── threshold-station.json
│   └── port-sorrow.json
├── memories/
│   └── kira-memories.json
├── stories/
│   └── broker-arc-stories.json
├── namesets/
│   └── spacer-names.json
└── campaign/
    ├── config.json      # Calendar, eras, campaign metadata
    ├── state.json       # Active branch, character states
    ├── log.json         # Session log entries
    └── changelog.json   # Character development changelog
```

### Write Location Rules

| Data Type | Canonical Location | Notes |
|-----------|-------------------|-------|
| characters | `characters/{id}.json` | One character per file |
| locations | `locations/{id}.json` | One location per file |
| memories | `memories/{id}.json` | Can be array of memories |
| stories | `stories/{id}.json` | Can be array of stories |
| namesets | `namesets/{id}.json` | One nameset per file |
| log | `campaign/log.json` | Single file, array of entries |
| state | `campaign/state.json` | Single file |
| config | `campaign/config.json` | Single file |
| changelog | `campaign/changelog.json` | Single file |

### Directory Creation

Tools create parent directories as needed:

```python
data_dir = search_root / data_type
data_dir.mkdir(exist_ok=True)
```

---

## Update Semantics

Updates follow a **find-and-modify** pattern:

1. **Find item in memory** using `find_item()` (ID or name lookup)
2. **Modify the in-memory dict**
3. **Locate the source file** (try canonical path first, then scan)
4. **Write back to source file**

### File Location Strategy

```python
# Try canonical path first
char_file = search_root / "characters" / f"{char_id}.json"

if not char_file.exists():
    # Scan directory to find file containing this ID
    for path in (search_root / "characters").glob("*.json"):
        with open(path) as f:
            data = json.load(f)
            if data.get("id") == char_id:
                char_file = path
                break
```

This handles cases where:
- Filename differs from ID
- File was discovered from a non-canonical location

---

## ID Conventions

### Format

- Lowercase
- Kebab-case (words separated by hyphens)
- No spaces or special characters

Examples: `kira-voss`, `threshold-station`, `memory-00042`

### Generated IDs

Some tools generate sequential IDs:

```python
# Log entries: log-00001, log-00002, ...
def generate_log_id(entries):
    max_num = max(
        (int(e["id"][4:]) for e in entries if e.get("id", "").startswith("log-")),
        default=0
    )
    return f"log-{max_num + 1:05d}"
```

### ID vs Filename

- The `id` field is authoritative
- Filename is a hint, but tools prefer the `id` field
- Recommended: keep filename and ID in sync (`kira-voss.json` contains `"id": "kira-voss"`)

---

## CRUD Operations

### Current State

| Tool | Create | Read | Update | Delete |
|------|--------|------|--------|--------|
| characters.py | - | ✓ | ✓ | - |
| locations.py | - | ✓ | - | - |
| memories.py | - | ✓ | - | - |
| stories.py | - | ✓ | - | - |
| log.py | ✓ (add) | ✓ | - | ✓ |
| campaign.py | - | ✓ | ✓ (state) | - |

### Implementation Guidelines

**Create:**
```python
def cmd_create(id: str, name: str, ...):
    # 1. Validate ID doesn't exist
    if id in items:
        error("ID already exists")

    # 2. Build item dict
    item = {"id": id, "name": name, ...}

    # 3. Write to canonical location
    path = Path.cwd() / data_type / f"{id}.json"
    path.parent.mkdir(exist_ok=True)
    with open(path, 'w') as f:
        json.dump(item, f, indent=2)
```

**Delete:**
```python
def cmd_delete(id: str):
    # 1. Find item (validates existence)
    item = find_item(items, id)

    # 2. Locate source file (same strategy as update)
    path = find_source_file(id)

    # 3. Remove file
    path.unlink()
```

---

## Edge Cases

### Duplicate IDs Across Sources

If the same ID exists in multiple discovered locations:
- Last discovered wins (per search order)
- No warning is issued
- This is intentional for local overrides

### Missing Source File on Update

If an item was discovered but the file can't be found for update:
- The update silently succeeds in memory
- File write is skipped
- This can happen if files are moved/deleted during a session

### Array Files

For files containing arrays (memories, stories):
- Each item in the array is indexed separately by ID
- Updates to array items require rewriting the entire file
- Consider: future migration to one-item-per-file for simpler updates

---

## Shared Library

The `scripts/lib/` module provides reusable components:

| Module | Purpose |
|--------|---------|
| `discovery.py` | Multi-path data file discovery |
| `lookup.py` | Find items by ID/name, field queries |
| `parsers.py` | Era and session string parsing |
| `changelog.py` | Character development changelog |
| `calendars/` | Modular calendar system |

Import via:
```python
from lib import discover_data, find_item, load_changelog
```
