#!/usr/bin/env python3
"""Location tool for solo RPG games. Provides hierarchical/graph location data loading."""

import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set


# Location storage
locations: Dict[str, Dict] = {}


def discover_locations(search_root: Path) -> None:
    """Discover location files from locations/ folder."""
    global locations

    loc_paths = []

    # Look in locations/ relative to search root
    locs_dir = search_root / "locations"
    if locs_dir.exists():
        loc_paths.extend(locs_dir.glob("*.json"))

    # Also check parent directories
    if not loc_paths:
        for parent in [search_root.parent, search_root.parent.parent]:
            locs_dir = parent / "locations"
            if locs_dir.exists():
                loc_paths.extend(locs_dir.glob("*.json"))
                break

    # Load all discovered locations
    for path in loc_paths:
        try:
            with open(path, encoding='utf-8') as f:
                data = json.load(f)
                # Handle both single location and array of locations
                if isinstance(data, list):
                    for loc in data:
                        loc_id = loc.get("id", path.stem)
                        locations[loc_id] = loc
                else:
                    loc_id = data.get("id", path.stem)
                    locations[loc_id] = data
        except Exception as e:
            print(f"Warning: Could not load location {path}: {e}", file=sys.stderr)

    if not locations:
        print("Warning: No location files found in locations/", file=sys.stderr)


def get_all_parents(loc: Dict) -> List[str]:
    """Get all parent IDs for a location (primary + additional)."""
    parents = []
    if loc.get("parent"):
        parents.append(loc["parent"])
    if loc.get("parents"):
        parents.extend(loc["parents"])
    return list(set(parents))  # dedupe


def get_children(loc_id: str) -> List[Dict]:
    """Get all locations that have loc_id as a parent."""
    children = []
    for loc in locations.values():
        if loc.get("parent") == loc_id:
            children.append(loc)
        elif loc_id in loc.get("parents", []):
            children.append(loc)
    return children


def get_root_locations() -> List[Dict]:
    """Get locations with no parent."""
    return [loc for loc in locations.values()
            if not loc.get("parent") and not loc.get("parents")]


def filter_locations(
    tag: Optional[str] = None,
    parent: Optional[str] = None,
    loc_type: Optional[str] = None
) -> List[Dict]:
    """Filter locations by tag, parent, or type."""
    result = list(locations.values())

    if tag:
        tag_lower = tag.lower()
        result = [loc for loc in result if tag_lower in [t.lower() for t in loc.get("tags", [])]]

    if parent:
        parent_lower = parent.lower()
        result = [loc for loc in result
                  if (loc.get("parent", "").lower() == parent_lower or
                      parent_lower in [p.lower() for p in loc.get("parents", [])])]

    if loc_type:
        type_lower = loc_type.lower()
        result = [loc for loc in result
                  if loc.get("minimal", {}).get("type", "").lower() == type_lower]

    return result


def format_minimal(loc: Dict) -> str:
    """Format location's minimal profile."""
    lines = []
    name = loc.get("name", loc.get("id", "Unknown"))
    lines.append(f"# {name}")

    minimal = loc.get("minimal", {})
    if minimal.get("type"):
        lines.append(f"**Type:** {minimal['type']}")
    if minimal.get("essence"):
        lines.append(f"**Essence:** {minimal['essence']}")

    # Show parent(s)
    parents = get_all_parents(loc)
    if parents:
        parent_names = []
        for pid in parents:
            if pid in locations:
                parent_names.append(locations[pid].get("name", pid))
            else:
                parent_names.append(pid)
        lines.append(f"**Within:** {', '.join(parent_names)}")

    # Show what's available
    available = []
    if loc.get("full"):
        available.append("--depth full")
    if loc.get("sections"):
        section_names = list(loc["sections"].keys())
        available.append(f"sections: {', '.join(section_names)}")

    if available:
        lines.append(f"\n[Available: {'; '.join(available)}]")

    return "\n".join(lines)


def format_full(loc: Dict) -> str:
    """Format location's full profile."""
    lines = [format_minimal(loc)]

    full = loc.get("full", {})

    if full.get("description"):
        lines.append(f"\n## Description\n{full['description']}")

    if full.get("atmosphere"):
        lines.append(f"\n## Atmosphere\n{full['atmosphere']}")

    if full.get("history"):
        lines.append(f"\n## History\n{full['history']}")

    if full.get("notable_features"):
        lines.append("\n## Notable Features")
        for feature in full["notable_features"]:
            lines.append(f"- {feature}")

    if full.get("dangers"):
        lines.append(f"\n## Dangers\n{full['dangers']}")

    if full.get("secrets"):
        lines.append(f"\n## Secrets\n{full['secrets']}")

    # Handle any additional fields in full
    known_fields = {"description", "atmosphere", "history", "notable_features", "dangers", "secrets"}
    for key, value in full.items():
        if key not in known_fields:
            lines.append(f"\n## {key.replace('_', ' ').title()}\n{value}")

    return "\n".join(lines)


def format_section(loc: Dict, section_name: str) -> str:
    """Format a specific section of a location."""
    name = loc.get("name", loc.get("id", "Unknown"))
    sections = loc.get("sections", {})

    if section_name not in sections:
        return f"Section '{section_name}' not found for {name}"

    section = sections[section_name]
    lines = [f"# {name} - {section_name.replace('_', ' ').title()}"]

    if isinstance(section, dict):
        for key, value in section.items():
            if isinstance(value, list):
                lines.append(f"\n**{key}:**")
                for item in value:
                    lines.append(f"- {item}")
            else:
                lines.append(f"**{key}:** {value}")
    elif isinstance(section, list):
        for item in section:
            lines.append(f"- {item}")
    else:
        lines.append(str(section))

    return "\n".join(lines)


def build_tree(loc_id: Optional[str] = None, indent: int = 0, visited: Optional[Set[str]] = None) -> List[str]:
    """Build tree representation starting from loc_id (or roots if None)."""
    if visited is None:
        visited = set()

    lines = []

    if loc_id is None:
        # Start from roots
        roots = get_root_locations()
        roots.sort(key=lambda x: x.get("name", x.get("id", "")))
        for root in roots:
            lines.extend(build_tree(root.get("id"), indent, visited.copy()))
    else:
        if loc_id in visited:
            return lines  # Prevent cycles
        visited.add(loc_id)

        loc = locations.get(loc_id)
        if not loc:
            return lines

        name = loc.get("name", loc_id)
        loc_type = loc.get("minimal", {}).get("type", "")
        type_str = f" ({loc_type})" if loc_type else ""

        prefix = "  " * indent + ("+- " if indent > 0 else "")
        lines.append(f"{prefix}{name}{type_str}")

        # Get children (using primary parent only for tree view)
        children = [c for c in locations.values() if c.get("parent") == loc_id]
        children.sort(key=lambda x: x.get("name", x.get("id", "")))

        for child in children:
            lines.extend(build_tree(child.get("id"), indent + 1, visited.copy()))

    return lines


def get_path_to_root(loc_id: str) -> List[str]:
    """Get path from location to root following primary parent."""
    path = []
    current_id = loc_id

    visited = set()
    while current_id and current_id not in visited:
        visited.add(current_id)
        loc = locations.get(current_id)
        if not loc:
            break
        path.append(loc.get("name", current_id))
        current_id = loc.get("parent")

    path.reverse()
    return path


def get_connections(loc_id: str) -> Dict[str, str]:
    """Get all connections for a location (from sections + bidirectional)."""
    loc = locations.get(loc_id)
    if not loc:
        return {}

    connections = {}

    # Direct connections from this location
    if loc.get("sections", {}).get("connections"):
        connections.update(loc["sections"]["connections"])

    # Connections TO this location from others
    for other_id, other_loc in locations.items():
        if other_id == loc_id:
            continue
        other_conns = other_loc.get("sections", {}).get("connections", {})
        if loc_id in other_conns:
            if other_id not in connections:
                connections[other_id] = f"(from {other_loc.get('name', other_id)}) {other_conns[loc_id]}"

    return connections


def cmd_list(
    tag: Optional[str] = None,
    parent: Optional[str] = None,
    loc_type: Optional[str] = None,
    short: bool = False
) -> None:
    """List locations."""
    filtered = filter_locations(tag, parent, loc_type)

    if not filtered:
        print("No locations found matching criteria")
        return

    filtered.sort(key=lambda x: x.get("name", x.get("id", "")))

    if short:
        for loc in filtered:
            print(format_minimal(loc))
            print()
    else:
        print("Locations:")
        for loc in filtered:
            name = loc.get("name", loc.get("id", "Unknown"))
            loc_type = loc.get("minimal", {}).get("type", "")
            tags = loc.get("tags", [])
            type_str = f" ({loc_type})" if loc_type else ""
            tag_str = f" [{', '.join(tags)}]" if tags else ""
            print(f"  - {name}{type_str}{tag_str}")

        print(f"\nTotal: {len(filtered)} locations")
        print("Use --short for minimal profiles, or 'get <name>' for details")


def cmd_get(
    loc_name: str,
    depth: str = "minimal",
    section: Optional[str] = None
) -> None:
    """Get a location's profile."""
    loc_lower = loc_name.lower()

    loc = None
    for l in locations.values():
        if (l.get("id", "").lower() == loc_lower or
            l.get("name", "").lower() == loc_lower):
            loc = l
            break

    if not loc:
        print(f"Error: Location '{loc_name}' not found", file=sys.stderr)
        print(f"Available: {', '.join(locations.keys())}", file=sys.stderr)
        sys.exit(1)

    if section:
        print(format_section(loc, section))
    elif depth == "full":
        print(format_full(loc))
    else:
        print(format_minimal(loc))


def cmd_tree(loc_name: Optional[str] = None) -> None:
    """Show location hierarchy."""
    if loc_name:
        loc_lower = loc_name.lower()
        loc_id = None
        for l in locations.values():
            if (l.get("id", "").lower() == loc_lower or
                l.get("name", "").lower() == loc_lower):
                loc_id = l.get("id")
                break
        if not loc_id:
            print(f"Error: Location '{loc_name}' not found", file=sys.stderr)
            sys.exit(1)
        lines = build_tree(loc_id)
    else:
        lines = build_tree()

    if lines:
        print("\n".join(lines))
    else:
        print("No locations to display")


def cmd_path(loc_name: str) -> None:
    """Show path from root to location."""
    loc_lower = loc_name.lower()

    loc_id = None
    for l in locations.values():
        if (l.get("id", "").lower() == loc_lower or
            l.get("name", "").lower() == loc_lower):
            loc_id = l.get("id")
            break

    if not loc_id:
        print(f"Error: Location '{loc_name}' not found", file=sys.stderr)
        sys.exit(1)

    path = get_path_to_root(loc_id)
    print(" > ".join(path))


def cmd_connections(loc_name: str) -> None:
    """Show all connections for a location."""
    loc_lower = loc_name.lower()

    loc = None
    loc_id = None
    for l in locations.values():
        if (l.get("id", "").lower() == loc_lower or
            l.get("name", "").lower() == loc_lower):
            loc = l
            loc_id = l.get("id")
            break

    if not loc:
        print(f"Error: Location '{loc_name}' not found", file=sys.stderr)
        sys.exit(1)

    name = loc.get("name", loc_id)
    connections = get_connections(loc_id)

    print(f"# Connections for {name}")

    # Parents
    parents = get_all_parents(loc)
    if parents:
        print("\n**Within:**")
        for pid in parents:
            pname = locations.get(pid, {}).get("name", pid)
            print(f"  - {pname}")

    # Children
    children = get_children(loc_id)
    if children:
        print("\n**Contains:**")
        for child in children:
            cname = child.get("name", child.get("id", "Unknown"))
            print(f"  - {cname}")

    # Lateral connections
    if connections:
        print("\n**Connected to:**")
        for conn_id, desc in connections.items():
            conn_name = locations.get(conn_id, {}).get("name", conn_id)
            print(f"  - {conn_name}: {desc}")

    if not parents and not children and not connections:
        print("\nNo connections found")


def cmd_sections(loc_name: str) -> None:
    """List available sections for a location."""
    loc_lower = loc_name.lower()

    loc = None
    for l in locations.values():
        if (l.get("id", "").lower() == loc_lower or
            l.get("name", "").lower() == loc_lower):
            loc = l
            break

    if not loc:
        print(f"Error: Location '{loc_name}' not found", file=sys.stderr)
        sys.exit(1)

    name = loc.get("name", loc.get("id", "Unknown"))
    sections = loc.get("sections", {})

    if not sections:
        print(f"{name} has no additional sections")
        return

    print(f"Sections available for {name}:")
    for section_name in sections.keys():
        print(f"  - {section_name}")


def cmd_memories(loc_name: str) -> None:
    """Show all memories at this location."""
    # Find location to validate name exists
    loc_lower = loc_name.lower()
    loc = None
    for l in locations.values():
        if (l.get("id", "").lower() == loc_lower or
            l.get("name", "").lower() == loc_lower):
            loc = l
            break

    if not loc:
        print(f"Error: Location '{loc_name}' not found", file=sys.stderr)
        sys.exit(1)

    # Call memories.py to show memories for this location
    script_dir = Path(__file__).parent
    memories_script = script_dir / "memories.py"

    try:
        result = subprocess.run(
            [sys.executable, str(memories_script), "location", loc_name],
            capture_output=False
        )
        sys.exit(result.returncode)
    except Exception as e:
        print(f"Error calling memories tool: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    search_root = Path.cwd()
    discover_locations(search_root)

    if len(sys.argv) < 2:
        print("Usage: python locations.py <command> [options]")
        print("\nCommands:")
        print("  list [filters...]              List location names")
        print("  list --short [filters...]      List with minimal profiles")
        print("  get <name>                     Get minimal profile")
        print("  get <name> --depth full        Get full profile")
        print("  get <name> --section NAME      Get specific section")
        print("  sections <name>                List available sections")
        print("  tree                           Show full hierarchy")
        print("  tree <name>                    Show subtree from location")
        print("  path <name>                    Show path from root")
        print("  connections <name>             Show all connections")
        print("  memories <name>                Show memories at location")
        print("\nFilters (for list):")
        print("  --tag NAME                     Filter by tag")
        print("  --parent NAME                  Filter by parent")
        print("  --type NAME                    Filter by type")
        sys.exit(1)

    command = sys.argv[1]

    # Parse options
    tag = None
    parent = None
    loc_type = None
    short = False
    depth = "minimal"
    section = None
    loc_name = None

    i = 2
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == "--tag" and i + 1 < len(sys.argv):
            tag = sys.argv[i + 1]
            i += 2
        elif arg == "--parent" and i + 1 < len(sys.argv):
            parent = sys.argv[i + 1]
            i += 2
        elif arg == "--type" and i + 1 < len(sys.argv):
            loc_type = sys.argv[i + 1]
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
            loc_name = arg
            i += 1
        else:
            print(f"Unknown option: {arg}", file=sys.stderr)
            sys.exit(1)

    # Execute command
    if command == "list":
        cmd_list(tag, parent, loc_type, short)
    elif command == "get":
        if not loc_name:
            print("Error: location name required for 'get'", file=sys.stderr)
            sys.exit(1)
        cmd_get(loc_name, depth, section)
    elif command == "tree":
        cmd_tree(loc_name)
    elif command == "path":
        if not loc_name:
            print("Error: location name required for 'path'", file=sys.stderr)
            sys.exit(1)
        cmd_path(loc_name)
    elif command == "connections":
        if not loc_name:
            print("Error: location name required for 'connections'", file=sys.stderr)
            sys.exit(1)
        cmd_connections(loc_name)
    elif command == "sections":
        if not loc_name:
            print("Error: location name required for 'sections'", file=sys.stderr)
            sys.exit(1)
        cmd_sections(loc_name)
    elif command == "memories":
        if not loc_name:
            print("Error: location name required for 'memories'", file=sys.stderr)
            sys.exit(1)
        cmd_memories(loc_name)
    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
