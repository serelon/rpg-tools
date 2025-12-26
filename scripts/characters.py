#!/usr/bin/env python3
"""Character tool for solo RPG games. Provides incremental character data loading."""

import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any

from lib import discover_data, find_item, load_changelog, save_item, delete_item_file


# Character storage
characters: Dict[str, Dict] = {}


def discover_characters(search_root: Path) -> None:
    """Discover character files from characters/ folder."""
    global characters
    characters = discover_data("characters", search_root)


def filter_characters(
    faction: Optional[str] = None,
    subfaction: Optional[str] = None,
    tag: Optional[str] = None,
    location: Optional[str] = None,
    branch: Optional[str] = None
) -> List[Dict]:
    """Filter characters by faction, subfaction, tag, location, or branch."""
    result = list(characters.values())

    if faction:
        faction_lower = faction.lower()
        result = [c for c in result if c.get("faction", "").lower() == faction_lower]

    if subfaction:
        subfaction_lower = subfaction.lower()
        result = [c for c in result if c.get("subfaction", "").lower() == subfaction_lower]

    if tag is not None:
        if not tag.strip():
            print("Error: --tag cannot be empty", file=sys.stderr)
            sys.exit(1)
        tag_lower = tag.lower()
        result = [c for c in result if tag_lower in [t.lower() for t in c.get("tags", [])]]

    if location:
        # Check current location from campaign state
        state_path = Path.cwd() / "campaign" / "state.json"
        if state_path.exists():
            try:
                with open(state_path, encoding='utf-8-sig') as f:
                    state = json.load(f)
                    char_states = state.get("characters", {})
                    location_lower = location.lower()
                    result = [c for c in result
                             if char_states.get(c.get("id", ""), {}).get("location", "").lower() == location_lower]
            except (FileNotFoundError, json.JSONDecodeError, KeyError):
                pass

    if branch:
        # Filter by branch protagonists from campaign config
        config_path = Path.cwd() / "campaign" / "config.json"
        if config_path.exists():
            try:
                with open(config_path, encoding='utf-8-sig') as f:
                    config = json.load(f)
                    branches = config.get("branches", [])
                    branch_data = next((b for b in branches if b["id"].lower() == branch.lower()), None)
                    if branch_data:
                        protagonists = [p.lower() for p in branch_data.get("protagonists", [])]
                        result = [c for c in result if c.get("id", "").lower() in protagonists]
            except (FileNotFoundError, json.JSONDecodeError, KeyError):
                pass

    return result


def format_minimal(char: Dict) -> str:
    """Format character's minimal profile."""
    lines = []
    name = char.get("name", char.get("id", "Unknown"))
    lines.append(f"# {name}")

    minimal = char.get("minimal", {})
    if minimal.get("role"):
        lines.append(f"**Role:** {minimal['role']}")
    if minimal.get("essence"):
        lines.append(f"**Essence:** {minimal['essence']}")
    if minimal.get("voice"):
        lines.append(f"**Voice:** \"{minimal['voice']}\"")

    # Show what's available
    available = []
    if char.get("full"):
        available.append("--depth full")
    if char.get("sections"):
        section_names = list(char["sections"].keys())
        available.append(f"sections: {', '.join(section_names)}")

    if available:
        lines.append(f"\n[Available: {'; '.join(available)}]")

    return "\n".join(lines)


def format_full(char: Dict) -> str:
    """Format character's full profile."""
    lines = [format_minimal(char)]

    full = char.get("full", {})

    if full.get("appearance"):
        lines.append(f"\n## Appearance\n{full['appearance']}")

    if full.get("personality"):
        lines.append(f"\n## Personality\n{full['personality']}")

    if full.get("background"):
        lines.append(f"\n## Background\n{full['background']}")

    if full.get("motivations"):
        lines.append(f"\n## Motivations\n{full['motivations']}")

    if full.get("voice_samples"):
        lines.append("\n## Voice Samples")
        for sample in full["voice_samples"]:
            if isinstance(sample, dict):
                context = sample.get("context", "")
                line = sample.get("line", "")
                lines.append(f"- **{context}:** \"{line}\"")
            else:
                lines.append(f"- \"{sample}\"")

    # Handle any additional fields in full
    known_fields = {"appearance", "personality", "background", "motivations", "voice_samples"}
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


def format_section(char: Dict, section_name: str) -> str:
    """Format a specific section of a character."""
    name = char.get("name", char.get("id", "Unknown"))
    sections = char.get("sections", {})

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
    faction: Optional[str] = None,
    subfaction: Optional[str] = None,
    tag: Optional[str] = None,
    location: Optional[str] = None,
    branch: Optional[str] = None,
    short: bool = False
) -> None:
    """List characters (names only by default, or short profiles with --short)."""
    filtered = filter_characters(faction, subfaction, tag, location, branch)

    if not filtered:
        print("No characters found matching criteria")
        return

    # Sort by name (null-safe: handles both missing keys and null values)
    filtered.sort(key=lambda c: (c.get("name") or c.get("id") or ""))

    if short:
        # Show minimal profiles
        for char in filtered:
            print(format_minimal(char))
            print()
    else:
        # Just names
        print("Characters:")
        for char in filtered:
            name = char.get("name", char.get("id", "Unknown"))
            faction_str = char.get("faction", "")
            tags = char.get("tags", [])
            tag_str = f" [{', '.join(tags)}]" if tags else ""
            faction_display = f" ({faction_str})" if faction_str else ""
            print(f"  - {name}{faction_display}{tag_str}")

        print(f"\nTotal: {len(filtered)} characters")
        print("Use --short for minimal profiles, or 'get <name>' for details")


def cmd_get(
    char_name: str,
    depth: str = "minimal",
    section: Optional[str] = None
) -> None:
    """Get a character's profile at specified depth."""
    char = find_item(characters, char_name, "Character")

    if section:
        print(format_section(char, section))
    elif depth == "full":
        print(format_full(char))
    else:
        print(format_minimal(char))


def cmd_sections(char_name: str) -> None:
    """List available sections for a character."""
    char = find_item(characters, char_name, "Character")
    name = char.get("name", char.get("id", "Unknown"))
    sections = char.get("sections", {})

    if not sections:
        print(f"{name} has no additional sections")
        return

    print(f"Sections available for {name}:")
    for section_name in sections.keys():
        print(f"  - {section_name}")


def cmd_show(char_name: str) -> None:
    """Show raw JSON for a character (debugging)."""
    char = find_item(characters, char_name, "Character")
    print(json.dumps(char, indent=2))


def cmd_memories(char_name: str) -> None:
    """Show all memories involving this character."""
    # Find character to validate name exists
    find_item(characters, char_name, "Character")

    # Call memories.py to show memories for this character
    script_dir = Path(__file__).parent
    memories_script = script_dir / "memories.py"

    try:
        result = subprocess.run(
            [sys.executable, str(memories_script), "character", char_name],
            capture_output=False
        )
        sys.exit(result.returncode)
    except Exception as e:
        print(f"Error calling memories tool: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_update(
    char_name: str,
    field: str,
    value: str,
    reason: str,
    session: Optional[str] = None,
    output_json: bool = False
) -> None:
    """Update a character's development-tier field."""
    char = find_item(characters, char_name, "Character")
    char_id = char.get("id", char_name)

    # Navigate to the field and get old value
    parts = field.split('.')
    target = char
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

    # Find the character file and save
    # Look in characters/ directory
    search_root = Path.cwd()
    char_file = search_root / "characters" / f"{char_id}.json"

    if not char_file.exists():
        # Try to find it
        for path in (search_root / "characters").glob("*.json"):
            try:
                with open(path, encoding='utf-8-sig') as f:
                    data = json.load(f)
                    if data.get("id") == char_id:
                        char_file = path
                        break
            except (OSError, json.JSONDecodeError):
                pass

    if char_file.exists():
        with open(char_file, 'w', encoding='utf-8') as f:
            json.dump(char, f, indent=2)

    # Record in changelog
    changelog = load_changelog(search_root)
    entry = changelog.add(
        session=session or "current",
        character=char_id,
        tier="development",
        field=field,
        from_value=old_value,
        to_value=parsed_value,
        reason=reason
    )

    if output_json:
        print(json.dumps({
            "character": char_id,
            "field": field,
            "from": old_value,
            "to": parsed_value,
            "change_id": entry.id
        }, indent=2))
    else:
        name = char.get("name", char_id)
        print(f"Updated {name}.{field}")
        print(f"  {old_value} -> {parsed_value}")
        print(f"Change logged: {entry.id}")


def cmd_create(
    char_id: str,
    name: str,
    role: str,
    essence: str,
    faction: Optional[str] = None,
    subfaction: Optional[str] = None,
    tags: Optional[str] = None,
    voice: Optional[str] = None,
    output_json: bool = False
) -> None:
    """Create a new character with minimal profile."""
    search_root = Path.cwd()

    # Check if ID already exists
    if char_id in characters:
        print(f"Error: Character '{char_id}' already exists", file=sys.stderr)
        sys.exit(1)

    # Build character dict
    character = {
        "id": char_id,
        "name": name,
        "minimal": {
            "role": role,
            "essence": essence,
        }
    }

    if faction:
        character["faction"] = faction
    if subfaction:
        character["subfaction"] = subfaction
    if tags:
        character["tags"] = [t.strip() for t in tags.split(',')]
    if voice:
        character["minimal"]["voice"] = voice

    # Save to file
    path = save_item("characters", character, search_root)

    if output_json:
        print(json.dumps(character, indent=2))
    else:
        print(f"Created character: {char_id}")
        print(f"  Name: {name}")
        print(f"  Role: {role}")
        print(f"  Saved to: {path}")


def find_character_references(char_id: str, search_root: Path) -> Dict[str, int]:
    """Find references to a character in logs and memories."""
    from typing import Callable, Iterable

    char_lower = char_id.lower()

    def _count_refs(dir_path: Path, extractor: Callable[[Dict], Iterable[str]]) -> int:
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
                        if any(c.lower() == char_lower for c in extractor(item)):
                            count += 1
            except (OSError, json.JSONDecodeError) as e:
                print(f"Warning: Could not parse {path} for character references: {e}", file=sys.stderr)
        return count

    log_refs = _count_refs(
        search_root / "campaign" / "logs",
        lambda item: item.get("characters", {}).keys()
    )

    mem_refs = _count_refs(
        search_root / "memories",
        lambda item: item.get("connections", {}).get("characters", [])
    )

    return {"logs": log_refs, "memories": mem_refs}


def cmd_delete(char_id: str, force: bool = False) -> None:
    """Delete a character."""
    search_root = Path.cwd()

    # Check character exists
    char = find_item(characters, char_id, "Character")
    actual_id = char.get("id", char_id)

    # Check for references unless --force is used
    if not force:
        refs = find_character_references(actual_id, search_root)
        total_refs = refs["logs"] + refs["memories"]
        if total_refs > 0:
            print(f"Warning: Character '{actual_id}' is referenced in:", file=sys.stderr)
            if refs["logs"] > 0:
                print(f"  - {refs['logs']} log entries", file=sys.stderr)
            if refs["memories"] > 0:
                print(f"  - {refs['memories']} memories", file=sys.stderr)
            print(f"\nUse --force to delete anyway.", file=sys.stderr)
            sys.exit(1)

    # Delete the file
    if delete_item_file("characters", actual_id, search_root):
        print(f"Deleted character: {actual_id}")
    else:
        print(f"Error: Could not find file for character '{actual_id}'", file=sys.stderr)
        sys.exit(1)


def main():
    # Find search root (current directory or script parent)
    search_root = Path.cwd()

    # Load characters
    discover_characters(search_root)

    # Parse command line
    if len(sys.argv) < 2 or sys.argv[1] in ('--help', '-h'):
        print("Usage: python characters.py <command> [options]")
        print("\nCommands:")
        print("  create <id> --name N --role R --essence E ...")
        print("                                 Create a new character")
        print("  delete <id> [--force]          Delete a character")
        print("  list [filters...]              List character names")
        print("  list --short [filters...]      List with minimal profiles")
        print("  get <name>                     Get minimal profile")
        print("  get <name> --depth full        Get full profile")
        print("  get <name> --section NAME      Get specific section")
        print("  sections <name>                List available sections")
        print("  memories <name>                Show memories involving character")
        print("  show <name>                    Show raw JSON")
        print("  update <name> --field FIELD --value VAL --reason R")
        print("                                 Update character field (dot notation)")
        print("\nCreate options:")
        print("  --name NAME                    Character display name (required)")
        print("  --role ROLE                    Character role (required)")
        print("  --essence TEXT                 Core essence, 35 words max (required)")
        print("  --faction NAME                 Faction/group")
        print("  --subfaction NAME              Sub-faction")
        print("  --tags TAGS                    Comma-separated tags")
        print("  --voice QUOTE                  Voice sample quote")
        print("  --json                         Output as JSON")
        print("\nFilters (for list):")
        print("  --faction NAME                 Filter by faction")
        print("  --subfaction NAME              Filter by subfaction")
        print("  --tag NAME                     Filter by tag")
        print("  --location NAME                Filter by current location (from campaign state)")
        print("  --branch NAME                  Filter by branch protagonists (from campaign config)")
        print("\nUpdate options:")
        print("  --field FIELD                  Field to update (dot notation, e.g., full.motivation)")
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
    faction = None
    subfaction = None
    tag = None
    location = None
    branch = None
    short = False
    depth = "minimal"
    section = None
    field = None
    char_name = None
    value = None
    reason = None
    session_name = None
    output_json = False
    force = False
    # Create-specific options
    name = None
    role = None
    essence = None
    voice = None
    tags_list = None

    i = 2
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == "--faction" and i + 1 < len(sys.argv):
            faction = sys.argv[i + 1]
            i += 2
        elif arg == "--subfaction" and i + 1 < len(sys.argv):
            subfaction = sys.argv[i + 1]
            i += 2
        elif arg == "--tag" and i + 1 < len(sys.argv):
            tag = sys.argv[i + 1]
            i += 2
        elif arg == "--location" and i + 1 < len(sys.argv):
            location = sys.argv[i + 1]
            i += 2
        elif arg == "--branch" and i + 1 < len(sys.argv):
            branch = sys.argv[i + 1]
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
        elif arg == "--role" and i + 1 < len(sys.argv):
            role = sys.argv[i + 1]
            i += 2
        elif arg == "--essence" and i + 1 < len(sys.argv):
            essence = sys.argv[i + 1]
            i += 2
        elif arg == "--voice" and i + 1 < len(sys.argv):
            voice = sys.argv[i + 1]
            i += 2
        elif arg == "--tags" and i + 1 < len(sys.argv):
            tags_list = sys.argv[i + 1]
            i += 2
        elif not arg.startswith("--"):
            # Positional argument (character name/id)
            char_name = arg
            i += 1
        else:
            print(f"Unknown option: {arg}", file=sys.stderr)
            sys.exit(1)

    # Execute command
    if command == "create":
        if not char_name:
            print("Error: character id required for create", file=sys.stderr)
            sys.exit(1)
        if not name:
            print("Error: --name required for create", file=sys.stderr)
            sys.exit(1)
        if not role:
            print("Error: --role required for create", file=sys.stderr)
            sys.exit(1)
        if not essence:
            print("Error: --essence required for create", file=sys.stderr)
            sys.exit(1)
        cmd_create(
            char_id=char_name,
            name=name,
            role=role,
            essence=essence,
            faction=faction,
            subfaction=subfaction,
            tags=tags_list,
            voice=voice,
            output_json=output_json
        )
    elif command == "delete":
        if not char_name:
            print("Error: character id required for delete", file=sys.stderr)
            sys.exit(1)
        cmd_delete(char_name, force)
    elif command == "list":
        cmd_list(faction, subfaction, tag, location, branch, short)
    elif command == "get":
        if not char_name:
            print("Error: character name is required for 'get' command", file=sys.stderr)
            sys.exit(1)
        cmd_get(char_name, depth, section)
    elif command == "sections":
        if not char_name:
            print("Error: character name is required for 'sections' command", file=sys.stderr)
            sys.exit(1)
        cmd_sections(char_name)
    elif command == "show":
        if not char_name:
            print("Error: character name is required for 'show' command", file=sys.stderr)
            sys.exit(1)
        cmd_show(char_name)
    elif command == "memories":
        if not char_name:
            print("Error: character name is required for 'memories' command", file=sys.stderr)
            sys.exit(1)
        cmd_memories(char_name)
    elif command == "update":
        if not char_name:
            print("Error: character name required", file=sys.stderr)
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
        cmd_update(char_name, field, value, reason, session_name, output_json)
    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
