#!/usr/bin/env python3
"""Campaign management tool for config, branches, state, and changelog."""

import json
import sys
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from lib import load_changelog


# Campaign data
campaign_config: Dict[str, Any] = {}
campaign_state: Dict[str, Any] = {}


def load_config(search_root: Path) -> Dict[str, Any]:
    """Load campaign configuration."""
    config_path = search_root / "campaign" / "config.json"

    if config_path.exists():
        try:
            with open(config_path, encoding='utf-8-sig') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Warning: Could not load campaign config: {e}", file=sys.stderr)

    return {}


def save_config(search_root: Path, config: Dict[str, Any]) -> None:
    """Save campaign configuration."""
    config_dir = search_root / "campaign"
    config_dir.mkdir(exist_ok=True)

    config_path = config_dir / "config.json"
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2)


def load_state(search_root: Path) -> Dict[str, Any]:
    """Load campaign state."""
    state_path = search_root / "campaign" / "state.json"

    if state_path.exists():
        try:
            with open(state_path, encoding='utf-8-sig') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Warning: Could not load campaign state: {e}", file=sys.stderr)

    return {"active_branch": None, "characters": {}}


def save_state(search_root: Path, state: Dict[str, Any]) -> None:
    """Save campaign state."""
    state_dir = search_root / "campaign"
    state_dir.mkdir(exist_ok=True)

    state_path = state_dir / "state.json"
    with open(state_path, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=2)


def cmd_init(
    name: str,
    calendar_type: str = "offset",
    output_json: bool = False
) -> None:
    """Initialize a new campaign."""
    global campaign_config

    campaign_config = {
        "campaign": name,
        "calendar": {
            "type": calendar_type,
            "config": {"year_prefix": "Y", "day_prefix": "D"}
        },
        "branches": [
            {
                "id": "main",
                "name": "Main Storyline",
                "protagonists": [],
                "status": "active"
            }
        ],
        "convergences": []
    }

    save_config(Path.cwd(), campaign_config)

    # Initialize state
    state = {"active_branch": "main", "characters": {}}
    save_state(Path.cwd(), state)

    if output_json:
        print(json.dumps(campaign_config, indent=2))
    else:
        print(f"Initialized campaign: {name}")
        print(f"Calendar: {calendar_type}")
        print("Created: campaign/config.json, campaign/state.json")


def cmd_show(output_json: bool = False) -> None:
    """Show campaign configuration."""
    if output_json:
        print(json.dumps(campaign_config, indent=2))
    else:
        name = campaign_config.get("campaign", "Unknown")
        print(f"Campaign: {name}")

        cal = campaign_config.get("calendar", {})
        print(f"Calendar: {cal.get('type', 'offset')}")

        branches = campaign_config.get("branches", [])
        print(f"\nBranches ({len(branches)}):")
        for branch in branches:
            status = branch.get("status", "active")
            protagonists = branch.get("protagonists", [])
            proto_str = f" [{', '.join(protagonists)}]" if protagonists else ""
            print(f"  - {branch['id']}: {branch['name']}{proto_str} ({status})")


def cmd_branch_list(output_json: bool = False) -> None:
    """List all branches."""
    branches = campaign_config.get("branches", [])
    active = campaign_state.get("active_branch")

    if output_json:
        print(json.dumps({"branches": branches, "active": active}, indent=2))
    else:
        print("Branches:")
        for branch in branches:
            marker = " *" if branch["id"] == active else ""
            status = branch.get("status", "active")
            print(f"  - {branch['id']}: {branch['name']} ({status}){marker}")
        if active:
            print(f"\n* = active branch")


def cmd_branch_switch(branch_id: str, output_json: bool = False) -> None:
    """Switch active branch."""
    global campaign_state

    branches = campaign_config.get("branches", [])
    branch = next((b for b in branches if b["id"] == branch_id), None)

    if not branch:
        print(f"Error: Branch '{branch_id}' not found", file=sys.stderr)
        sys.exit(1)

    campaign_state["active_branch"] = branch_id
    save_state(Path.cwd(), campaign_state)

    if output_json:
        print(json.dumps({"active_branch": branch_id}, indent=2))
    else:
        print(f"Switched to branch: {branch['name']} ({branch_id})")


def cmd_branch_create(
    branch_id: str,
    name: str,
    from_branch: Optional[str] = None,
    protagonists: Optional[str] = None,
    output_json: bool = False
) -> None:
    """Create a new branch."""
    global campaign_config

    branches = campaign_config.get("branches", [])

    if any(b["id"] == branch_id for b in branches):
        print(f"Error: Branch '{branch_id}' already exists", file=sys.stderr)
        sys.exit(1)

    new_branch = {
        "id": branch_id,
        "name": name,
        "protagonists": protagonists.split(',') if protagonists else [],
        "status": "active"
    }

    if from_branch:
        new_branch["forked_from"] = from_branch

    branches.append(new_branch)
    campaign_config["branches"] = branches
    save_config(Path.cwd(), campaign_config)

    if output_json:
        print(json.dumps(new_branch, indent=2))
    else:
        print(f"Created branch: {name} ({branch_id})")
        if from_branch:
            print(f"  Forked from: {from_branch}")


def cmd_state_show(
    character: Optional[str] = None,
    branch: Optional[str] = None,
    output_json: bool = False
) -> None:
    """Show current campaign state."""
    state = campaign_state.copy()

    # Filter by branch if specified
    if branch:
        state["active_branch"] = branch

    # Filter by character if specified
    if character:
        char_state = state.get("characters", {}).get(character, {})
        state = {"character": character, "state": char_state}

    if output_json:
        print(json.dumps(state, indent=2))
    else:
        if character:
            print(f"State for {character}:")
            char_state = state.get("state", {})
            if not char_state:
                print("  (no state recorded)")
            else:
                for key, value in char_state.items():
                    print(f"  {key}: {value}")
        else:
            print(f"Active branch: {state.get('active_branch', 'none')}")
            chars = state.get("characters", {})
            if chars:
                print(f"\nCharacter states ({len(chars)}):")
                for char_id, char_state in chars.items():
                    count = len(char_state)
                    word = "field" if count == 1 else "fields"
                    print(f"  {char_id}: {count} {word}")


def cmd_state_set(
    characters: str,
    field: str,
    value: str,
    reason: str,
    session: Optional[str] = None,
    output_json: bool = False
) -> None:
    """Set state for one or more characters (comma-separated)."""
    global campaign_state

    if "characters" not in campaign_state:
        campaign_state["characters"] = {}

    # Split comma-separated characters, filtering empty strings
    char_list = [c.strip() for c in characters.split(',') if c.strip()]
    results = []

    # Check if characters exist (warn if not, but proceed)
    from lib import discover_data
    existing_chars = discover_data("characters", Path.cwd(), on_warning=lambda x: None)
    existing_char_keys_lower = {c.lower() for c in existing_chars.keys()}
    for character in char_list:
        if character.lower() not in existing_char_keys_lower:
            print(f"Note: No character file found for '{character}'", file=sys.stderr)

    changelog = load_changelog(Path.cwd())

    for character in char_list:
        if character not in campaign_state["characters"]:
            campaign_state["characters"][character] = {}

        old_value = campaign_state["characters"][character].get(field)
        campaign_state["characters"][character][field] = value

        # Record in changelog
        entry = changelog.add(
            session=session or "current",
            character=character,
            tier="state",
            field=field,
            from_value=old_value,
            to_value=value,
            reason=reason,
            branch=campaign_state.get("active_branch")
        )

        results.append({
            "character": character,
            "field": field,
            "value": value,
            "change_id": entry.id
        })

    if results:
        save_state(Path.cwd(), campaign_state)

    if output_json:
        print(json.dumps(results, indent=2))
    else:
        for r in results:
            print(f"Set {r['character']}.{r['field']} = {r['value']}")
        if results:
            print(f"Changes logged: {len(results)}")


def cmd_state_delete(
    characters: str,
    field: str,
    reason: str,
    session: Optional[str] = None,
    output_json: bool = False
) -> None:
    """Delete state field for one or more characters (comma-separated)."""
    global campaign_state

    if "characters" not in campaign_state:
        print(f"Error: No state recorded for any character", file=sys.stderr)
        sys.exit(1)

    # Split comma-separated characters, filtering empty strings
    char_list = [c.strip() for c in characters.split(',') if c.strip()]
    results = []
    errors = []

    changelog = load_changelog(Path.cwd())

    for character in char_list:
        char_state = campaign_state["characters"].get(character)
        if char_state is None:
            errors.append(f"No state recorded for '{character}'")
            continue

        if field not in char_state:
            errors.append(f"Field '{field}' not found for '{character}'")
            continue

        old_value = char_state.pop(field)

        # Clean up empty character dict
        if not char_state:
            del campaign_state["characters"][character]

        # Record deletion in changelog
        entry = changelog.add(
            session=session or "current",
            character=character,
            tier="state",
            field=field,
            from_value=old_value,
            to_value=None,
            reason=reason,
            branch=campaign_state.get("active_branch")
        )

        results.append({
            "character": character,
            "field": field,
            "deleted": True,
            "old_value": old_value,
            "change_id": entry.id
        })

    # Save state if any changes were made
    if results:
        save_state(Path.cwd(), campaign_state)

    if output_json:
        print(json.dumps({"results": results, "errors": errors}, indent=2))
    else:
        for r in results:
            print(f"Deleted {r['character']}.{r['field']} (was: {r['old_value']})")
        if results:
            print(f"Changes logged: {len(results)}")
        for err in errors:
            print(f"Warning: {err}", file=sys.stderr)

    # Exit with error if all characters failed
    if not results and errors:
        sys.exit(1)


def cmd_changelog_show(
    character: Optional[str] = None,
    session: Optional[str] = None,
    field: Optional[str] = None,
    tier: Optional[str] = None,
    limit: int = 0,
    output_json: bool = False
) -> None:
    """Show changelog entries."""
    changelog = load_changelog(Path.cwd())

    entries = changelog.entries.copy()

    if character:
        entries = [e for e in entries if e.character.lower() == character.lower()]
    if session:
        entries = [e for e in entries if e.session.lower() == session.lower()]
    if field:
        entries = [e for e in entries if field.lower() in e.field.lower()]
    if tier:
        entries = [e for e in entries if e.tier.lower() == tier.lower()]

    if limit > 0:
        entries = entries[-limit:]

    if output_json:
        print(json.dumps([e.to_dict() for e in entries], indent=2))
    else:
        if not entries:
            print("No changelog entries found")
            return

        for entry in entries:
            print(f"[{entry.id}] {entry.character}.{entry.field}")
            print(f"  {entry.from_value} -> {entry.to_value}")
            print(f"  Reason: {entry.reason}")
            print(f"  Session: {entry.session}, Tier: {entry.tier}")
            print()


# Directories to include in export
EXPORT_DIRS = ["campaign", "characters", "locations", "memories", "stories", "namesets"]


def cmd_export(
    output_path: Optional[str] = None,
    output_json: bool = False
) -> None:
    """Export campaign to a zip archive."""
    search_root = Path.cwd()

    # Generate default filename from campaign name and date
    campaign_name = campaign_config.get("campaign", "campaign")
    # Sanitize name for filename
    safe_name = "".join(c if c.isalnum() or c in "-_" else "-" for c in campaign_name.lower())
    date_str = datetime.now().strftime("%Y%m%d")
    default_filename = f"{safe_name}-{date_str}.zip"

    zip_path = Path(output_path) if output_path else search_root / default_filename

    # Count files for manifest
    manifest = {
        "campaign": campaign_name,
        "exported": datetime.now().isoformat(),
        "counts": {}
    }

    skipped_files = []

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for dir_name in EXPORT_DIRS:
            dir_path = search_root / dir_name
            if not dir_path.exists():
                continue

            count = 0
            for json_file in dir_path.glob("*.json"):
                try:
                    # Validate JSON is readable before adding to archive
                    with open(json_file, encoding='utf-8-sig') as f:
                        json.load(f)

                    # Use forward slashes for zip paths (cross-platform)
                    arc_name = f"{dir_name}/{json_file.name}"
                    zf.write(json_file, arc_name)
                    count += 1
                except json.JSONDecodeError as e:
                    skipped_files.append((json_file, f"Invalid JSON: {e}"))
                except (IOError, OSError) as e:
                    skipped_files.append((json_file, f"Read error: {e}"))

            if count > 0:
                manifest["counts"][dir_name] = count

        # Write manifest
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))

    # Report skipped files
    if skipped_files:
        print(f"Warning: {len(skipped_files)} file(s) skipped due to errors:", file=sys.stderr)
        for path, error in skipped_files:
            print(f"  - {path.name}: {error}", file=sys.stderr)
        print(file=sys.stderr)

    if output_json:
        result = {
            "output": str(zip_path),
            "manifest": manifest,
            "skipped": [{"file": str(p), "error": e} for p, e in skipped_files] if skipped_files else []
        }
        print(json.dumps(result, indent=2))
    else:
        print(f"Exported to: {zip_path}")
        print(f"\nContents:")
        from collections import Counter
        skipped_counts_by_dir = Counter(p.parent.name for p, _ in skipped_files)
        for dir_name, count in manifest["counts"].items():
            skipped_in_dir = skipped_counts_by_dir.get(dir_name, 0)
            if skipped_in_dir > 0:
                print(f"  {dir_name}: {count} files ({skipped_in_dir} skipped)")
            else:
                print(f"  {dir_name}: {count} files")
        total = sum(manifest["counts"].values())
        print(f"\nTotal: {total} files")


def cmd_import(
    zip_path: str,
    into_path: Optional[str] = None,
    output_json: bool = False
) -> None:
    """Import campaign from a zip archive."""
    source = Path(zip_path)
    if not source.exists():
        print(f"Error: File not found: {zip_path}", file=sys.stderr)
        sys.exit(1)

    target = Path(into_path) if into_path else Path.cwd()

    # Warn if target is not empty
    if target.exists() and any(f for f in target.iterdir() if f.resolve() != source.resolve()):
        print(f"Warning: Target directory '{target}' is not empty. Files may be overwritten.", file=sys.stderr)

    # Read manifest if present
    manifest = None
    try:
        with zipfile.ZipFile(source, 'r') as zf:
            if "manifest.json" in zf.namelist():
                manifest = json.loads(zf.read("manifest.json").decode('utf-8'))

            # Validate structure
            has_config = any(name.startswith("campaign/") for name in zf.namelist())
            if not has_config:
                print("Warning: No campaign/ directory found in archive", file=sys.stderr)

            # Extract files safely, preventing path traversal (Zip Slip)
            for member in zf.infolist():
                if member.filename.startswith('/') or '..' in member.filename:
                    print(f"Warning: Skipping unsafe path: {member.filename}", file=sys.stderr)
                    continue
                zf.extract(member, target)
    except zipfile.BadZipFile:
        print(f"Error: Invalid zip file: {zip_path}", file=sys.stderr)
        sys.exit(1)

    if output_json:
        result = {
            "source": str(source),
            "target": str(target),
            "manifest": manifest
        }
        print(json.dumps(result, indent=2))
    else:
        print(f"Imported from: {source}")
        print(f"Into: {target}")
        if manifest:
            print(f"\nCampaign: {manifest.get('campaign', 'Unknown')}")
            print(f"Originally exported: {manifest.get('exported', 'Unknown')}")
            print(f"\nContents:")
            for dir_name, count in manifest.get("counts", {}).items():
                print(f"  {dir_name}: {count} files")


def main():
    global campaign_config, campaign_state

    search_root = Path.cwd()
    campaign_config = load_config(search_root)
    campaign_state = load_state(search_root)

    if len(sys.argv) < 2 or sys.argv[1] in ('--help', '-h'):
        print("Usage: python campaign.py <command> [options]")
        print("\nCommands:")
        print("  init <name>                    Initialize new campaign")
        print("  show                           Show campaign config")
        print("  export [--output FILE.zip]     Export campaign to zip")
        print("  import <file.zip> [--into DIR] Import campaign from zip")
        print("  branch list                    List all branches")
        print("  branch switch <id>             Switch active branch")
        print("  branch create <id> <name>      Create new branch")
        print("  state show [--character X] [--branch Y]  Show campaign state")
        print("  state set <chars> <field> <val>   Set character state")
        print("  state delete <chars> <field>      Delete character state field")
        print("  changelog show [filters...]    Show changelog entries")
        print("\nState commands accept comma-separated characters:")
        print("  state set kira,dex,tam location \"station\" --reason \"Docked\"")
        print("  state delete kira,dex condition.wounded --reason \"Healed\"")
        print("\nGlobal options:")
        print("  --json                         Output as JSON")
        sys.exit(0 if len(sys.argv) > 1 and sys.argv[1] in ('--help', '-h') else 1)

    # Commands that use subcommands
    SUBCOMMAND_CMDS = {'branch', 'state', 'changelog'}

    command = sys.argv[1]
    subcommand = None

    if command in SUBCOMMAND_CMDS and len(sys.argv) > 2 and not sys.argv[2].startswith("--"):
        subcommand = sys.argv[2]
        i = 3
    else:
        i = 2

    # Parse options
    opts = {
        "name": None,
        "branch_id": None,
        "calendar_type": "offset",
        "from_branch": None,
        "branch": None,
        "protagonists": None,
        "character": None,
        "field": None,
        "value": None,
        "reason": None,
        "session": None,
        "tier": None,
        "limit": 0,
        "output": None,
        "into": None,
        "output_json": False,
    }

    positional = []
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == "--json":
            opts["output_json"] = True
            i += 1
        elif arg == "--calendar" and i + 1 < len(sys.argv):
            opts["calendar_type"] = sys.argv[i + 1]
            i += 2
        elif arg == "--from" and i + 1 < len(sys.argv):
            opts["from_branch"] = sys.argv[i + 1]
            i += 2
        elif arg == "--branch" and i + 1 < len(sys.argv):
            opts["branch"] = sys.argv[i + 1]
            i += 2
        elif arg == "--protagonists" and i + 1 < len(sys.argv):
            opts["protagonists"] = sys.argv[i + 1]
            i += 2
        elif arg == "--character" and i + 1 < len(sys.argv):
            opts["character"] = sys.argv[i + 1]
            i += 2
        elif arg == "--session" and i + 1 < len(sys.argv):
            opts["session"] = sys.argv[i + 1]
            i += 2
        elif arg == "--field" and i + 1 < len(sys.argv):
            opts["field"] = sys.argv[i + 1]
            i += 2
        elif arg == "--tier" and i + 1 < len(sys.argv):
            opts["tier"] = sys.argv[i + 1]
            i += 2
        elif arg == "--reason" and i + 1 < len(sys.argv):
            opts["reason"] = sys.argv[i + 1]
            i += 2
        elif arg == "--limit" and i + 1 < len(sys.argv):
            opts["limit"] = int(sys.argv[i + 1])
            i += 2
        elif arg == "--output" and i + 1 < len(sys.argv):
            opts["output"] = sys.argv[i + 1]
            i += 2
        elif arg == "--into" and i + 1 < len(sys.argv):
            opts["into"] = sys.argv[i + 1]
            i += 2
        elif not arg.startswith("--"):
            positional.append(arg)
            i += 1
        else:
            print(f"Unknown option: {arg}", file=sys.stderr)
            sys.exit(1)

    # Execute command
    if command == "init":
        if not positional:
            print("Error: campaign name required", file=sys.stderr)
            sys.exit(1)
        cmd_init(positional[0], opts["calendar_type"], opts["output_json"])

    elif command == "show":
        cmd_show(opts["output_json"])

    elif command == "export":
        cmd_export(opts["output"], opts["output_json"])

    elif command == "import":
        if not positional:
            print("Error: zip file path required", file=sys.stderr)
            sys.exit(1)
        cmd_import(positional[0], opts["into"], opts["output_json"])

    elif command == "branch":
        if subcommand == "list":
            cmd_branch_list(opts["output_json"])
        elif subcommand == "switch":
            if not positional:
                print("Error: branch ID required", file=sys.stderr)
                sys.exit(1)
            cmd_branch_switch(positional[0], opts["output_json"])
        elif subcommand == "create":
            if len(positional) < 2:
                print("Error: branch ID and name required", file=sys.stderr)
                sys.exit(1)
            cmd_branch_create(
                positional[0], positional[1],
                opts["from_branch"], opts["protagonists"],
                opts["output_json"]
            )
        else:
            print(f"Unknown branch subcommand: {subcommand}", file=sys.stderr)
            sys.exit(1)

    elif command == "state":
        if subcommand == "show":
            cmd_state_show(opts["character"], opts["branch"], opts["output_json"])
        elif subcommand == "set":
            if len(positional) < 3:
                print("Error: character, field, and value required", file=sys.stderr)
                sys.exit(1)
            if not opts["reason"]:
                print("Error: --reason is required for state changes", file=sys.stderr)
                sys.exit(1)
            cmd_state_set(
                positional[0], positional[1], positional[2],
                opts["reason"], opts["session"], opts["output_json"]
            )
        elif subcommand == "delete":
            if len(positional) < 2:
                print("Error: character and field required", file=sys.stderr)
                sys.exit(1)
            if not opts["reason"]:
                print("Error: --reason is required for state changes", file=sys.stderr)
                sys.exit(1)
            cmd_state_delete(
                positional[0], positional[1],
                opts["reason"], opts["session"], opts["output_json"]
            )
        else:
            print(f"Unknown state subcommand: {subcommand}", file=sys.stderr)
            sys.exit(1)

    elif command == "changelog":
        if subcommand == "show":
            cmd_changelog_show(
                opts["character"], opts["session"], opts["field"],
                opts["tier"], opts["limit"], opts["output_json"]
            )
        else:
            print(f"Unknown changelog subcommand: {subcommand}", file=sys.stderr)
            sys.exit(1)

    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
