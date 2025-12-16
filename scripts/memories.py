#!/usr/bin/env python3
"""Memory tool for solo RPG games. Manages campaign memories with cross-references."""

import json
import random
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set

from lib import parse_era, parse_session, discover_data, find_item


# Memory storage
memories: Dict[str, Dict] = {}


def discover_memories(search_root: Path) -> None:
    """Discover memory files from memories/ folder."""
    global memories
    memories = discover_data(
        "memories",
        search_root,
        loose_pattern="*-memories.json"
    )


def validate_connections() -> None:
    """Validate connections and print warnings for broken references."""
    warnings = []

    # Try to discover characters and locations for validation
    characters_available = {}
    locations_available = {}

    try:
        search_root = Path.cwd()

        # Discover characters
        chars_dir = search_root / "characters"
        if not chars_dir.exists():
            # Try parent directories
            for parent in [search_root.parent, search_root.parent.parent]:
                chars_dir = parent / "characters"
                if chars_dir.exists():
                    break

        if chars_dir.exists():
            for path in chars_dir.glob("*.json"):
                try:
                    with open(path, encoding='utf-8') as f:
                        char = json.load(f)
                        char_id = char.get("id", path.stem)
                        characters_available[char_id.lower()] = char_id
                except:
                    pass

        # Discover locations
        locs_dir = search_root / "locations"
        if not locs_dir.exists():
            for parent in [search_root.parent, search_root.parent.parent]:
                locs_dir = parent / "locations"
                if locs_dir.exists():
                    break

        if locs_dir.exists():
            for path in locs_dir.glob("*.json"):
                try:
                    with open(path, encoding='utf-8') as f:
                        data = json.load(f)
                        if isinstance(data, list):
                            for loc in data:
                                loc_id = loc.get("id", path.stem)
                                locations_available[loc_id.lower()] = loc_id
                        else:
                            loc_id = data.get("id", path.stem)
                            locations_available[loc_id.lower()] = loc_id
                except:
                    pass
    except:
        pass  # Silently skip validation if discovery fails

    # Validate connections
    for mem_id, mem in memories.items():
        connections = mem.get("connections", {})

        # Check related_memories
        for rel_id in connections.get("related_memories", []):
            if rel_id not in memories:
                warnings.append(f"Memory '{mem_id}' references unknown memory '{rel_id}'")

        # Check characters (if we discovered any)
        if characters_available:
            for char_id in connections.get("characters", []):
                if char_id.lower() not in characters_available:
                    warnings.append(f"Memory '{mem_id}' references unknown character '{char_id}'")

        # Check locations (if we discovered any)
        if locations_available:
            for loc_id in connections.get("locations", []):
                if loc_id.lower() not in locations_available:
                    warnings.append(f"Memory '{mem_id}' references unknown location '{loc_id}'")

    # Print warnings if any (but don't exit - these are just warnings)
    if warnings:
        for warning in warnings[:5]:  # Limit to first 5 to avoid spam
            print(f"Warning: {warning}", file=sys.stderr)
        if len(warnings) > 5:
            print(f"Warning: ... and {len(warnings) - 5} more broken references", file=sys.stderr)


def filter_memories(
    campaign: Optional[str] = None,
    character: Optional[str] = None,
    location: Optional[str] = None,
    mem_type: Optional[str] = None,
    tag: Optional[str] = None,
    era: Optional[str] = None,
    session: Optional[str] = None,
    intensity: Optional[str] = None,
    perspective: Optional[str] = None,
    before_era: Optional[str] = None
) -> List[Dict]:
    """Filter memories by various criteria."""
    result = list(memories.values())

    if campaign:
        campaign_lower = campaign.lower()
        result = [m for m in result if campaign_lower in m.get("campaign", "").lower()]

    if character:
        char_lower = character.lower()
        result = [m for m in result
                  if any(char_lower in c.lower()
                         for c in m.get("connections", {}).get("characters", []))]

    if location:
        loc_lower = location.lower()
        result = [m for m in result
                  if any(loc_lower in loc.lower()
                         for loc in m.get("connections", {}).get("locations", []))]

    if mem_type:
        type_lower = mem_type.lower()
        result = [m for m in result if m.get("type", "").lower() == type_lower]

    if tag:
        tag_lower = tag.lower()
        result = [m for m in result
                  if any(tag_lower in t.lower() for t in m.get("tags", []))]

    if era:
        era_lower = era.lower()
        result = [m for m in result if era_lower in m.get("era", "").lower()]

    if session:
        result = [m for m in result if m.get("session", "") == session]

    if intensity:
        intensity_lower = intensity.lower()
        result = [m for m in result if m.get("intensity", "").lower() == intensity_lower]

    if perspective:
        persp_lower = perspective.lower()
        result = [m for m in result if persp_lower in m.get("perspective", "").lower()]

    if before_era:
        target = parse_era(before_era)
        result = [m for m in result if parse_era(m.get("era", "")) <= target]

    return result


def format_memory(mem: Dict, show_text: bool = True) -> str:
    """Format a memory for display."""
    lines = []

    title = mem.get("title", mem.get("id", "Untitled"))
    lines.append(f"# {title}")

    # Metadata
    meta = []
    if mem.get("type"):
        meta.append(f"Type: {mem['type']}")
    if mem.get("era"):
        meta.append(f"Era: {mem['era']}")
    if mem.get("session"):
        meta.append(f"Session: {mem['session']}")
    if mem.get("intensity"):
        meta.append(f"Intensity: {mem['intensity']}")
    if mem.get("perspective"):
        meta.append(f"Perspective: {mem['perspective']}")

    if meta:
        lines.append(f"**{' | '.join(meta)}**")

    # Tags
    if mem.get("tags"):
        lines.append(f"*Tags: {', '.join(mem['tags'])}*")

    # Connections
    connections = mem.get("connections", {})
    if any(connections.values()):
        conn_lines = []
        if connections.get("characters"):
            conn_lines.append(f"Characters: {', '.join(connections['characters'])}")
        if connections.get("locations"):
            conn_lines.append(f"Locations: {', '.join(connections['locations'])}")
        if connections.get("stories"):
            conn_lines.append(f"Stories: {', '.join(connections['stories'])}")
        if connections.get("related_memories"):
            conn_lines.append(f"Related: {', '.join(connections['related_memories'])}")

        if conn_lines:
            lines.append(f"\n*Connected to: {' • '.join(conn_lines)}*")

    # Text
    if show_text and mem.get("text"):
        lines.append(f"\n{mem['text']}")

    return "\n".join(lines)


def cmd_list(
    campaign: Optional[str] = None,
    character: Optional[str] = None,
    location: Optional[str] = None,
    mem_type: Optional[str] = None,
    tag: Optional[str] = None,
    era: Optional[str] = None,
    session: Optional[str] = None,
    intensity: Optional[str] = None,
    perspective: Optional[str] = None,
    short: bool = False
) -> None:
    """List memories."""
    filtered = filter_memories(
        campaign=campaign,
        character=character,
        location=location,
        mem_type=mem_type,
        tag=tag,
        era=era,
        session=session,
        intensity=intensity,
        perspective=perspective
    )

    if not filtered:
        print("No memories found matching criteria")
        return

    # Sort by session, then era
    filtered.sort(key=lambda m: (parse_session(m.get("session", "")),
                                  parse_era(m.get("era", ""))))

    if short:
        # Show full details without text
        for mem in filtered:
            print(format_memory(mem, show_text=False))
            print()
    else:
        # Just titles and basic info
        print(f"\n{'Title':<45} {'Type':<18} {'Era':<15}")
        print("-" * 78)

        for mem in filtered:
            title = mem.get("title", mem.get("id", "Untitled"))[:43]
            mem_type = mem.get("type", "")[:16]
            era = mem.get("era", "")[:13]
            print(f"{title:<45} {mem_type:<18} {era:<15}")

        print(f"\nTotal: {len(filtered)} memories")
        print("Use --short for details, or 'get <id>' for full memory")


def cmd_get(mem_id: str) -> None:
    """Get a specific memory."""
    mem = find_item(memories, mem_id, "Memory")
    print(format_memory(mem))


def cmd_random(
    campaign: Optional[str] = None,
    character: Optional[str] = None,
    location: Optional[str] = None,
    mem_type: Optional[str] = None,
    tag: Optional[str] = None,
    era: Optional[str] = None,
    intensity: Optional[str] = None
) -> None:
    """Get a random memory."""
    filtered = filter_memories(
        campaign=campaign,
        character=character,
        location=location,
        mem_type=mem_type,
        tag=tag,
        era=era,
        intensity=intensity
    )

    if not filtered:
        print("No memories found matching criteria", file=sys.stderr)
        sys.exit(1)

    mem = random.choice(filtered)
    print(format_memory(mem))


def cmd_recent(
    campaign: Optional[str] = None,
    count: int = 5,
    by_era: bool = False
) -> None:
    """Show recent memories (by session number or era chronology)."""
    filtered = filter_memories(campaign=campaign)

    if not filtered:
        print("No memories found", file=sys.stderr)
        return

    # Sort by era or session
    if by_era:
        filtered.sort(key=lambda m: parse_era(m.get("era", "")), reverse=True)
    else:
        filtered.sort(key=lambda m: parse_session(m.get("session", "")), reverse=True)

    # Take top N
    recent = filtered[:count]

    for mem in recent:
        print(format_memory(mem))
        print("\n" + "-" * 78 + "\n")


def cmd_search(query: str, campaign: Optional[str] = None) -> None:
    """Full-text search across memory text and titles."""
    query_lower = query.lower()

    filtered = filter_memories(campaign=campaign)

    # Search in title and text
    matches = []
    for mem in filtered:
        title = mem.get("title", "").lower()
        text = mem.get("text", "").lower()
        if query_lower in title or query_lower in text:
            matches.append(mem)

    if not matches:
        print(f"No memories found matching '{query}'")
        return

    print(f"Found {len(matches)} memories matching '{query}':\n")

    for mem in matches:
        print(format_memory(mem, show_text=False))

        # Show excerpt with match
        text = mem.get("text", "")
        if text:
            text_lower = text.lower()
            pos = text_lower.find(query_lower)
            if pos >= 0:
                start = max(0, pos - 50)
                end = min(len(text), pos + len(query) + 50)
                excerpt = text[start:end]
                if start > 0:
                    excerpt = "..." + excerpt
                if end < len(text):
                    excerpt = excerpt + "..."
                print(f"\n*Excerpt:* {excerpt}")

        print("\n" + "-" * 78 + "\n")


def cmd_connections(mem_id: str) -> None:
    """Show all connections for a memory."""
    mem = find_item(memories, mem_id, "Memory")
    title = mem.get("title", mem.get("id", "Untitled"))
    print(f"# Connections for: {title}\n")

    connections = mem.get("connections", {})

    # Characters
    if connections.get("characters"):
        print("**Characters:**")
        for char in connections["characters"]:
            print(f"  - {char}")
        print()

    # Locations
    if connections.get("locations"):
        print("**Locations:**")
        for loc in connections["locations"]:
            print(f"  - {loc}")
        print()

    # Stories
    if connections.get("stories"):
        print("**Stories:**")
        for story in connections["stories"]:
            print(f"  - {story}")
        print()

    # Related memories
    if connections.get("related_memories"):
        print("**Related Memories:**")
        for rel_id in connections["related_memories"]:
            rel_mem = memories.get(rel_id)
            if rel_mem:
                rel_title = rel_mem.get("title", rel_id)
                rel_type = rel_mem.get("type", "")
                print(f"  - {rel_title} ({rel_type})")
            else:
                print(f"  - {rel_id} (not loaded)")
        print()

    if not any(connections.values()):
        print("No connections found")


def cmd_chain(mem_id: str, visited: Optional[Set[str]] = None) -> None:
    """Follow related_memories to show narrative thread."""
    if visited is None:
        visited = set()

    mem = find_item(memories, mem_id, "Memory")
    actual_id = mem.get("id", mem_id)

    if actual_id in visited:
        return  # Prevent cycles

    visited.add(actual_id)

    # Print this memory
    print(format_memory(mem, show_text=False))
    print()

    # Follow related memories
    related = mem.get("connections", {}).get("related_memories", [])
    if related:
        print(f"↓ Related memories:\n")
        for rel_id in related:
            if rel_id not in visited:
                # Check if related memory exists
                rel_exists = False
                for mid in memories.keys():
                    if mid == rel_id:
                        rel_exists = True
                        break

                if rel_exists:
                    cmd_chain(rel_id, visited)
                else:
                    print(f"  [Memory '{rel_id}' referenced but not found]\n")


def cmd_character(char_name: str) -> None:
    """Show all memories involving a character."""
    filtered = filter_memories(character=char_name)

    if not filtered:
        print(f"No memories found involving '{char_name}'")
        return

    # Sort by session/era
    filtered.sort(key=lambda m: (parse_session(m.get("session", "")),
                                  parse_era(m.get("era", ""))))

    print(f"# Memories involving {char_name}\n")
    print(f"Found {len(filtered)} memories:\n")

    for mem in filtered:
        print(format_memory(mem, show_text=False))
        print()


def cmd_location(loc_name: str) -> None:
    """Show all memories at a location."""
    filtered = filter_memories(location=loc_name)

    if not filtered:
        print(f"No memories found at '{loc_name}'")
        return

    # Sort by session/era
    filtered.sort(key=lambda m: (parse_session(m.get("session", "")),
                                  parse_era(m.get("era", ""))))

    print(f"# Memories at {loc_name}\n")
    print(f"Found {len(filtered)} memories:\n")

    for mem in filtered:
        print(format_memory(mem, show_text=False))
        print()


def cmd_meta(campaign: Optional[str] = None) -> None:
    """Show metadata summary with counts."""
    filtered = filter_memories(campaign=campaign)

    if not filtered:
        print("No memories found")
        return

    # Count types
    types: Dict[str, int] = {}
    for m in filtered:
        t = m.get("type", "unknown")
        types[t] = types.get(t, 0) + 1

    # Count tags
    tags: Dict[str, int] = {}
    for m in filtered:
        for tag in m.get("tags", []):
            tags[tag] = tags.get(tag, 0) + 1

    # Count intensities
    intensities: Dict[str, int] = {}
    for m in filtered:
        i = m.get("intensity", "unknown")
        intensities[i] = intensities.get(i, 0) + 1

    # Count perspectives
    perspectives: Dict[str, int] = {}
    for m in filtered:
        p = m.get("perspective", "unknown")
        perspectives[p] = perspectives.get(p, 0) + 1

    # Count sessions
    sessions: Dict[str, int] = {}
    for m in filtered:
        s = m.get("session", "unknown")
        sessions[s] = sessions.get(s, 0) + 1

    # Print results
    print(f"\n## Types")
    for k, v in sorted(types.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")

    print(f"\n## Intensities")
    for k, v in sorted(intensities.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")

    print(f"\n## Perspectives")
    for k, v in sorted(perspectives.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")

    print(f"\n## Sessions")
    for k, v in sorted(sessions.items(), key=lambda x: parse_session(x[0])):
        print(f"  {k}: {v}")

    print(f"\n## Top Tags")
    for k, v in sorted(tags.items(), key=lambda x: -x[1])[:15]:
        print(f"  {k}: {v}")

    print(f"\n**Total: {len(filtered)} memories**")


def main():
    # Find search root
    search_root = Path.cwd()

    # Load memories
    discover_memories(search_root)

    # Validate connections (warnings only, doesn't exit)
    validate_connections()

    if len(sys.argv) < 2:
        print("Usage: python memories.py <command> [options]")
        print("\nCommands:")
        print("  list [filters...]                    List memories")
        print("  list --short [filters...]            List with details (no text)")
        print("  get <id>                             Get specific memory")
        print("  random [filters...]                  Get random memory")
        print("  recent [--campaign NAME] [--count N] Show recent memories")
        print("  recent --by-era                      Sort by era instead of session")
        print("  search <query> [--campaign NAME]     Full-text search")
        print("  connections <id>                     Show all connections")
        print("  chain <id>                           Follow related memories")
        print("  character <name>                     All memories involving character")
        print("  location <name>                      All memories at location")
        print("  meta [--campaign NAME]               Show metadata summary")
        print("\nFilters (for list/random):")
        print("  --campaign NAME        Filter by campaign")
        print("  --character NAME       Filter by character")
        print("  --location NAME        Filter by location")
        print("  --type TYPE            Filter by type")
        print("  --tag TAG              Filter by tag")
        print("  --era ERA              Filter by era")
        print("  --session SESSION      Filter by session")
        print("  --intensity LEVEL      Filter by intensity")
        print("  --perspective VIEW     Filter by perspective")
        sys.exit(1)

    command = sys.argv[1]

    # Parse options
    campaign = None
    character = None
    location = None
    mem_type = None
    tag = None
    era = None
    session = None
    intensity = None
    perspective = None
    short = False
    count = 5
    by_era = False
    query = None
    mem_id = None

    i = 2
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == "--campaign" and i + 1 < len(sys.argv):
            campaign = sys.argv[i + 1]
            i += 2
        elif arg == "--character" and i + 1 < len(sys.argv):
            character = sys.argv[i + 1]
            i += 2
        elif arg == "--location" and i + 1 < len(sys.argv):
            location = sys.argv[i + 1]
            i += 2
        elif arg == "--type" and i + 1 < len(sys.argv):
            mem_type = sys.argv[i + 1]
            i += 2
        elif arg == "--tag" and i + 1 < len(sys.argv):
            tag = sys.argv[i + 1]
            i += 2
        elif arg == "--era" and i + 1 < len(sys.argv):
            era = sys.argv[i + 1]
            i += 2
        elif arg == "--session" and i + 1 < len(sys.argv):
            session = sys.argv[i + 1]
            i += 2
        elif arg == "--intensity" and i + 1 < len(sys.argv):
            intensity = sys.argv[i + 1]
            i += 2
        elif arg == "--perspective" and i + 1 < len(sys.argv):
            perspective = sys.argv[i + 1]
            i += 2
        elif arg == "--short":
            short = True
            i += 1
        elif arg == "--count" and i + 1 < len(sys.argv):
            count = int(sys.argv[i + 1])
            i += 2
        elif arg == "--by-era":
            by_era = True
            i += 1
        elif not arg.startswith("--"):
            # Positional argument (query or id)
            if command == "search":
                query = arg
            else:
                mem_id = arg
            i += 1
        else:
            print(f"Unknown option: {arg}", file=sys.stderr)
            sys.exit(1)

    # Execute command
    if command == "list":
        cmd_list(campaign, character, location, mem_type, tag, era, session,
                 intensity, perspective, short)
    elif command == "get":
        if not mem_id:
            print("Error: memory id required for 'get'", file=sys.stderr)
            sys.exit(1)
        cmd_get(mem_id)
    elif command == "random":
        cmd_random(campaign, character, location, mem_type, tag, era, intensity)
    elif command == "recent":
        cmd_recent(campaign, count, by_era)
    elif command == "search":
        if not query:
            print("Error: search query required", file=sys.stderr)
            sys.exit(1)
        cmd_search(query, campaign)
    elif command == "connections":
        if not mem_id:
            print("Error: memory id required for 'connections'", file=sys.stderr)
            sys.exit(1)
        cmd_connections(mem_id)
    elif command == "chain":
        if not mem_id:
            print("Error: memory id required for 'chain'", file=sys.stderr)
            sys.exit(1)
        cmd_chain(mem_id)
    elif command == "character":
        if not mem_id:
            print("Error: character name required", file=sys.stderr)
            sys.exit(1)
        cmd_character(mem_id)
    elif command == "location":
        if not mem_id:
            print("Error: location name required", file=sys.stderr)
            sys.exit(1)
        cmd_location(mem_id)
    elif command == "meta":
        cmd_meta(campaign)
    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
