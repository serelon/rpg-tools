#!/usr/bin/env python3
"""Campaign log tool for tracking events chronologically."""

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

from lib.calendars import create_calendar, is_loose_date


# Log storage
log_entries: List[Dict[str, Any]] = []
campaign_config: Dict[str, Any] = {}

# Importance hierarchy for filtering (higher = more important)
IMPORTANCE_LEVELS = {"minor": 0, "normal": 1, "major": 2, "critical": 3}


def load_campaign_config(search_root: Path) -> Dict[str, Any]:
    """Load campaign configuration."""
    config_paths = [
        search_root / "campaign" / "config.json",
        search_root / "campaign.json",
    ]

    for path in config_paths:
        if path.exists():
            try:
                with open(path, encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Warning: Could not load campaign config: {e}", file=sys.stderr)

    # Default config
    return {
        "calendar": {
            "type": "offset",
            "config": {"year_prefix": "Y", "day_prefix": "D"}
        }
    }


def load_log(search_root: Path) -> List[Dict[str, Any]]:
    """Load log entries from campaign/log.json."""
    log_paths = [
        search_root / "campaign" / "log.json",
    ]

    for path in log_paths:
        if path.exists():
            try:
                with open(path, encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Warning: Could not load log: {e}", file=sys.stderr)

    return []


def save_log(search_root: Path, entries: List[Dict[str, Any]]) -> None:
    """Save log entries to campaign/log.json."""
    log_dir = search_root / "campaign"
    log_dir.mkdir(exist_ok=True)

    log_path = log_dir / "log.json"
    with open(log_path, 'w', encoding='utf-8') as f:
        json.dump(entries, f, indent=2)


def generate_log_id(entries: List[Dict[str, Any]]) -> str:
    """Generate next log entry ID."""
    max_num = 0
    for entry in entries:
        entry_id = entry.get("id", "")
        if entry_id.startswith("log-"):
            try:
                num = int(entry_id[4:])
                max_num = max(max_num, num)
            except ValueError:
                pass
    return f"log-{max_num + 1:05d}"


def get_calendar():
    """Get calendar instance from config."""
    cal_config = campaign_config.get("calendar", {})
    cal_type = cal_config.get("type", "offset")
    return create_calendar(cal_type, cal_config.get("config"))


def parse_characters_arg(chars_str: str) -> Dict[str, str]:
    """Parse characters argument like 'juno:defining,tam:present'."""
    result = {}
    if not chars_str:
        return result

    # Handle JSON format
    if chars_str.startswith('{'):
        try:
            return json.loads(chars_str)
        except json.JSONDecodeError:
            pass

    # Handle compact format: juno:defining,tam:present
    for pair in chars_str.split(','):
        pair = pair.strip()
        if ':' in pair:
            char_id, role = pair.split(':', 1)
            result[char_id.strip()] = role.strip()
        else:
            result[pair] = "present"

    return result


def format_entry(entry: Dict[str, Any], verbose: bool = False) -> str:
    """Format a log entry for display."""
    lines = []

    date = entry.get("date") or entry.get("date_loose") or "?"
    summary = entry.get("summary", "")
    entry_id = entry.get("id", "")

    if verbose:
        lines.append(f"[{entry_id}] {date}: {summary}")

        if entry.get("branch"):
            lines.append(f"  Branch: {entry['branch']}")
        if entry.get("importance"):
            lines.append(f"  Importance: {entry['importance']}")
        if entry.get("characters"):
            chars = entry["characters"]
            char_strs = [f"{k} ({v})" for k, v in chars.items()]
            lines.append(f"  Characters: {', '.join(char_strs)}")
        if entry.get("locations"):
            lines.append(f"  Locations: {', '.join(entry['locations'])}")
        if entry.get("tags"):
            lines.append(f"  Tags: {', '.join(entry['tags'])}")
    else:
        lines.append(f"{date}: {summary}")

    return "\n".join(lines)


def cmd_add(
    summary: str,
    date: Optional[str] = None,
    date_loose: Optional[str] = None,
    branch: Optional[str] = None,
    importance: str = "normal",
    characters: Optional[str] = None,
    locations: Optional[str] = None,
    tags: Optional[str] = None,
    session: Optional[str] = None,
    output_json: bool = False
) -> None:
    """Add a new log entry."""
    global log_entries

    entry = {
        "id": generate_log_id(log_entries),
        "summary": summary,
        "importance": importance,
        "created": datetime.now().isoformat(),
    }

    # Handle dates
    if date:
        if is_loose_date(date):
            entry["date_loose"] = date
        else:
            entry["date"] = date
    elif date_loose:
        entry["date_loose"] = date_loose

    if branch:
        entry["branch"] = branch
    else:
        # Auto-detect from campaign state
        state_path = Path.cwd() / "campaign" / "state.json"
        if state_path.exists():
            try:
                with open(state_path, encoding='utf-8') as f:
                    state = json.load(f)
                    if state.get("active_branch"):
                        entry["branch"] = state["active_branch"]
            except (OSError, json.JSONDecodeError) as e:
                print(f"Warning: Could not auto-detect branch from state file: {e}", file=sys.stderr)
    if characters:
        entry["characters"] = parse_characters_arg(characters)
    if locations:
        entry["locations"] = [loc.strip() for loc in locations.split(',')]
    if tags:
        entry["tags"] = [tag.strip() for tag in tags.split(',')]
    if session:
        entry["session"] = session

    log_entries.append(entry)
    save_log(Path.cwd(), log_entries)

    if output_json:
        print(json.dumps(entry, indent=2))
    else:
        print(f"Added: {format_entry(entry)}")


def cmd_list(
    branch: Optional[str] = None,
    character: Optional[str] = None,
    location: Optional[str] = None,
    importance: Optional[str] = None,
    tag: Optional[str] = None,
    session: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    limit: int = 0,
    verbose: bool = False,
    output_json: bool = False
) -> None:
    """List log entries with optional filters."""
    filtered = log_entries.copy()

    if branch:
        branch_lower = branch.lower()
        filtered = [e for e in filtered if e.get("branch", "").lower() == branch_lower]

    if character:
        char_lower = character.lower()
        filtered = [e for e in filtered
                   if char_lower in [c.lower() for c in e.get("characters", {}).keys()]]

    if location:
        loc_lower = location.lower()
        filtered = [e for e in filtered
                   if loc_lower in [l.lower() for l in e.get("locations", [])]]

    if importance:
        imp_lower = importance.lower()
        min_level = IMPORTANCE_LEVELS.get(imp_lower, 1)
        filtered = [e for e in filtered
                   if IMPORTANCE_LEVELS.get(e.get("importance", "normal").lower(), 1) >= min_level]

    if tag:
        tag_lower = tag.lower()
        filtered = [e for e in filtered
                   if tag_lower in [t.lower() for t in e.get("tags", [])]]

    if session:
        session_lower = session.lower()
        filtered = [e for e in filtered if e.get("session", "").lower() == session_lower]

    # Create calendar for date operations
    calendar = get_calendar()

    # Date range filtering
    if from_date or to_date:
        from_parsed = calendar.parse(from_date) if from_date else None
        to_parsed = calendar.parse(to_date) if to_date else None

        def in_range(entry):
            entry_date = entry.get("date")
            if not entry_date:
                # Exclude loose dates from range queries (can't compare)
                return False
            parsed = calendar.parse(entry_date)
            if not parsed:
                return False  # Can't parse, exclude from range query
            if from_parsed and parsed < from_parsed:
                return False
            if to_parsed and parsed > to_parsed:
                return False
            return True

        filtered = [e for e in filtered if in_range(e)]

    # Sort by date
    def sort_key(entry):
        date = entry.get("date")
        if date:
            parsed = calendar.parse(date)
            if parsed:
                return parsed.sort_key
        return (float('inf'),)

    filtered.sort(key=sort_key)

    if limit > 0:
        filtered = filtered[:limit]

    if output_json:
        print(json.dumps(filtered, indent=2))
    else:
        if not filtered:
            print("No log entries found matching criteria")
            return

        for entry in filtered:
            print(format_entry(entry, verbose))
            if verbose:
                print()


def cmd_show(entry_id: str, output_json: bool = False) -> None:
    """Show a specific log entry."""
    for entry in log_entries:
        if entry.get("id") == entry_id:
            if output_json:
                print(json.dumps(entry, indent=2))
            else:
                print(format_entry(entry, verbose=True))
            return

    print(f"Error: Log entry '{entry_id}' not found", file=sys.stderr)
    sys.exit(1)


def cmd_delete(entry_id: str) -> None:
    """Delete a log entry."""
    global log_entries

    for i, entry in enumerate(log_entries):
        if entry.get("id") == entry_id:
            deleted = log_entries.pop(i)
            save_log(Path.cwd(), log_entries)
            print(f"Deleted: {format_entry(deleted)}")
            return

    print(f"Error: Log entry '{entry_id}' not found", file=sys.stderr)
    sys.exit(1)


def main():
    global log_entries, campaign_config

    search_root = Path.cwd()
    campaign_config = load_campaign_config(search_root)
    log_entries = load_log(search_root)

    if len(sys.argv) < 2 or sys.argv[1] in ('--help', '-h'):
        print("Usage: python log.py <command> [options]")
        print("\nCommands:")
        print("  add <summary> [options]        Add a log entry")
        print("  list [filters...]              List log entries")
        print("  show <id>                      Show specific entry")
        print("  delete <id>                    Delete an entry")
        print("\nAdd options:")
        print("  --date DATE                    In-world date (e.g., Y3.D45)")
        print("  --date-loose TEXT              Loose date (e.g., 'after the festival')")
        print("  --branch NAME                  Branch/arc name")
        print("  --importance LEVEL             normal, minor, major, critical")
        print("  --characters CHARS             juno:defining,tam:present or JSON")
        print("  --locations LOCS               Comma-separated location IDs")
        print("  --tags TAGS                    Comma-separated tags")
        print("  --session NAME                 Session identifier")
        print("\nList filters:")
        print("  --branch NAME                  Filter by branch")
        print("  --character NAME               Filter by character involvement")
        print("  --location NAME                Filter by location")
        print("  --importance LEVEL             Filter by importance")
        print("  --tag NAME                     Filter by tag")
        print("  --from DATE                    Filter from date")
        print("  --to DATE                      Filter to date")
        print("  --limit N                      Limit results")
        print("  --verbose                      Show full details")
        print("\nGlobal options:")
        print("  --json                         Output as JSON")
        sys.exit(0 if len(sys.argv) > 1 and sys.argv[1] in ('--help', '-h') else 1)

    command = sys.argv[1]

    # Parse options
    opts = {
        "summary": None,
        "entry_id": None,
        "date": None,
        "date_loose": None,
        "branch": None,
        "importance": None,  # Default to None, not "normal" - only filter if user specifies
        "characters": None,
        "locations": None,
        "tags": None,
        "session": None,
        "character": None,
        "location": None,
        "tag": None,
        "from_date": None,
        "to_date": None,
        "limit": 0,
        "verbose": False,
        "output_json": False,
    }

    i = 2
    positional_set = False
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == "--date" and i + 1 < len(sys.argv):
            opts["date"] = sys.argv[i + 1]
            i += 2
        elif arg == "--date-loose" and i + 1 < len(sys.argv):
            opts["date_loose"] = sys.argv[i + 1]
            i += 2
        elif arg == "--branch" and i + 1 < len(sys.argv):
            opts["branch"] = sys.argv[i + 1]
            i += 2
        elif arg == "--importance" and i + 1 < len(sys.argv):
            opts["importance"] = sys.argv[i + 1]
            i += 2
        elif arg == "--characters" and i + 1 < len(sys.argv):
            opts["characters"] = sys.argv[i + 1]
            i += 2
        elif arg == "--locations" and i + 1 < len(sys.argv):
            opts["locations"] = sys.argv[i + 1]
            i += 2
        elif arg == "--tags" and i + 1 < len(sys.argv):
            opts["tags"] = sys.argv[i + 1]
            i += 2
        elif arg == "--session" and i + 1 < len(sys.argv):
            opts["session"] = sys.argv[i + 1]
            i += 2
        elif arg == "--character" and i + 1 < len(sys.argv):
            opts["character"] = sys.argv[i + 1]
            i += 2
        elif arg == "--location" and i + 1 < len(sys.argv):
            opts["location"] = sys.argv[i + 1]
            i += 2
        elif arg == "--tag" and i + 1 < len(sys.argv):
            opts["tag"] = sys.argv[i + 1]
            i += 2
        elif arg == "--from" and i + 1 < len(sys.argv):
            opts["from_date"] = sys.argv[i + 1]
            i += 2
        elif arg == "--to" and i + 1 < len(sys.argv):
            opts["to_date"] = sys.argv[i + 1]
            i += 2
        elif arg == "--limit" and i + 1 < len(sys.argv):
            opts["limit"] = int(sys.argv[i + 1])
            i += 2
        elif arg == "--verbose":
            opts["verbose"] = True
            i += 1
        elif arg == "--json":
            opts["output_json"] = True
            i += 1
        elif not arg.startswith("--") and not positional_set:
            if command == "add":
                opts["summary"] = arg
            else:
                opts["entry_id"] = arg
            positional_set = True
            i += 1
        else:
            print(f"Unknown option: {arg}", file=sys.stderr)
            sys.exit(1)

    # Execute command
    if command == "add":
        if not opts["summary"]:
            print("Error: summary is required for 'add' command", file=sys.stderr)
            sys.exit(1)
        cmd_add(
            opts["summary"],
            date=opts["date"],
            date_loose=opts["date_loose"],
            branch=opts["branch"],
            importance=opts["importance"] or "normal",  # Default to "normal" if not specified
            characters=opts["characters"],
            locations=opts["locations"],
            tags=opts["tags"],
            session=opts["session"],
            output_json=opts["output_json"]
        )
    elif command == "list":
        cmd_list(
            branch=opts["branch"],
            character=opts["character"],
            location=opts["location"],
            importance=opts["importance"],
            tag=opts["tag"],
            session=opts["session"],
            from_date=opts["from_date"],
            to_date=opts["to_date"],
            limit=opts["limit"],
            verbose=opts["verbose"],
            output_json=opts["output_json"]
        )
    elif command == "show":
        if not opts["entry_id"]:
            print("Error: entry ID is required for 'show' command", file=sys.stderr)
            sys.exit(1)
        cmd_show(opts["entry_id"], output_json=opts["output_json"])
    elif command == "delete":
        if not opts["entry_id"]:
            print("Error: entry ID is required for 'delete' command", file=sys.stderr)
            sys.exit(1)
        cmd_delete(opts["entry_id"])
    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
