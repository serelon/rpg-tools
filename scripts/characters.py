#!/usr/bin/env python3
"""Character tool for solo RPG games. Provides incremental character data loading."""

import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any


# Character storage
characters: Dict[str, Dict] = {}


def discover_characters(search_root: Path) -> None:
    """Discover character files from characters/ folder."""
    global characters

    char_paths = []

    # Look in characters/ relative to search root
    chars_dir = search_root / "characters"
    if chars_dir.exists():
        char_paths.extend(chars_dir.glob("*.json"))

    # Also check if we're in a campaign folder with characters/
    if not char_paths:
        # Try parent directories
        for parent in [search_root.parent, search_root.parent.parent]:
            chars_dir = parent / "characters"
            if chars_dir.exists():
                char_paths.extend(chars_dir.glob("*.json"))
                break

    # Load all discovered characters
    for path in char_paths:
        try:
            with open(path, encoding='utf-8') as f:
                char = json.load(f)
                char_id = char.get("id", path.stem)
                characters[char_id] = char
        except Exception as e:
            print(f"Warning: Could not load character {path}: {e}", file=sys.stderr)

    if not characters:
        print("Warning: No character files found in characters/", file=sys.stderr)


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
    char_lower = char_name.lower()

    # Find character by id or name
    char = None
    for c in characters.values():
        if (c.get("id", "").lower() == char_lower or
            c.get("name", "").lower() == char_lower):
            char = c
            break

    if not char:
        print(f"Error: Character '{char_name}' not found", file=sys.stderr)
        print(f"Available: {', '.join(characters.keys())}", file=sys.stderr)
        sys.exit(1)

    if section:
        print(format_section(char, section))
    elif depth == "full":
        print(format_full(char))
    else:
        print(format_minimal(char))


def cmd_sections(char_name: str) -> None:
    """List available sections for a character."""
    char_lower = char_name.lower()

    char = None
    for c in characters.values():
        if (c.get("id", "").lower() == char_lower or
            c.get("name", "").lower() == char_lower):
            char = c
            break

    if not char:
        print(f"Error: Character '{char_name}' not found", file=sys.stderr)
        sys.exit(1)

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
    char_lower = char_name.lower()

    char = None
    for c in characters.values():
        if (c.get("id", "").lower() == char_lower or
            c.get("name", "").lower() == char_lower):
            char = c
            break

    if not char:
        print(f"Error: Character '{char_name}' not found", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(char, indent=2))


def cmd_memories(char_name: str) -> None:
    """Show all memories involving this character."""
    # Find character to validate name exists
    char_lower = char_name.lower()
    char = None
    for c in characters.values():
        if (c.get("id", "").lower() == char_lower or
            c.get("name", "").lower() == char_lower):
            char = c
            break

    if not char:
        print(f"Error: Character '{char_name}' not found", file=sys.stderr)
        sys.exit(1)

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
        print("\nFilters (for list):")
        print("  --faction NAME                 Filter by faction")
        print("  --subfaction NAME              Filter by subfaction")
        print("  --tag NAME                     Filter by tag")
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
    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
