#!/usr/bin/env python3
"""Faction tool for solo RPG games. Provides faction data management."""

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any

from lib import discover_data, find_item, load_changelog, save_item, find_source_file, delete_item_file


# Faction storage
factions: Dict[str, Dict] = {}


def discover_factions(search_root: Path) -> None:
    """Discover faction files from factions/ folder."""
    global factions
    factions = discover_data("factions", search_root)


def filter_factions(
    faction_type: Optional[str] = None,
    tag: Optional[str] = None
) -> List[Dict]:
    """Filter factions by type or tag."""
    result = list(factions.values())

    if faction_type:
        type_lower = faction_type.lower()
        result = [f for f in result if f.get("type", "").lower() == type_lower]

    if tag is not None:
        if not tag.strip():
            print("Error: --tag cannot be empty", file=sys.stderr)
            sys.exit(1)
        tag_lower = tag.lower()
        result = [f for f in result if tag_lower in [t.lower() for t in f.get("tags", [])]]

    return result


def format_minimal(faction: Dict) -> str:
    """Format faction's minimal profile."""
    lines = []
    name = faction.get("name", faction.get("id", "Unknown"))
    lines.append(f"# {name}")

    faction_type = faction.get("type", "")
    if faction_type:
        lines.append(f"**Type:** {faction_type}")

    minimal = faction.get("minimal", {})
    if minimal.get("essence"):
        lines.append(f"**Essence:** {minimal['essence']}")
    if minimal.get("current_status"):
        lines.append(f"**Status:** {minimal['current_status']}")

    tags = faction.get("tags", [])
    if tags:
        lines.append(f"**Tags:** {', '.join(tags)}")

    # Show what's available
    available = []
    if faction.get("full"):
        available.append("--depth full")
    if faction.get("sections"):
        section_names = list(faction["sections"].keys())
        available.append(f"sections: {', '.join(section_names)}")

    if available:
        lines.append(f"\n[Available: {'; '.join(available)}]")

    return "\n".join(lines)


def format_full(faction: Dict) -> str:
    """Format faction's full profile."""
    lines = [format_minimal(faction)]

    full = faction.get("full", {})

    if full.get("description"):
        lines.append(f"\n## Description\n{full['description']}")

    if full.get("history"):
        lines.append(f"\n## History\n{full['history']}")

    if full.get("goals"):
        lines.append(f"\n## Goals\n{full['goals']}")

    if full.get("structure"):
        lines.append(f"\n## Structure\n{full['structure']}")

    if full.get("resources"):
        lines.append(f"\n## Resources\n{full['resources']}")

    if full.get("notable_members"):
        lines.append("\n## Notable Members")
        for member in full["notable_members"]:
            if isinstance(member, dict):
                name = member.get("name", "")
                role = member.get("role", "")
                lines.append(f"- **{name}:** {role}")
            else:
                lines.append(f"- {member}")

    # Handle any additional fields in full
    known_fields = {"description", "history", "goals", "structure", "resources", "notable_members"}
    for key, value in full.items():
        if key not in known_fields:
            lines.append(f"\n## {key.replace('_', ' ').title()}\n{value}")

    return "\n".join(lines)


def format_value(value: Any, indent: int = 0) -> List[str]:
    """Recursively format a value, handling nested dicts and lists."""
    prefix = "  " * indent
    lines = []

    if isinstance(value, dict):
        for k, v in value.items():
            if isinstance(v, dict):
                lines.append(f"{prefix}**{k}:**")
                lines.extend(format_value(v, indent + 1))
            elif isinstance(v, list):
                lines.append(f"{prefix}**{k}:**")
                for item in v:
                    if isinstance(item, dict):
                        lines.append(f"{prefix}  -")
                        lines.extend(format_value(item, indent + 2))
                    else:
                        lines.append(f"{prefix}  - {item}")
            else:
                lines.append(f"{prefix}**{k}:** {v}")
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                lines.append(f"{prefix}-")
                lines.extend(format_value(item, indent + 1))
            else:
                lines.append(f"{prefix}- {item}")
    else:
        lines.append(f"{prefix}{value}")

    return lines


def format_section(faction: Dict, section_name: str) -> str:
    """Format a specific section of a faction."""
    name = faction.get("name", faction.get("id", "Unknown"))
    sections = faction.get("sections", {})

    if section_name not in sections:
        return f"Section '{section_name}' not found for {name}"

    section = sections[section_name]
    lines = [f"# {name} - {section_name.replace('_', ' ').title()}"]

    if isinstance(section, dict):
        for key, value in section.items():
            if isinstance(value, list):
                lines.append(f"\n**{key}:**")
                for item in value:
                    if isinstance(item, dict):
                        lines.extend(format_value(item, 1))
                    else:
                        lines.append(f"- {item}")
            elif isinstance(value, dict):
                lines.append(f"\n**{key}:**")
                lines.extend(format_value(value, 1))
            else:
                lines.append(f"**{key}:** {value}")
    elif isinstance(section, list):
        for item in section:
            if isinstance(item, dict):
                # Timeline-style entries
                era = item.get("era", "")
                event = item.get("event", str(item))
                lines.append(f"- **{era}:** {event}")
            else:
                lines.append(f"- {item}")
    else:
        lines.append(str(section))

    return "\n".join(lines)


def cmd_list(
    faction_type: Optional[str] = None,
    tag: Optional[str] = None,
    short: bool = False
) -> None:
    """List factions (names only by default, or short profiles with --short)."""
    filtered = filter_factions(faction_type, tag)

    if not filtered:
        print("No factions found matching criteria")
        return

    # Sort by name (null-safe: handles both missing keys and null values)
    filtered.sort(key=lambda f: (f.get("name") or f.get("id") or ""))

    if short:
        # Show minimal profiles
        for faction in filtered:
            print(format_minimal(faction))
            print()
    else:
        # Just names
        print("Factions:")
        for faction in filtered:
            name = faction.get("name", faction.get("id", "Unknown"))
            faction_type = faction.get("type", "")
            tags = faction.get("tags", [])
            type_str = f" ({faction_type})" if faction_type else ""
            tag_str = f" [{', '.join(tags)}]" if tags else ""
            print(f"  - {name}{type_str}{tag_str}")

        print(f"\nTotal: {len(filtered)} factions")
        print("Use --short for minimal profiles, or 'get <name>' for details")


def cmd_get(
    faction_name: str,
    depth: str = "minimal",
    section: Optional[str] = None
) -> None:
    """Get a faction's profile at specified depth."""
    faction = find_item(factions, faction_name, "Faction")

    if section:
        print(format_section(faction, section))
    elif depth == "full":
        print(format_full(faction))
    else:
        print(format_minimal(faction))


def cmd_sections(faction_name: str) -> None:
    """List available sections for a faction."""
    faction = find_item(factions, faction_name, "Faction")
    name = faction.get("name", faction.get("id", "Unknown"))
    sections = faction.get("sections", {})

    if not sections:
        print(f"{name} has no additional sections")
        return

    print(f"Sections available for {name}:")
    for section_name in sections.keys():
        print(f"  - {section_name}")


def cmd_show(faction_name: str) -> None:
    """Show raw JSON for a faction (debugging)."""
    faction = find_item(factions, faction_name, "Faction")
    print(json.dumps(faction, indent=2))


def cmd_create(
    faction_id: str,
    name: str,
    faction_type: str,
    essence: str,
    tags: Optional[str] = None,
    output_json: bool = False
) -> None:
    """Create a new faction with minimal profile."""
    search_root = Path.cwd()

    # Check if ID already exists
    if faction_id in factions:
        print(f"Error: Faction '{faction_id}' already exists", file=sys.stderr)
        sys.exit(1)

    # Build faction dict
    faction = {
        "id": faction_id,
        "name": name,
        "type": faction_type,
        "tags": [],
        "minimal": {
            "essence": essence,
            "current_status": "active"
        }
    }

    if tags:
        faction["tags"] = [t.strip() for t in tags.split(',')]

    # Save to file
    path = save_item("factions", faction, search_root)

    if output_json:
        print(json.dumps(faction, indent=2))
    else:
        print(f"Created faction: {faction_id}")
        print(f"  Name: {name}")
        print(f"  Type: {faction_type}")
        print(f"  Saved to: {path}")


def cmd_update(
    faction_name: str,
    field: str,
    value: str,
    reason: str,
    session: Optional[str] = None,
    output_json: bool = False
) -> None:
    """Update a faction field."""
    search_root = Path.cwd()

    faction = find_item(factions, faction_name, "Faction")
    faction_id = faction.get("id", faction_name)

    # Navigate to the field and get old value
    parts = field.split('.')
    target = faction
    for part in parts[:-1]:
        if part not in target:
            target[part] = {}
        target = target[part]

    final_key = parts[-1]
    old_value = target.get(final_key)

    # Try to parse value as JSON (for arrays/objects)
    parsed_value = value
    if value.startswith('{') or value.startswith('['):
        try:
            parsed_value = json.loads(value)
        except json.JSONDecodeError:
            pass  # Keep as string

    # Update the value
    target[final_key] = parsed_value

    # Find the faction file and save
    faction_file = find_source_file("factions", faction_id, search_root)
    if faction_file:
        with open(faction_file, 'w', encoding='utf-8') as f:
            json.dump(faction, f, indent=2)

    # Record in changelog
    changelog = load_changelog(search_root)
    entry = changelog.add(
        session=session or "current",
        character=faction_id,  # Using character field for faction ID
        tier="development",
        field=field,
        from_value=old_value,
        to_value=parsed_value,
        reason=reason
    )

    if output_json:
        print(json.dumps({
            "faction": faction_id,
            "field": field,
            "from": old_value,
            "to": parsed_value,
            "change_id": entry.id
        }, indent=2))
    else:
        name = faction.get("name", faction_id)
        print(f"Updated {name}.{field}")
        print(f"  {old_value} -> {parsed_value}")
        print(f"Change logged: {entry.id}")


def find_faction_references(faction_id: str, search_root: Path) -> Dict[str, int]:
    """Find references to a faction in logs and memories."""
    faction_lower = faction_id.lower()

    def _count_refs(dir_path: Path, extractor) -> int:
        """Helper to find references in a directory of JSON files."""
        count = 0
        if not dir_path.exists():
            return 0

        for path in dir_path.glob("*.json"):
            try:
                with open(path, encoding='utf-8-sig') as f:
                    data = json.load(f)
                    items = data if isinstance(data, list) else [data]
                    for item in items:
                        if any(c.lower() == faction_lower for c in extractor(item)):
                            count += 1
            except (OSError, json.JSONDecodeError) as e:
                print(f"Warning: Could not parse {path} for faction references: {e}", file=sys.stderr)
        return count

    log_refs = _count_refs(
        search_root / "campaign" / "logs",
        lambda item: item.get("factions", {}).keys() if isinstance(item.get("factions"), dict) else []
    )

    mem_refs = _count_refs(
        search_root / "memories",
        lambda item: item.get("connections", {}).get("factions", [])
    )

    return {"logs": log_refs, "memories": mem_refs}


def cmd_delete(faction_id: str, force: bool = False) -> None:
    """Delete a faction."""
    search_root = Path.cwd()

    # Check faction exists
    faction = find_item(factions, faction_id, "Faction")
    actual_id = faction.get("id", faction_id)

    # Check for references unless --force is used
    if not force:
        refs = find_faction_references(actual_id, search_root)
        total_refs = refs["logs"] + refs["memories"]
        if total_refs > 0:
            print(f"Warning: Faction '{actual_id}' is referenced in:", file=sys.stderr)
            if refs["logs"] > 0:
                print(f"  - {refs['logs']} log entries", file=sys.stderr)
            if refs["memories"] > 0:
                print(f"  - {refs['memories']} memories", file=sys.stderr)
            print(f"\nUse --force to delete anyway.", file=sys.stderr)
            sys.exit(1)

    # Delete the file
    if delete_item_file("factions", actual_id, search_root):
        print(f"Deleted faction: {actual_id}")
    else:
        print(f"Error: Could not find file for faction '{actual_id}'", file=sys.stderr)
        sys.exit(1)


# Stub commands for future implementation
def cmd_members(faction_name: str) -> None:
    """Show faction members."""
    print("Not implemented yet")


def cmd_economy(faction_name: str) -> None:
    """Show faction economy."""
    print("Not implemented yet")


def cmd_tree(faction_name: str) -> None:
    """Show faction hierarchy tree."""
    print("Not implemented yet")


def cmd_relationships(faction_name: str) -> None:
    """Show faction relationships."""
    print("Not implemented yet")


def cmd_add_member(faction_name: str, character_name: str) -> None:
    """Add a member to a faction."""
    print("Not implemented yet")


def cmd_remove_member(faction_name: str, character_name: str) -> None:
    """Remove a member from a faction."""
    print("Not implemented yet")


def main():
    # Find search root (current directory or script parent)
    search_root = Path.cwd()

    # Load factions
    discover_factions(search_root)

    # Parse command line
    if len(sys.argv) < 2 or sys.argv[1] in ('--help', '-h'):
        print("Usage: python factions.py <command> [options]")
        print("\nCommands:")
        print("  create <id> --name N --type T --essence E ...")
        print("                                 Create a new faction")
        print("  delete <id> [--force]          Delete a faction")
        print("  list [filters...]              List faction names")
        print("  list --short [filters...]      List with minimal profiles")
        print("  get <name>                     Get minimal profile")
        print("  get <name> --depth full        Get full profile")
        print("  get <name> --section NAME      Get specific section")
        print("  sections <name>                List available sections")
        print("  show <name>                    Show raw JSON")
        print("  update <name> --field FIELD --value VAL --reason R")
        print("                                 Update faction field (dot notation)")
        print("\nStub commands (not yet implemented):")
        print("  members <name>                 Show faction members")
        print("  economy <name>                 Show faction economy")
        print("  tree <name>                    Show faction hierarchy")
        print("  relationships <name>           Show faction relationships")
        print("  add-member <faction> <char>    Add member to faction")
        print("  remove-member <faction> <char> Remove member from faction")
        print("\nCreate options:")
        print("  --name NAME                    Faction display name (required)")
        print("  --type TYPE                    Faction type: fleet|house|organization|military|other (required)")
        print("  --essence TEXT                 Core essence, 35 words max (required)")
        print("  --tags TAGS                    Comma-separated tags")
        print("  --json                         Output as JSON")
        print("\nFilters (for list):")
        print("  --type TYPE                    Filter by type")
        print("  --tag NAME                     Filter by tag")
        print("\nUpdate options:")
        print("  --field FIELD                  Field to update (dot notation, e.g., full.goals)")
        print("  --value VALUE                  New value (JSON arrays/objects auto-parsed)")
        print("  --reason REASON                Reason for change")
        print("  --session NAME                 Session identifier (optional)")
        print("  --json                         Output as JSON")
        print("\n  Examples:")
        print("    --value 'Simple string'")
        print("    --value '[\"item1\", \"item2\"]'   # Parsed as JSON array")
        print("    --value '{\"key\": \"val\"}'       # Parsed as JSON object")
        sys.exit(0 if len(sys.argv) > 1 and sys.argv[1] in ('--help', '-h') else 1)

    command = sys.argv[1]

    # Parse options
    faction_type = None
    tag = None
    short = False
    depth = "minimal"
    section = None
    field = None
    faction_name = None
    value = None
    reason = None
    session_name = None
    output_json = False
    force = False
    # Create-specific options
    name = None
    essence = None
    tags_list = None
    # Second positional for add-member/remove-member
    character_name = None

    i = 2
    positional_count = 0
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == "--type" and i + 1 < len(sys.argv):
            faction_type = sys.argv[i + 1]
            i += 2
        elif arg == "--tag" and i + 1 < len(sys.argv):
            tag = sys.argv[i + 1]
            i += 2
        elif arg == "--short":
            short = True
            i += 1
        elif arg == "--depth" and i + 1 < len(sys.argv):
            depth = sys.argv[i + 1]
            i += 2
        elif arg == "--section" and i + 1 < len(sys.argv):
            section = sys.argv[i + 1]
            i += 2
        elif arg == "--field" and i + 1 < len(sys.argv):
            field = sys.argv[i + 1]
            i += 2
        elif arg == "--value" and i + 1 < len(sys.argv):
            value = sys.argv[i + 1]
            i += 2
        elif arg == "--reason" and i + 1 < len(sys.argv):
            reason = sys.argv[i + 1]
            i += 2
        elif arg == "--session" and i + 1 < len(sys.argv):
            session_name = sys.argv[i + 1]
            i += 2
        elif arg == "--json":
            output_json = True
            i += 1
        elif arg == "--force":
            force = True
            i += 1
        elif arg == "--name" and i + 1 < len(sys.argv):
            name = sys.argv[i + 1]
            i += 2
        elif arg == "--essence" and i + 1 < len(sys.argv):
            essence = sys.argv[i + 1]
            i += 2
        elif arg == "--tags" and i + 1 < len(sys.argv):
            tags_list = sys.argv[i + 1]
            i += 2
        elif not arg.startswith("--"):
            # Positional argument
            if positional_count == 0:
                faction_name = arg
            elif positional_count == 1:
                character_name = arg
            positional_count += 1
            i += 1
        else:
            print(f"Unknown option: {arg}", file=sys.stderr)
            sys.exit(1)

    # Execute command
    if command == "create":
        if not faction_name:
            print("Error: faction id required for create", file=sys.stderr)
            sys.exit(1)
        if not name:
            print("Error: --name required for create", file=sys.stderr)
            sys.exit(1)
        if not faction_type:
            print("Error: --type required for create", file=sys.stderr)
            sys.exit(1)
        if not essence:
            print("Error: --essence required for create", file=sys.stderr)
            sys.exit(1)
        cmd_create(
            faction_id=faction_name,
            name=name,
            faction_type=faction_type,
            essence=essence,
            tags=tags_list,
            output_json=output_json
        )
    elif command == "delete":
        if not faction_name:
            print("Error: faction id required for delete", file=sys.stderr)
            sys.exit(1)
        cmd_delete(faction_name, force)
    elif command == "list":
        cmd_list(faction_type, tag, short)
    elif command == "get":
        if not faction_name:
            print("Error: faction name is required for 'get' command", file=sys.stderr)
            sys.exit(1)
        cmd_get(faction_name, depth, section)
    elif command == "sections":
        if not faction_name:
            print("Error: faction name is required for 'sections' command", file=sys.stderr)
            sys.exit(1)
        cmd_sections(faction_name)
    elif command == "show":
        if not faction_name:
            print("Error: faction name is required for 'show' command", file=sys.stderr)
            sys.exit(1)
        cmd_show(faction_name)
    elif command == "update":
        if not faction_name:
            print("Error: faction name required", file=sys.stderr)
            sys.exit(1)
        if not field:
            print("Error: --field required", file=sys.stderr)
            sys.exit(1)
        if not value:
            print("Error: --value required", file=sys.stderr)
            sys.exit(1)
        if not reason:
            print("Error: --reason required", file=sys.stderr)
            sys.exit(1)
        cmd_update(faction_name, field, value, reason, session_name, output_json)
    elif command == "members":
        if not faction_name:
            print("Error: faction name required", file=sys.stderr)
            sys.exit(1)
        cmd_members(faction_name)
    elif command == "economy":
        if not faction_name:
            print("Error: faction name required", file=sys.stderr)
            sys.exit(1)
        cmd_economy(faction_name)
    elif command == "tree":
        if not faction_name:
            print("Error: faction name required", file=sys.stderr)
            sys.exit(1)
        cmd_tree(faction_name)
    elif command == "relationships":
        if not faction_name:
            print("Error: faction name required", file=sys.stderr)
            sys.exit(1)
        cmd_relationships(faction_name)
    elif command == "add-member":
        if not faction_name:
            print("Error: faction name required", file=sys.stderr)
            sys.exit(1)
        if not character_name:
            print("Error: character name required", file=sys.stderr)
            sys.exit(1)
        cmd_add_member(faction_name, character_name)
    elif command == "remove-member":
        if not faction_name:
            print("Error: faction name required", file=sys.stderr)
            sys.exit(1)
        if not character_name:
            print("Error: character name required", file=sys.stderr)
            sys.exit(1)
        cmd_remove_member(faction_name, character_name)
    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
