#!/usr/bin/env python3
"""Character tool for solo RPG games. Provides incremental character data loading."""

import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any

from lib import discover_data, find_item, load_changelog


# Character storage
characters: Dict[str, Dict] = {}


def discover_characters(search_root: Path) -> None:
    """Discover character files from characters/ folder."""
    global characters
    characters = discover_data("characters", search_root)


def filter_characters(
    faction: Optional[str] = None,
    subfaction: Optional[str] = None,
    tag: Optional[str] = None
) -> List[Dict]:
    """Filter characters by faction, subfaction, or tag."""
    result = list(characters.values())

    if faction:
        faction_lower = faction.lower()
        result = [c for c in result if c.get("faction", "").lower() == faction_lower]

    if subfaction:
        subfaction_lower = subfaction.lower()
        result = [c for c in result if c.get("subfaction", "").lower() == subfaction_lower]

    if tag:
        tag_lower = tag.lower()
        result = [c for c in result if tag_lower in [t.lower() for t in c.get("tags", [])]]

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
                        lines.append(f"- {item}")
                    else:
                        lines.append(f"- {item}")
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
    short: bool = False
) -> None:
    """List characters (names only by default, or short profiles with --short)."""
    filtered = filter_characters(faction, subfaction, tag)

    if not filtered:
        print("No characters found matching criteria")
        return

    # Sort by name
    filtered.sort(key=lambda c: c.get("name", c.get("id", "")))

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

    # Update the value
    target[final_key] = value

    # Find the character file and save
    # Look in characters/ directory
    search_root = Path.cwd()
    char_file = search_root / "characters" / f"{char_id}.json"

    if not char_file.exists():
        # Try to find it
        for path in (search_root / "characters").glob("*.json"):
            try:
                with open(path, encoding='utf-8') as f:
                    data = json.load(f)
                    if data.get("id") == char_id:
                        char_file = path
                        break
            except:
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
        to_value=value,
        reason=reason
    )

    if output_json:
        print(json.dumps({
            "character": char_id,
            "field": field,
            "from": old_value,
            "to": value,
            "change_id": entry.id
        }, indent=2))
    else:
        name = char.get("name", char_id)
        print(f"Updated {name}.{field}")
        print(f"  {old_value} -> {value}")
        print(f"Change logged: {entry.id}")


def main():
    # Find search root (current directory or script parent)
    search_root = Path.cwd()

    # Load characters
    discover_characters(search_root)

    # Parse command line
    if len(sys.argv) < 2:
        print("Usage: python characters.py <command> [options]")
        print("\nCommands:")
        print("  list [filters...]              List character names")
        print("  list --short [filters...]      List with minimal profiles")
        print("  get <name>                     Get minimal profile")
        print("  get <name> --depth full        Get full profile")
        print("  get <name> --section NAME      Get specific section")
        print("  sections <name>                List available sections")
        print("  memories <name>                Show memories involving character")
        print("  show <name>                    Show raw JSON")
        print("  update <name> --section FIELD --value VAL --reason R")
        print("                                 Update character field")
        print("\nFilters (for list):")
        print("  --faction NAME                 Filter by faction")
        print("  --subfaction NAME              Filter by subfaction")
        print("  --tag NAME                     Filter by tag")
        print("\nUpdate options:")
        print("  --section FIELD                Field to update (dot notation supported)")
        print("  --value VALUE                  New value")
        print("  --reason REASON                Reason for change")
        print("  --session NAME                 Session identifier (optional)")
        print("  --json                         Output as JSON")
        sys.exit(1)

    command = sys.argv[1]

    # Parse options
    faction = None
    subfaction = None
    tag = None
    short = False
    depth = "minimal"
    section = None
    char_name = None
    value = None
    reason = None
    session_name = None
    output_json = False

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
        elif arg == "--short":
            short = True
            i += 1
        elif arg == "--depth" and i + 1 < len(sys.argv):
            depth = sys.argv[i + 1]
            i += 2
        elif arg == "--section" and i + 1 < len(sys.argv):
            section = sys.argv[i + 1]
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
        elif not arg.startswith("--"):
            # Positional argument (character name)
            char_name = arg
            i += 1
        else:
            print(f"Unknown option: {arg}", file=sys.stderr)
            sys.exit(1)

    # Execute command
    if command == "list":
        cmd_list(faction, subfaction, tag, short)
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
        if not section:  # reuse --section as --field
            print("Error: --section required", file=sys.stderr)
            sys.exit(1)
        if not value:
            print("Error: --value required", file=sys.stderr)
            sys.exit(1)
        if not reason:
            print("Error: --reason required", file=sys.stderr)
            sys.exit(1)
        cmd_update(char_name, section, value, reason, session_name, output_json)
    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
