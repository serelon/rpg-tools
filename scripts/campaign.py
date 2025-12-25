#!/usr/bin/env python3
"""Campaign management tool for config, branches, state, and changelog."""

import json
import sys
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
            with open(config_path, encoding='utf-8') as f:
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
            with open(state_path, encoding='utf-8') as f:
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
                    print(f"  {char_id}: {len(char_state)} fields")


def cmd_state_set(
    character: str,
    field: str,
    value: str,
    reason: str,
    session: Optional[str] = None,
    output_json: bool = False
) -> None:
    """Set a character's session state."""
    global campaign_state

    if "characters" not in campaign_state:
        campaign_state["characters"] = {}

    if character not in campaign_state["characters"]:
        campaign_state["characters"][character] = {}

    old_value = campaign_state["characters"][character].get(field)
    campaign_state["characters"][character][field] = value

    save_state(Path.cwd(), campaign_state)

    # Also record in changelog
    changelog = load_changelog(Path.cwd())
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

    if output_json:
        print(json.dumps({
            "character": character,
            "field": field,
            "value": value,
            "change_id": entry.id
        }, indent=2))
    else:
        print(f"Set {character}.{field} = {value}")
        print(f"Change logged: {entry.id}")


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


def main():
    global campaign_config, campaign_state

    search_root = Path.cwd()
    campaign_config = load_config(search_root)
    campaign_state = load_state(search_root)

    if len(sys.argv) < 2:
        print("Usage: python campaign.py <command> [options]")
        print("\nCommands:")
        print("  init <name>                    Initialize new campaign")
        print("  show                           Show campaign config")
        print("  branch list                    List all branches")
        print("  branch switch <id>             Switch active branch")
        print("  branch create <id> <name>      Create new branch")
        print("  state show [--character X] [--branch Y]  Show campaign state")
        print("  state set <char> <field> <val> Set character state")
        print("  changelog show [filters...]    Show changelog entries")
        print("\nGlobal options:")
        print("  --json                         Output as JSON")
        sys.exit(1)

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
