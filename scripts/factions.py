#!/usr/bin/env python3
"""Faction tool for solo RPG games. Provides faction data management."""

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any

from lib import discover_data, find_item, load_changelog, save_item, find_source_file, delete_item_file


# Faction storage
factions: Dict[str, Dict] = {}

# Character storage for member queries
characters: Dict[str, Dict] = {}


def discover_factions(search_root: Path) -> None:
    """Discover faction files from factions/ folder."""
    global factions
    factions = discover_data("factions", search_root)


def discover_characters(search_root: Path) -> None:
    """Discover character files from characters/ folder."""
    global characters
    characters = discover_data("characters", search_root)


def get_parent(faction: Dict) -> Optional[Dict]:
    """Get the parent faction if it exists."""
    parent_id = faction.get("parent")
    if parent_id and parent_id in factions:
        return factions[parent_id]
    return None


def get_children(faction_id: str) -> List[Dict]:
    """Get all factions that have this faction as parent."""
    children = []
    for f in factions.values():
        if f.get("parent") == faction_id:
            children.append(f)
    return children


def validate_parent_exists(parent_id: str) -> bool:
    """Check if a parent faction exists."""
    return parent_id in factions


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

    # Show parent relationship
    parent = get_parent(faction)
    if parent:
        parent_name = parent.get("name", parent.get("id", "Unknown"))
        lines.append(f"**Parent:** {parent_name}")
    elif faction.get("parent"):
        # Parent ID specified but not found
        lines.append(f"**Parent:** {faction['parent']} [not found]")

    # Show autonomous flag if present
    if faction.get("autonomous"):
        lines.append("**Autonomous:** yes")

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

            # Show parent if present
            parent_str = ""
            parent = get_parent(faction)
            if parent:
                parent_name = parent.get("name", parent.get("id", ""))
                parent_str = f" <- {parent_name}"
            elif faction.get("parent"):
                parent_str = f" <- {faction['parent']} [!]"

            print(f"  - {name}{type_str}{parent_str}{tag_str}")

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
    parent: Optional[str] = None,
    output_json: bool = False
) -> None:
    """Create a new faction with minimal profile."""
    search_root = Path.cwd()

    # Check if ID already exists
    if faction_id in factions:
        print(f"Error: Faction '{faction_id}' already exists", file=sys.stderr)
        sys.exit(1)

    # Validate parent exists if specified
    if parent and not validate_parent_exists(parent):
        print(f"Error: Parent faction '{parent}' not found", file=sys.stderr)
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

    if parent:
        faction["parent"] = parent

    # Save to file
    path = save_item("factions", faction, search_root)

    if output_json:
        print(json.dumps(faction, indent=2))
    else:
        print(f"Created faction: {faction_id}")
        print(f"  Name: {name}")
        print(f"  Type: {faction_type}")
        if parent:
            parent_faction = factions.get(parent, {})
            parent_name = parent_faction.get("name", parent)
            print(f"  Parent: {parent_name}")
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


def find_incoming_relationships(faction_id: str) -> List[Dict]:
    """Find relationships from other factions that target this faction.

    Returns a list of dicts with 'source_id', 'source_name', 'type', and 'relationship'.
    """
    faction_lower = faction_id.lower()
    incoming = []

    for f in factions.values():
        f_id = f.get("id", "")
        if f_id.lower() == faction_lower:
            continue  # Skip self

        relationships = f.get("relationships", [])
        for rel in relationships:
            target = rel.get("target", "").lower()
            if target == faction_lower:
                incoming.append({
                    "source_id": f_id,
                    "source_name": f.get("name", f_id),
                    "type": rel.get("type", "unknown"),
                    "relationship": rel
                })

    return incoming


def cmd_delete(faction_id: str, force: bool = False) -> None:
    """Delete a faction."""
    search_root = Path.cwd()

    # Check faction exists
    faction = find_item(factions, faction_id, "Faction")
    actual_id = faction.get("id", faction_id)
    faction_name = faction.get("name", actual_id)

    # Check for children (subfactions)
    children = get_children(actual_id)

    # Check for references unless --force is used
    if not force:
        has_warnings = False

        # Check for child factions
        if children:
            print(f"Warning: Faction '{faction_name}' has {len(children)} child faction(s):", file=sys.stderr)
            for child in children:
                child_name = child.get("name", child.get("id", "Unknown"))
                print(f"  - {child_name}", file=sys.stderr)
            has_warnings = True

        # Check for references in logs/memories
        refs = find_faction_references(actual_id, search_root)
        total_refs = refs["logs"] + refs["memories"]
        if total_refs > 0:
            if has_warnings:
                print(file=sys.stderr)
            print(f"Warning: Faction '{faction_name}' is referenced in:", file=sys.stderr)
            if refs["logs"] > 0:
                print(f"  - {refs['logs']} log entries", file=sys.stderr)
            if refs["memories"] > 0:
                print(f"  - {refs['memories']} memories", file=sys.stderr)
            has_warnings = True

        # Check for incoming relationships from other factions
        incoming = find_incoming_relationships(actual_id)
        if incoming:
            if has_warnings:
                print(file=sys.stderr)
            print(f"Warning: Other factions have relationships targeting '{faction_name}':", file=sys.stderr)
            for inc in incoming:
                print(f"  - {inc['source_name']}: {inc['type']} relationship", file=sys.stderr)
            has_warnings = True

        if has_warnings:
            print(f"\nUse --force to delete anyway.", file=sys.stderr)
            sys.exit(1)

    # Delete the file
    if delete_item_file("factions", actual_id, search_root):
        print(f"Deleted faction: {actual_id}")
    else:
        print(f"Error: Could not find file for faction '{actual_id}'", file=sys.stderr)
        sys.exit(1)


def check_sync_warnings(faction: Dict, faction_chars: List[Dict]) -> List[str]:
    """Check for bidirectional sync mismatches between faction and characters.

    Returns a list of warning messages.
    """
    warnings = []
    faction_id = faction.get("id", "")
    faction_name = faction.get("name", faction_id)

    # Get the named members from faction
    members = faction.get("members", {})
    named_members = set(m.lower() for m in members.get("named", []))

    # Check characters who have this faction but aren't in members.named
    for char in faction_chars:
        char_id = char.get("id", "").lower()
        char_name = char.get("name", char_id)
        if char_id and char_id not in named_members:
            warnings.append(
                f"Warning: {char_name} has faction '{faction_id}' but is not in "
                f"{faction_name}'s members.named list"
            )

    # Check members.named entries whose characters don't have matching faction
    faction_char_ids = set(c.get("id", "").lower() for c in faction_chars)
    for member_id in members.get("named", []):
        member_lower = member_id.lower()
        if member_lower not in faction_char_ids:
            # Check if character exists at all
            char = None
            for c in characters.values():
                if c.get("id", "").lower() == member_lower:
                    char = c
                    break

            if char:
                char_faction = char.get("faction", "")
                if char_faction.lower() != faction_id.lower():
                    warnings.append(
                        f"Warning: {member_id} is in {faction_name}'s members.named "
                        f"but has faction '{char_faction}' (not '{faction_id}')"
                    )
            else:
                warnings.append(
                    f"Warning: {member_id} is in {faction_name}'s members.named "
                    f"but character file not found"
                )

    return warnings


def cmd_members(
    faction_name: str,
    subfaction_filter: Optional[str] = None,
    unit_filter: Optional[str] = None,
    output_json: bool = False
) -> None:
    """Show faction members."""
    search_root = Path.cwd()

    # Discover characters if not already loaded
    if not characters:
        discover_characters(search_root)

    faction = find_item(factions, faction_name, "Faction")
    faction_id = faction.get("id", faction_name)
    name = faction.get("name", faction_id)

    # Find characters with this faction
    faction_chars = []
    for char in characters.values():
        char_faction = char.get("faction", "")
        if char_faction.lower() == faction_id.lower():
            # Apply subfaction filter if provided
            if subfaction_filter:
                char_subfaction = char.get("subfaction", "")
                if char_subfaction.lower() != subfaction_filter.lower():
                    continue
            faction_chars.append(char)

    # Sort by name
    faction_chars.sort(key=lambda c: c.get("name", c.get("id", "")))

    # Get members section from faction
    members = faction.get("members", {})
    named = members.get("named", [])
    units = members.get("units", [])
    pools = members.get("pools", [])

    # Apply unit filter
    if unit_filter:
        units = [u for u in units if u.get("id", "").lower() == unit_filter.lower()
                 or u.get("name", "").lower() == unit_filter.lower()]

    # Check for sync warnings
    warnings = check_sync_warnings(faction, faction_chars)

    if output_json:
        result = {
            "faction": faction_id,
            "named_characters": [
                {
                    "id": c.get("id"),
                    "name": c.get("name"),
                    "role": c.get("minimal", {}).get("role"),
                    "subfaction": c.get("subfaction")
                }
                for c in faction_chars
            ],
            "units": units,
            "pools": pools,
            "warnings": warnings,
            "totals": {
                "named": len(faction_chars),
                "units": len(units),
                "unit_count": sum(u.get("count", 0) for u in units),
                "pools": len(pools),
                "pool_count": sum(p.get("count", 0) for p in pools)
            }
        }
        print(json.dumps(result, indent=2))
        return

    # Print warnings first
    for warning in warnings:
        print(warning, file=sys.stderr)
    if warnings:
        print(file=sys.stderr)

    # Format output
    lines = [f"# {name} Members"]

    # Named characters from character files
    if faction_chars:
        lines.append("\n## Named Characters (from character files)")
        for char in faction_chars:
            char_name = char.get("name", char.get("id", "Unknown"))
            role = char.get("minimal", {}).get("role", "")
            subfaction = char.get("subfaction", "")

            parts = [f"- {char_name}"]
            if role:
                parts.append(f"({role})")
            if subfaction:
                parts.append(f"- subfaction: {subfaction}")
            lines.append(" ".join(parts))

    # Units
    if units:
        lines.append("\n## Units")
        for unit in units:
            unit_name = unit.get("name", unit.get("id", "Unknown"))
            count = unit.get("count", 0)
            role = unit.get("role", "")
            morale = unit.get("morale", "")

            parts = [f"- {unit_name} ({count})"]
            details = []
            if role:
                details.append(f"role: {role}")
            if morale:
                details.append(f"morale: {morale}")
            if details:
                parts.append(f"- {', '.join(details)}")
            lines.append(" ".join(parts))

    # Pools
    if pools:
        lines.append("\n## Pools")
        for pool in pools:
            pool_name = pool.get("description", pool.get("id", "Unknown"))
            count = pool.get("count", 0)
            state = pool.get("state", "")

            parts = [f"- {pool_name} ({count})"]
            if state:
                parts.append(f"- state: {state}")
            lines.append(" ".join(parts))

    # Totals
    total_named = len(faction_chars)
    total_units = len(units)
    unit_count = sum(u.get("count", 0) for u in units)
    total_pools = len(pools)
    pool_count = sum(p.get("count", 0) for p in pools)

    totals = []
    if total_named > 0:
        totals.append(f"{total_named} named")
    if total_units > 0:
        totals.append(f"{total_units} units ({unit_count})")
    if total_pools > 0:
        totals.append(f"{total_pools} pool{'s' if total_pools > 1 else ''} ({pool_count})")

    if totals:
        lines.append(f"\nTotal: {', '.join(totals)}")
    else:
        lines.append("\nNo members found")

    print("\n".join(lines))


def cmd_economy(faction_name: str) -> None:
    """Show faction economy."""
    print("Not implemented yet")


def build_tree_lines(
    faction_id: str,
    prefix: str = "",
    is_last: bool = True,
    max_depth: Optional[int] = None,
    current_depth: int = 0,
    visited: Optional[set] = None
) -> List[str]:
    """Build tree representation lines for a faction and its descendants."""
    if visited is None:
        visited = set()

    # Prevent infinite loops from circular references
    if faction_id in visited:
        return [f"{prefix}[circular reference to {faction_id}]"]
    visited.add(faction_id)

    lines = []
    faction = factions.get(faction_id)
    if not faction:
        return [f"{prefix}{faction_id} [not found]"]

    name = faction.get("name", faction_id)
    faction_type = faction.get("type", "")

    # Build annotation
    annotations = []
    if faction_type:
        annotations.append(faction_type)
    if faction.get("autonomous"):
        annotations.append("autonomous")

    annotation_str = f" ({', '.join(annotations)})" if annotations else ""
    lines.append(f"{prefix}{name}{annotation_str}")

    # Check depth limit
    if max_depth is not None and current_depth >= max_depth:
        return lines

    # Get and sort children
    children = get_children(faction_id)
    children.sort(key=lambda f: (f.get("name") or f.get("id") or ""))

    for i, child in enumerate(children):
        child_id = child.get("id")
        if not child_id:
            continue

        is_child_last = (i == len(children) - 1)

        # Determine the prefix for child lines
        if current_depth == 0:
            # Root level: no connector prefix needed for first level
            child_prefix = ""
            child_connector = "|-- " if not is_child_last else "`-- "
        else:
            # Nested: continue the tree structure
            if is_last:
                child_prefix = prefix.replace("`-- ", "    ").replace("|-- ", "|   ")
            else:
                child_prefix = prefix.replace("`-- ", "    ").replace("|-- ", "|   ")
            child_connector = "|-- " if not is_child_last else "`-- "

        child_lines = build_tree_lines(
            child_id,
            prefix=child_prefix + child_connector,
            is_last=is_child_last,
            max_depth=max_depth,
            current_depth=current_depth + 1,
            visited=visited.copy()
        )
        lines.extend(child_lines)

    return lines


def cmd_tree(faction_name: str, max_depth: Optional[int] = None) -> None:
    """Show faction hierarchy tree."""
    faction = find_item(factions, faction_name, "Faction")
    faction_id = faction.get("id", faction_name)

    lines = build_tree_lines(faction_id, max_depth=max_depth)
    print("\n".join(lines))


# Relationship type schemas - expected fields per type (allows freeform extension)
RELATIONSHIP_SCHEMAS = {
    "debtor": {"expected": ["principal", "rate", "accruing"], "description": "owes money/favors"},
    "creditor": {"expected": ["principal", "rate", "accruing"], "description": "is owed money/favors"},
    "ally": {"expected": ["trust", "terms"], "description": "mutual support"},
    "enemy": {"expected": ["threat", "conflict"], "description": "active opposition"},
    "rival": {"expected": ["tension", "domain"], "description": "competition"},
    "vassal": {"expected": ["obligations", "tribute"], "description": "subordinate"},
    "patron": {"expected": ["protection", "expectations"], "description": "protector"},
    "reports_to": {"expected": ["via", "bypasses"], "description": "authority chain"},
    "neutral": {"expected": ["last_contact"], "description": "no active relationship"},
}


def format_number(n: Any) -> str:
    """Format a number with commas for readability."""
    if isinstance(n, (int, float)):
        if isinstance(n, float) and n == int(n):
            n = int(n)
        return f"{n:,}"
    return str(n)


def format_relationship_state(rel_type: str, state: Dict) -> str:
    """Format relationship state based on type."""
    if not state:
        return ""

    parts = []

    if rel_type in ("debtor", "creditor"):
        principal = state.get("principal")
        rate = state.get("rate")
        accruing = state.get("accruing")

        if principal is not None:
            parts.append(f"{format_number(principal)} credits")
        if rate is not None:
            if isinstance(rate, float) and rate < 1:
                parts.append(f"at {int(rate * 100)}%")
            else:
                parts.append(f"at {rate}%")
        if accruing is not None:
            if isinstance(accruing, bool):
                if accruing:
                    parts.append("accruing")
            else:
                parts.append(f"({format_number(accruing)}/month accruing)")

        # Add any extra fields
        for k, v in state.items():
            if k not in ("principal", "rate", "accruing"):
                parts.append(f"{k}={v}")

    elif rel_type == "ally":
        trust = state.get("trust")
        terms = state.get("terms")

        if trust is not None:
            parts.append(f"trust={trust}")
        # Terms shown separately
        for k, v in state.items():
            if k not in ("trust", "terms"):
                parts.append(f"{k}={v}")

    elif rel_type == "enemy":
        threat = state.get("threat")
        conflict = state.get("conflict")

        if threat is not None:
            parts.append(f"threat={threat}")
        if conflict is not None:
            parts.append(f"conflict={conflict}")
        for k, v in state.items():
            if k not in ("threat", "conflict"):
                parts.append(f"{k}={v}")

    elif rel_type == "rival":
        tension = state.get("tension")
        domain = state.get("domain")

        if tension is not None:
            parts.append(f"tension={tension}")
        if domain is not None:
            parts.append(f"domain={domain}")
        for k, v in state.items():
            if k not in ("tension", "domain"):
                parts.append(f"{k}={v}")

    elif rel_type == "vassal":
        obligations = state.get("obligations")
        tribute = state.get("tribute")

        if obligations is not None:
            parts.append(f"obligations={obligations}")
        if tribute is not None:
            parts.append(f"tribute={tribute}")
        for k, v in state.items():
            if k not in ("obligations", "tribute"):
                parts.append(f"{k}={v}")

    elif rel_type == "patron":
        protection = state.get("protection")
        expectations = state.get("expectations")

        if protection is not None:
            parts.append(f"protection={protection}")
        if expectations is not None:
            parts.append(f"expectations={expectations}")
        for k, v in state.items():
            if k not in ("protection", "expectations"):
                parts.append(f"{k}={v}")

    elif rel_type == "reports_to":
        via = state.get("via")
        bypasses = state.get("bypasses")

        if via is not None:
            parts.append(f"via={via}")
        if bypasses is not None:
            if isinstance(bypasses, list):
                parts.append(f"bypasses=[{', '.join(bypasses)}]")
            else:
                parts.append(f"bypasses={bypasses}")
        for k, v in state.items():
            if k not in ("via", "bypasses"):
                parts.append(f"{k}={v}")

    else:
        # Generic handling for unknown types
        for k, v in state.items():
            parts.append(f"{k}={v}")

    return ", ".join(parts)


def get_target_name(target_id: str) -> str:
    """Get display name for a relationship target (faction or character)."""
    # Check factions first
    if target_id in factions:
        faction = factions[target_id]
        return faction.get("name", target_id)

    # Check characters
    if target_id in characters:
        char = characters[target_id]
        return char.get("name", target_id)

    # Fuzzy search in factions
    target_lower = target_id.lower()
    for f in factions.values():
        if f.get("id", "").lower() == target_lower:
            return f.get("name", target_id)
        if f.get("name", "").lower() == target_lower:
            return f.get("name", target_id)

    # Fuzzy search in characters
    for c in characters.values():
        if c.get("id", "").lower() == target_lower:
            return c.get("name", target_id)
        if c.get("name", "").lower() == target_lower:
            return c.get("name", target_id)

    return target_id


def is_sibling_faction(faction: Dict, target_id: str) -> bool:
    """Check if target is a sibling faction (shares same parent)."""
    faction_parent = faction.get("parent")
    if not faction_parent:
        return False

    target_lower = target_id.lower()
    for f in factions.values():
        f_id = f.get("id", "").lower()
        f_name = f.get("name", "").lower()
        if f_id == target_lower or f_name == target_lower:
            target_parent = f.get("parent")
            return target_parent and target_parent.lower() == faction_parent.lower()

    return False


def cmd_relationships(
    faction_name: str,
    rel_type: Optional[str] = None,
    output_json: bool = False
) -> None:
    """Show faction relationships."""
    search_root = Path.cwd()

    # Load characters for target name resolution
    if not characters:
        discover_characters(search_root)

    faction = find_item(factions, faction_name, "Faction")
    faction_id = faction.get("id", faction_name)
    name = faction.get("name", faction_id)

    relationships = faction.get("relationships", [])

    # Filter by type if specified
    if rel_type:
        rel_type_lower = rel_type.lower()
        relationships = [r for r in relationships if r.get("type", "").lower() == rel_type_lower]

    if output_json:
        result = {
            "faction": faction_id,
            "relationships": relationships
        }
        print(json.dumps(result, indent=2))
        return

    if not relationships:
        if rel_type:
            print(f"{name} has no {rel_type} relationships")
        else:
            print(f"{name} has no relationships defined")
        return

    # Group relationships by type
    by_type: Dict[str, List[Dict]] = {}
    for rel in relationships:
        rtype = rel.get("type", "unknown")
        if rtype not in by_type:
            by_type[rtype] = []
        by_type[rtype].append(rel)

    lines = [f"# {name} Relationships"]

    # Sort types for consistent output
    for rtype in sorted(by_type.keys()):
        rels = by_type[rtype]
        lines.append(f"\n## {rtype.title()}")

        for rel in rels:
            target_id = rel.get("target", "unknown")
            target_name = get_target_name(target_id)
            state = rel.get("state", {})
            notes = rel.get("notes")

            # Check if sibling
            sibling_marker = " (sibling)" if is_sibling_faction(faction, target_id) else ""

            # Format state
            state_str = format_relationship_state(rtype, state)

            # Build line
            if state_str:
                lines.append(f"- {target_name}{sibling_marker}: {state_str}")
            else:
                lines.append(f"- {target_name}{sibling_marker}")

            # Add terms/notes on separate lines if present
            if rtype == "ally" and state.get("terms"):
                lines.append(f"  Terms: {state['terms']}")

            if notes:
                lines.append(f"  Notes: {notes}")

    print("\n".join(lines))


def validate_target_exists(target_id: str) -> tuple[bool, str]:
    """Check if a target exists in factions or characters.

    Returns (exists, entity_type) where entity_type is 'faction', 'character', or 'unknown'.
    """
    target_lower = target_id.lower()

    # Check factions
    for f in factions.values():
        if f.get("id", "").lower() == target_lower or f.get("name", "").lower() == target_lower:
            return True, "faction"

    # Check characters
    for c in characters.values():
        if c.get("id", "").lower() == target_lower or c.get("name", "").lower() == target_lower:
            return True, "character"

    return False, "unknown"


def find_relationship(faction: Dict, target_id: str) -> Optional[Dict]:
    """Find a relationship by target ID."""
    relationships = faction.get("relationships", [])
    target_lower = target_id.lower()

    for rel in relationships:
        if rel.get("target", "").lower() == target_lower:
            return rel

    return None


def cmd_add_relationship(
    faction_name: str,
    rel_type: str,
    target: str,
    state: Optional[str] = None,
    notes: Optional[str] = None,
    reason: Optional[str] = None,
    session: Optional[str] = None,
    output_json: bool = False
) -> None:
    """Add a relationship to a faction."""
    search_root = Path.cwd()

    # Load characters for target validation
    if not characters:
        discover_characters(search_root)

    faction = find_item(factions, faction_name, "Faction")
    faction_id = faction.get("id", faction_name)
    faction_display = faction.get("name", faction_id)

    # Validate target exists (warn if not, but allow)
    target_exists, target_type = validate_target_exists(target)
    if not target_exists:
        print(f"Warning: Target '{target}' not found in factions or characters", file=sys.stderr)
        print("  (Proceeding anyway - target may be external)", file=sys.stderr)

    # Check for existing relationship with same target
    existing = find_relationship(faction, target)
    if existing:
        print(f"Error: Relationship with target '{target}' already exists", file=sys.stderr)
        print(f"  Use update-relationship to modify it, or remove-relationship first", file=sys.stderr)
        sys.exit(1)

    # Parse state JSON if provided
    state_dict = {}
    if state:
        try:
            state_dict = json.loads(state)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in --state: {e}", file=sys.stderr)
            sys.exit(1)

    # Build relationship
    relationship = {
        "type": rel_type,
        "target": target,
        "state": state_dict
    }

    if notes:
        relationship["notes"] = notes

    # Add to faction's relationships
    if "relationships" not in faction:
        faction["relationships"] = []

    faction["relationships"].append(relationship)

    # Save faction file
    faction_file = find_source_file("factions", faction_id, search_root)
    if faction_file:
        with open(faction_file, 'w', encoding='utf-8') as f:
            json.dump(faction, f, indent=2)

    # Log to changelog
    changelog = load_changelog(search_root)
    entry = changelog.add(
        session=session or "current",
        character=faction_id,
        tier="development",
        field="relationships",
        from_value=None,
        to_value=relationship,
        reason=reason or f"Added {rel_type} relationship with {target}"
    )

    if output_json:
        print(json.dumps({
            "action": "add-relationship",
            "faction": faction_id,
            "relationship": relationship,
            "target_found": target_exists,
            "target_type": target_type,
            "change_id": entry.id
        }, indent=2))
    else:
        target_name = get_target_name(target)
        print(f"Added {rel_type} relationship to {faction_display}")
        print(f"  Target: {target_name}")
        if state_dict:
            print(f"  State: {state_dict}")
        if notes:
            print(f"  Notes: {notes}")
        if not target_exists:
            print(f"  Warning: Target not found (may be external)")
        print(f"Change logged: {entry.id}")


def cmd_update_relationship(
    faction_name: str,
    target: str,
    field: str,
    value: str,
    reason: Optional[str] = None,
    session: Optional[str] = None,
    output_json: bool = False
) -> None:
    """Update a specific field in a relationship."""
    search_root = Path.cwd()

    # Load characters for target resolution
    if not characters:
        discover_characters(search_root)

    faction = find_item(factions, faction_name, "Faction")
    faction_id = faction.get("id", faction_name)
    faction_display = faction.get("name", faction_id)

    # Find the relationship
    relationship = find_relationship(faction, target)
    if not relationship:
        print(f"Error: No relationship found with target '{target}'", file=sys.stderr)
        sys.exit(1)

    # Navigate to the field (supports dot notation like state.trust)
    parts = field.split('.')
    obj = relationship
    for part in parts[:-1]:
        if part not in obj:
            obj[part] = {}
        obj = obj[part]

    final_key = parts[-1]
    old_value = obj.get(final_key)

    # Try to parse value as JSON
    parsed_value = value
    if value.startswith('{') or value.startswith('['):
        try:
            parsed_value = json.loads(value)
        except json.JSONDecodeError:
            pass  # Keep as string
    elif value.lower() == 'true':
        parsed_value = True
    elif value.lower() == 'false':
        parsed_value = False
    elif value.lower() == 'null':
        parsed_value = None
    else:
        # Try to parse as number
        try:
            if '.' in value:
                parsed_value = float(value)
            else:
                parsed_value = int(value)
        except ValueError:
            pass  # Keep as string

    # Update the value
    obj[final_key] = parsed_value

    # Save faction file
    faction_file = find_source_file("factions", faction_id, search_root)
    if faction_file:
        with open(faction_file, 'w', encoding='utf-8') as f:
            json.dump(faction, f, indent=2)

    # Log to changelog
    changelog = load_changelog(search_root)
    entry = changelog.add(
        session=session or "current",
        character=faction_id,
        tier="development",
        field=f"relationships[{target}].{field}",
        from_value=old_value,
        to_value=parsed_value,
        reason=reason or f"Updated relationship with {target}"
    )

    if output_json:
        print(json.dumps({
            "action": "update-relationship",
            "faction": faction_id,
            "target": target,
            "field": field,
            "from": old_value,
            "to": parsed_value,
            "change_id": entry.id
        }, indent=2))
    else:
        target_name = get_target_name(target)
        print(f"Updated {faction_display} relationship with {target_name}")
        print(f"  {field}: {old_value} -> {parsed_value}")
        print(f"Change logged: {entry.id}")


def cmd_remove_relationship(
    faction_name: str,
    target: str,
    reason: Optional[str] = None,
    session: Optional[str] = None,
    output_json: bool = False
) -> None:
    """Remove a relationship from a faction."""
    search_root = Path.cwd()

    # Load characters for target resolution
    if not characters:
        discover_characters(search_root)

    faction = find_item(factions, faction_name, "Faction")
    faction_id = faction.get("id", faction_name)
    faction_display = faction.get("name", faction_id)

    # Find the relationship
    relationships = faction.get("relationships", [])
    target_lower = target.lower()

    removed = None
    idx = -1
    for i, rel in enumerate(relationships):
        if rel.get("target", "").lower() == target_lower:
            removed = rel
            idx = i
            break

    if removed is None:
        print(f"Error: No relationship found with target '{target}'", file=sys.stderr)
        sys.exit(1)

    # Remove the relationship
    del relationships[idx]

    # Save faction file
    faction_file = find_source_file("factions", faction_id, search_root)
    if faction_file:
        with open(faction_file, 'w', encoding='utf-8') as f:
            json.dump(faction, f, indent=2)

    # Log to changelog
    changelog = load_changelog(search_root)
    entry = changelog.add(
        session=session or "current",
        character=faction_id,
        tier="development",
        field="relationships",
        from_value=removed,
        to_value=None,
        reason=reason or f"Removed {removed.get('type', 'unknown')} relationship with {target}"
    )

    if output_json:
        print(json.dumps({
            "action": "remove-relationship",
            "faction": faction_id,
            "removed": removed,
            "change_id": entry.id
        }, indent=2))
    else:
        target_name = get_target_name(target)
        rel_type = removed.get("type", "unknown")
        print(f"Removed {rel_type} relationship from {faction_display}")
        print(f"  Target: {target_name}")
        print(f"Change logged: {entry.id}")


def cmd_add_member(
    faction_name: str,
    character_name: str,
    subfaction: Optional[str] = None,
    unit: Optional[str] = None,
    session: Optional[str] = None,
    output_json: bool = False
) -> None:
    """Add a member to a faction."""
    search_root = Path.cwd()

    # Discover characters if not already loaded
    if not characters:
        discover_characters(search_root)

    # Find faction and character
    faction = find_item(factions, faction_name, "Faction")
    faction_id = faction.get("id", faction_name)
    faction_display = faction.get("name", faction_id)

    char = find_item(characters, character_name, "Character")
    char_id = char.get("id", character_name)
    char_display = char.get("name", char_id)

    # Track changes for changelog
    changes = []

    # Update character's faction field
    old_faction = char.get("faction")
    old_subfaction = char.get("subfaction")

    char["faction"] = faction_id
    if subfaction:
        char["subfaction"] = subfaction

    # Save character file
    char_file = find_source_file("characters", char_id, search_root)
    if char_file:
        with open(char_file, 'w', encoding='utf-8') as f:
            json.dump(char, f, indent=2)
        changes.append({
            "type": "character",
            "id": char_id,
            "field": "faction",
            "from": old_faction,
            "to": faction_id
        })
        if subfaction and subfaction != old_subfaction:
            changes.append({
                "type": "character",
                "id": char_id,
                "field": "subfaction",
                "from": old_subfaction,
                "to": subfaction
            })

    # Add to faction's members.named if not already there
    if "members" not in faction:
        faction["members"] = {}
    if "named" not in faction["members"]:
        faction["members"]["named"] = []

    named_lower = [m.lower() for m in faction["members"]["named"]]
    if char_id.lower() not in named_lower:
        faction["members"]["named"].append(char_id)

        # Save faction file
        faction_file = find_source_file("factions", faction_id, search_root)
        if faction_file:
            with open(faction_file, 'w', encoding='utf-8') as f:
                json.dump(faction, f, indent=2)
            changes.append({
                "type": "faction",
                "id": faction_id,
                "field": "members.named",
                "action": "add",
                "value": char_id
            })

    # Log to changelog
    changelog = load_changelog(search_root)
    entry = changelog.add(
        session=session or "current",
        character=char_id,
        tier="development",
        field="faction",
        from_value=old_faction,
        to_value=faction_id,
        reason=f"Added to {faction_display}"
    )

    if output_json:
        print(json.dumps({
            "action": "add-member",
            "faction": faction_id,
            "character": char_id,
            "subfaction": subfaction,
            "changes": changes,
            "change_id": entry.id
        }, indent=2))
    else:
        print(f"Added {char_display} to {faction_display}")
        if subfaction:
            print(f"  Subfaction: {subfaction}")
        print(f"  Character faction field updated")
        print(f"  Added to faction members.named list")
        print(f"Change logged: {entry.id}")


def cmd_remove_member(
    faction_name: str,
    character_name: str,
    session: Optional[str] = None,
    output_json: bool = False
) -> None:
    """Remove a member from a faction."""
    search_root = Path.cwd()

    # Discover characters if not already loaded
    if not characters:
        discover_characters(search_root)

    # Find faction and character
    faction = find_item(factions, faction_name, "Faction")
    faction_id = faction.get("id", faction_name)
    faction_display = faction.get("name", faction_id)

    char = find_item(characters, character_name, "Character")
    char_id = char.get("id", character_name)
    char_display = char.get("name", char_id)

    # Track changes for changelog
    changes = []

    # Clear character's faction and subfaction fields
    old_faction = char.get("faction")
    old_subfaction = char.get("subfaction")

    if "faction" in char:
        del char["faction"]
        changes.append({
            "type": "character",
            "id": char_id,
            "field": "faction",
            "from": old_faction,
            "to": None
        })

    if "subfaction" in char:
        del char["subfaction"]
        changes.append({
            "type": "character",
            "id": char_id,
            "field": "subfaction",
            "from": old_subfaction,
            "to": None
        })

    # Save character file
    char_file = find_source_file("characters", char_id, search_root)
    if char_file:
        with open(char_file, 'w', encoding='utf-8') as f:
            json.dump(char, f, indent=2)

    # Remove from faction's members.named
    members = faction.get("members", {})
    named = members.get("named", [])
    named_lower = [m.lower() for m in named]

    if char_id.lower() in named_lower:
        # Find and remove (case-insensitive)
        idx = named_lower.index(char_id.lower())
        removed = named.pop(idx)

        # Save faction file
        faction_file = find_source_file("factions", faction_id, search_root)
        if faction_file:
            with open(faction_file, 'w', encoding='utf-8') as f:
                json.dump(faction, f, indent=2)
            changes.append({
                "type": "faction",
                "id": faction_id,
                "field": "members.named",
                "action": "remove",
                "value": removed
            })

    # Log to changelog
    changelog = load_changelog(search_root)
    entry = changelog.add(
        session=session or "current",
        character=char_id,
        tier="development",
        field="faction",
        from_value=old_faction,
        to_value=None,
        reason=f"Removed from {faction_display}"
    )

    if output_json:
        print(json.dumps({
            "action": "remove-member",
            "faction": faction_id,
            "character": char_id,
            "changes": changes,
            "change_id": entry.id
        }, indent=2))
    else:
        print(f"Removed {char_display} from {faction_display}")
        if old_subfaction:
            print(f"  Cleared subfaction: {old_subfaction}")
        print(f"  Character faction field cleared")
        print(f"  Removed from faction members.named list")
        print(f"Change logged: {entry.id}")


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
        print("  tree <name> [--depth N]        Show faction hierarchy tree")
        print("\nMember management:")
        print("  members <name> [--subfaction SUB] [--unit UNIT]")
        print("                                 Show faction members")
        print("  add-member <faction> <char> [--subfaction SUB]")
        print("                                 Add character to faction")
        print("  remove-member <faction> <char> Remove character from faction")
        print("\nRelationship management:")
        print("  relationships <name> [--type TYPE] [--json]")
        print("                                 Show faction relationships")
        print("  add-relationship <faction> --type TYPE --target TARGET")
        print("                   [--state '{...}'] [--notes '...'] [--reason '...']")
        print("                                 Add a relationship edge")
        print("  update-relationship <faction> --target TARGET --field FIELD --value VAL")
        print("                   [--reason '...']  Update relationship field")
        print("  remove-relationship <faction> --target TARGET [--reason '...']")
        print("                                 Remove a relationship edge")
        print("\nStub commands (not yet implemented):")
        print("  economy <name>                 Show faction economy")
        print("\nCreate options:")
        print("  --name NAME                    Faction display name (required)")
        print("  --type TYPE                    Faction type: fleet|house|organization|military|other (required)")
        print("  --essence TEXT                 Core essence, 35 words max (required)")
        print("  --parent PARENT_ID             Parent faction ID (optional)")
        print("  --tags TAGS                    Comma-separated tags")
        print("  --json                         Output as JSON")
        print("\nTree options:")
        print("  --depth N                      Limit tree depth (default: unlimited)")
        print("\nFilters (for list):")
        print("  --type TYPE                    Filter by type")
        print("  --tag NAME                     Filter by tag")
        print("\nMember options:")
        print("  --subfaction NAME              Filter by or set subfaction")
        print("  --unit NAME                    Filter by unit")
        print("  --session NAME                 Session identifier for changelog")
        print("\nRelationship options:")
        print("  --type TYPE                    Relationship type: ally|enemy|rival|debtor|creditor|")
        print("                                   vassal|patron|reports_to|neutral (or custom)")
        print("  --target TARGET                Target faction or character ID")
        print("  --state '{...}'                JSON object with state fields")
        print("  --notes '...'                  Freeform notes about the relationship")
        print("  --reason '...'                 Reason for the change (changelog)")
        print("\nRelationship type schemas (expected state fields):")
        print("  debtor/creditor: principal, rate, accruing")
        print("  ally: trust, terms")
        print("  enemy: threat, conflict")
        print("  rival: tension, domain")
        print("  vassal: obligations, tribute")
        print("  patron: protection, expectations")
        print("  reports_to: via, bypasses")
        print("  (all types allow additional freeform fields)")
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
    parent = None
    # Tree-specific options
    tree_depth = None
    # Second positional for add-member/remove-member
    character_name = None
    # Member command options
    subfaction_filter = None
    unit_filter = None
    # Relationship command options
    target = None
    state_json = None
    notes = None

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
            # For tree command, parse as integer
            try:
                tree_depth = int(depth)
            except ValueError:
                pass  # Keep as string for get command
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
        elif arg == "--parent" and i + 1 < len(sys.argv):
            parent = sys.argv[i + 1]
            i += 2
        elif arg == "--subfaction" and i + 1 < len(sys.argv):
            subfaction_filter = sys.argv[i + 1]
            i += 2
        elif arg == "--unit" and i + 1 < len(sys.argv):
            unit_filter = sys.argv[i + 1]
            i += 2
        elif arg == "--target" and i + 1 < len(sys.argv):
            target = sys.argv[i + 1]
            i += 2
        elif arg == "--state" and i + 1 < len(sys.argv):
            state_json = sys.argv[i + 1]
            i += 2
        elif arg == "--notes" and i + 1 < len(sys.argv):
            notes = sys.argv[i + 1]
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
            parent=parent,
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
        cmd_members(faction_name, subfaction_filter, unit_filter, output_json)
    elif command == "economy":
        if not faction_name:
            print("Error: faction name required", file=sys.stderr)
            sys.exit(1)
        cmd_economy(faction_name)
    elif command == "tree":
        if not faction_name:
            print("Error: faction name required", file=sys.stderr)
            sys.exit(1)
        cmd_tree(faction_name, tree_depth)
    elif command == "relationships":
        if not faction_name:
            print("Error: faction name required", file=sys.stderr)
            sys.exit(1)
        cmd_relationships(faction_name, faction_type, output_json)
    elif command == "add-relationship":
        if not faction_name:
            print("Error: faction name required", file=sys.stderr)
            sys.exit(1)
        if not faction_type:
            print("Error: --type required for add-relationship", file=sys.stderr)
            sys.exit(1)
        if not target:
            print("Error: --target required for add-relationship", file=sys.stderr)
            sys.exit(1)
        cmd_add_relationship(
            faction_name, faction_type, target, state_json, notes,
            reason, session_name, output_json
        )
    elif command == "update-relationship":
        if not faction_name:
            print("Error: faction name required", file=sys.stderr)
            sys.exit(1)
        if not target:
            print("Error: --target required for update-relationship", file=sys.stderr)
            sys.exit(1)
        if not field:
            print("Error: --field required for update-relationship", file=sys.stderr)
            sys.exit(1)
        if not value:
            print("Error: --value required for update-relationship", file=sys.stderr)
            sys.exit(1)
        cmd_update_relationship(
            faction_name, target, field, value, reason, session_name, output_json
        )
    elif command == "remove-relationship":
        if not faction_name:
            print("Error: faction name required", file=sys.stderr)
            sys.exit(1)
        if not target:
            print("Error: --target required for remove-relationship", file=sys.stderr)
            sys.exit(1)
        cmd_remove_relationship(faction_name, target, reason, session_name, output_json)
    elif command == "add-member":
        if not faction_name:
            print("Error: faction name required", file=sys.stderr)
            sys.exit(1)
        if not character_name:
            print("Error: character name required", file=sys.stderr)
            sys.exit(1)
        cmd_add_member(faction_name, character_name, subfaction_filter, unit_filter, session_name, output_json)
    elif command == "remove-member":
        if not faction_name:
            print("Error: faction name required", file=sys.stderr)
            sys.exit(1)
        if not character_name:
            print("Error: character name required", file=sys.stderr)
            sys.exit(1)
        cmd_remove_member(faction_name, character_name, session_name, output_json)
    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
