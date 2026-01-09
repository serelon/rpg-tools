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

    # Include structured resources if present
    resources = faction.get("resources", {})
    if resources:
        lines.append("\n## Resources (Tracked)")
        for res_name, res_data in resources.items():
            # Handle both structured and simple format
            if isinstance(res_data, (int, float)):
                lines.append(f"- {res_name.replace('_', ' ').title()}: {res_data:,}")
            elif isinstance(res_data, str):
                lines.append(f"- {res_name.replace('_', ' ').title()}: {res_data}")
            elif isinstance(res_data, dict):
                current = res_data.get("current", 0)
                capacity = res_data.get("capacity")
                unit = res_data.get("unit", "")
                if capacity is not None and capacity > 0:
                    pct = (current / capacity * 100) if capacity > 0 else 0
                    if unit:
                        lines.append(f"- {res_name.replace('_', ' ').title()}: {current:,}/{capacity:,} {unit} ({pct:.0f}%)")
                    else:
                        lines.append(f"- {res_name.replace('_', ' ').title()}: {current:,}/{capacity:,} ({pct:.0f}%)")
                else:
                    if unit:
                        lines.append(f"- {res_name.replace('_', ' ').title()}: {current:,} {unit}")
                    else:
                        lines.append(f"- {res_name.replace('_', ' ').title()}: {current:,}")
            else:
                lines.append(f"- {res_name.replace('_', ' ').title()}: {res_data}")

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


def format_md(faction: Dict, search_root: Path) -> str:
    """Format faction as a comprehensive markdown 'character sheet'."""
    lines = []
    faction_id = faction.get("id", "unknown")
    name = faction.get("name", faction_id)
    faction_type = faction.get("type", "")
    minimal = faction.get("minimal", {})

    # Header
    lines.append(f"# {name}")
    lines.append("")

    # Identity section
    lines.append("## Identity")
    if faction_type:
        lines.append(f"- **Type:** {faction_type}")
    if minimal.get("essence"):
        lines.append(f"- **Essence:** {minimal['essence']}")
    if minimal.get("current_status"):
        lines.append(f"- **Status:** {minimal['current_status']}")
    tags = faction.get("tags", [])
    if tags:
        lines.append(f"- **Tags:** {', '.join(tags)}")
    if faction.get("autonomous"):
        lines.append("- **Autonomous:** yes")
    lines.append("")

    # Hierarchy section
    parent = get_parent(faction)
    children = get_children(faction_id)
    if parent or children or faction.get("parent"):
        lines.append("## Hierarchy")
        if parent:
            parent_name = parent.get("name", parent.get("id", "Unknown"))
            lines.append(f"- **Parent:** {parent_name}")
        elif faction.get("parent"):
            lines.append(f"- **Parent:** {faction['parent']} [not found]")
        if children:
            lines.append("- **Subfactions:**")
            for child in children:
                child_name = child.get("name", child.get("id", "Unknown"))
                child_type = child.get("type", "")
                type_str = f" ({child_type})" if child_type else ""
                lines.append(f"  - {child_name}{type_str}")
        lines.append("")

    # Members section
    members = faction.get("members", {})
    named = members.get("named", [])
    units = members.get("units", [])
    pools = members.get("pools", [])
    if named or units or pools:
        lines.append("## Members")
        if named:
            lines.append("### Named Characters")
            for member_id in named:
                lines.append(f"- {member_id}")
        if units:
            lines.append("### Units")
            for unit in units:
                unit_name = unit.get("name", unit.get("id", "Unknown"))
                count = unit.get("count", 0)
                role = unit.get("role", "")
                morale = unit.get("morale", "")
                details = []
                if role:
                    details.append(f"role: {role}")
                if morale:
                    details.append(f"morale: {morale}")
                detail_str = f" - {', '.join(details)}" if details else ""
                lines.append(f"- {unit_name} ({count}){detail_str}")
        if pools:
            lines.append("### Pools")
            for pool in pools:
                desc = pool.get("description", pool.get("id", "Unknown"))
                count = pool.get("count", 0)
                state = pool.get("state", "")
                state_str = f" - {state}" if state else ""
                lines.append(f"- {desc} ({count}){state_str}")
        lines.append("")

    # Relationships section
    relationships = faction.get("relationships", [])
    if relationships:
        lines.append("## Relationships")
        # Group by type
        by_type: Dict[str, List[Dict]] = {}
        for rel in relationships:
            rtype = rel.get("type", "unknown")
            if rtype not in by_type:
                by_type[rtype] = []
            by_type[rtype].append(rel)
        for rtype in sorted(by_type.keys()):
            lines.append(f"### {rtype.title()}")
            for rel in by_type[rtype]:
                target = rel.get("target", "unknown")
                state = rel.get("state", {})
                notes = rel.get("notes", "")
                state_parts = []
                for k, v in state.items():
                    state_parts.append(f"{k}={v}")
                state_str = f" ({', '.join(state_parts)})" if state_parts else ""
                lines.append(f"- {target}{state_str}")
                if notes:
                    lines.append(f"  - Notes: {notes}")
        lines.append("")

    # Economy section
    economy = faction.get("economy", {})
    if economy:
        lines.append("## Economy")
        accounts = economy.get("accounts", [])
        running_costs = economy.get("running_costs", [])
        inventory = economy.get("inventory", [])
        assets = economy.get("assets", [])

        # Calculate summary
        liquid = sum(a.get("balance", 0) for a in accounts if a.get("category") == "liquid")
        receivables = sum(a.get("balance", 0) for a in accounts if a.get("category") == "receivable")
        payables = sum(a.get("balance", 0) for a in accounts if a.get("category") == "payable")
        net_worth = liquid + receivables + payables
        monthly_burn = sum(
            c.get("amount", 0) if c.get("period", "monthly") == "monthly"
            else c.get("amount", 0) // 12
            for c in running_costs
        )

        lines.append(f"- **Liquid Assets:** {liquid:,} cr")
        lines.append(f"- **Receivables:** {receivables:,} cr")
        lines.append(f"- **Payables:** {payables:,} cr")
        lines.append(f"- **Net Worth:** {net_worth:,} cr")
        if monthly_burn > 0:
            lines.append(f"- **Monthly Burn:** {monthly_burn:,} cr")
            if liquid > 0:
                runway = liquid / monthly_burn
                lines.append(f"- **Runway:** {runway:.1f} months")
        if inventory:
            lines.append(f"- **Inventory Items:** {len(inventory)}")
        if assets:
            lines.append(f"- **Assets:** {len(assets)}")
        lines.append("")

    # Resources section
    resources = faction.get("resources", {})
    if resources:
        lines.append("## Resources")
        for res_name, res_data in resources.items():
            # Handle both structured and simple format
            if isinstance(res_data, (int, float)):
                lines.append(f"- **{res_name.replace('_', ' ').title()}:** {res_data:,}")
            elif isinstance(res_data, str):
                lines.append(f"- **{res_name.replace('_', ' ').title()}:** {res_data}")
            elif isinstance(res_data, dict):
                current = res_data.get("current", 0)
                capacity = res_data.get("capacity")
                unit = res_data.get("unit", "")
                if capacity is not None and capacity > 0:
                    pct = (current / capacity * 100) if capacity > 0 else 0
                    if unit:
                        lines.append(f"- **{res_name.replace('_', ' ').title()}:** {current:,}/{capacity:,} {unit} ({pct:.0f}%)")
                    else:
                        lines.append(f"- **{res_name.replace('_', ' ').title()}:** {current:,}/{capacity:,} ({pct:.0f}%)")
                else:
                    if unit:
                        lines.append(f"- **{res_name.replace('_', ' ').title()}:** {current:,} {unit}")
                    else:
                        lines.append(f"- **{res_name.replace('_', ' ').title()}:** {current:,}")
            else:
                lines.append(f"- **{res_name.replace('_', ' ').title()}:** {res_data}")
        lines.append("")

    # Full description/narrative sections
    full = faction.get("full", {})
    if full.get("description"):
        lines.append("## Description")
        lines.append(full["description"])
        lines.append("")
    if full.get("history"):
        lines.append("## History")
        lines.append(full["history"])
        lines.append("")
    if full.get("goals"):
        lines.append("## Goals")
        lines.append(full["goals"])
        lines.append("")
    if full.get("structure"):
        lines.append("## Structure")
        lines.append(full["structure"])
        lines.append("")

    # Custom sections
    sections = faction.get("sections", {})
    for section_name, section_data in sections.items():
        lines.append(f"## {section_name.replace('_', ' ').title()}")
        if isinstance(section_data, dict):
            for key, value in section_data.items():
                if isinstance(value, list):
                    lines.append(f"### {key.replace('_', ' ').title()}")
                    for item in value:
                        if isinstance(item, dict):
                            # Format as key-value pairs
                            parts = [f"{k}: {v}" for k, v in item.items()]
                            lines.append(f"- {', '.join(parts)}")
                        else:
                            lines.append(f"- {item}")
                elif isinstance(value, dict):
                    lines.append(f"### {key.replace('_', ' ').title()}")
                    for k, v in value.items():
                        lines.append(f"- **{k}:** {v}")
                else:
                    lines.append(f"- **{key.replace('_', ' ').title()}:** {value}")
        elif isinstance(section_data, list):
            for item in section_data:
                if isinstance(item, dict):
                    era = item.get("era", "")
                    event = item.get("event", str(item))
                    if era:
                        lines.append(f"- **{era}:** {event}")
                    else:
                        lines.append(f"- {event}")
                else:
                    lines.append(f"- {item}")
        else:
            lines.append(str(section_data))
        lines.append("")

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
    section: Optional[str] = None,
    output_format: Optional[str] = None
) -> None:
    """Get a faction's profile at specified depth."""
    search_root = Path.cwd()
    faction = find_item(factions, faction_name, "Faction")

    if output_format == "md":
        print(format_md(faction, search_root))
    elif section:
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


# Account categories for economy
ACCOUNT_CATEGORIES = ["liquid", "receivable", "payable", "other"]


def calculate_net_worth(economy: Dict) -> Dict[str, int]:
    """Calculate net worth from economy accounts.

    Returns dict with liquid, receivables, payables, and net_worth totals.
    """
    accounts = economy.get("accounts", [])

    liquid = sum(a.get("balance", 0) for a in accounts if a.get("category") == "liquid")
    receivables = sum(a.get("balance", 0) for a in accounts if a.get("category") == "receivable")
    payables = sum(a.get("balance", 0) for a in accounts if a.get("category") == "payable")
    other = sum(a.get("balance", 0) for a in accounts if a.get("category") == "other")

    return {
        "liquid": liquid,
        "receivables": receivables,
        "payables": payables,
        "other": other,
        "net_worth": liquid + receivables + payables + other
    }


def calculate_monthly_burn(economy: Dict) -> int:
    """Calculate total monthly burn from running costs.

    Monthly costs are summed directly, annual costs are divided by 12.
    """
    costs = economy.get("running_costs", [])
    total = 0

    for cost in costs:
        amount = cost.get("amount", 0)
        period = cost.get("period", "monthly").lower()

        if period == "monthly":
            total += amount
        elif period == "annual":
            total += amount // 12

    return total


def calculate_runway(liquid: int, monthly_burn: int) -> Optional[float]:
    """Calculate runway in months (liquid / monthly_burn).

    Returns None if monthly_burn is zero.
    """
    if monthly_burn <= 0:
        return None
    return liquid / monthly_burn


def find_account(economy: Dict, account_id: str) -> Optional[Dict]:
    """Find an account by ID."""
    accounts = economy.get("accounts", [])
    account_id_lower = account_id.lower()

    for account in accounts:
        if account.get("id", "").lower() == account_id_lower:
            return account

    return None


def find_running_cost(economy: Dict, cost_id: str) -> Optional[Dict]:
    """Find a running cost by ID."""
    costs = economy.get("running_costs", [])
    cost_id_lower = cost_id.lower()

    for cost in costs:
        if cost.get("id", "").lower() == cost_id_lower:
            return cost

    return None


def format_economy_summary(faction: Dict) -> str:
    """Format economy summary view."""
    name = faction.get("name", faction.get("id", "Unknown"))
    economy = faction.get("economy", {})

    # Calculate totals
    totals = calculate_net_worth(economy)
    monthly_burn = calculate_monthly_burn(economy)
    runway = calculate_runway(totals["liquid"], monthly_burn)

    lines = [f"# {name} Economy", "", "## Summary"]

    # Assets and liabilities
    lines.append(f"Liquid Assets:     {format_number(totals['liquid']):>12} cr")
    lines.append(f"Receivables:       {format_number(totals['receivables']):>12} cr")
    lines.append(f"Payables:          {format_number(totals['payables']):>12} cr")
    if totals["other"] != 0:
        lines.append(f"Other:             {format_number(totals['other']):>12} cr")
    lines.append("-" * 37)
    lines.append(f"Net Worth:         {format_number(totals['net_worth']):>12} cr")
    lines.append("")
    lines.append(f"Monthly Burn:      {format_number(monthly_burn):>12} cr")

    if runway is not None:
        lines.append(f"Runway:            {runway:>11.1f} months")
    else:
        lines.append("Runway:                     N/A")

    return "\n".join(lines)


def format_economy_accounts(faction: Dict) -> str:
    """Format economy accounts view."""
    name = faction.get("name", faction.get("id", "Unknown"))
    economy = faction.get("economy", {})
    accounts = economy.get("accounts", [])

    lines = [f"# {name} Economy", "", "## Accounts"]

    if not accounts:
        lines.append("No accounts defined")
        return "\n".join(lines)

    for account in accounts:
        acc_id = account.get("id", "unknown")
        balance = account.get("balance", 0)
        category = account.get("category", "other")
        notes = account.get("notes", "")
        interest = account.get("interest")

        # Build line
        parts = [f"- {acc_id}: {format_number(balance)} cr"]

        if interest is not None:
            if isinstance(interest, float) and interest < 1:
                parts.append(f"@ {int(interest * 100)}% annual")
            else:
                parts.append(f"@ {interest}% annual")

        parts.append(f"({category})")

        if notes:
            parts.append(f"- {notes}")

        lines.append(" ".join(parts))

    return "\n".join(lines)


def format_economy_costs(faction: Dict) -> str:
    """Format economy running costs view."""
    name = faction.get("name", faction.get("id", "Unknown"))
    economy = faction.get("economy", {})
    costs = economy.get("running_costs", [])

    lines = [f"# {name} Economy", "", "## Running Costs (Monthly)"]

    if not costs:
        lines.append("No running costs defined")
        return "\n".join(lines)

    total_monthly = 0

    for cost in costs:
        desc = cost.get("description", cost.get("id", "unknown"))
        amount = cost.get("amount", 0)
        period = cost.get("period", "monthly").lower()
        formula = cost.get("formula")

        # Calculate monthly equivalent
        if period == "monthly":
            monthly = amount
        else:  # annual
            monthly = amount // 12

        total_monthly += monthly

        # Build line
        line = f"- {desc}: {format_number(monthly)} cr"

        if formula:
            line += f" (= {formula})"
        elif period == "annual":
            line += f" ({format_number(amount)}/year)"

        lines.append(line)

    lines.append("-" * 37)
    lines.append(f"Total Monthly Burn: {format_number(total_monthly)} cr")

    return "\n".join(lines)


def format_economy_full(faction: Dict) -> str:
    """Format complete economy view (summary + accounts + costs)."""
    parts = [
        format_economy_summary(faction),
        "",
        format_economy_accounts(faction).split("\n", 3)[-1] if faction.get("economy", {}).get("accounts") else "",
        "",
        format_economy_costs(faction).split("\n", 3)[-1] if faction.get("economy", {}).get("running_costs") else ""
    ]

    # Clean up empty parts
    return "\n".join(p for p in parts if p.strip())


def cmd_economy(
    faction_name: str,
    show_accounts: bool = False,
    show_costs: bool = False,
    show_inventory: bool = False,
    show_assets: bool = False,
    show_summary: bool = True,
    output_json: bool = False
) -> None:
    """Show faction economy."""
    faction = find_item(factions, faction_name, "Faction")
    faction_id = faction.get("id", faction_name)

    economy = faction.get("economy", {})
    inventory = economy.get("inventory", [])
    assets = economy.get("assets", [])

    if output_json:
        # Calculate totals for JSON output
        totals = calculate_net_worth(economy)
        monthly_burn = calculate_monthly_burn(economy)
        inv_value = calculate_inventory_value(inventory)
        asset_value = calculate_asset_value(assets)
        asset_maint = calculate_asset_maintenance(assets)
        total_monthly = monthly_burn + asset_maint
        runway = calculate_runway(totals["liquid"], total_monthly)

        result = {
            "faction": faction_id,
            "accounts": economy.get("accounts", []),
            "running_costs": economy.get("running_costs", []),
            "inventory": inventory,
            "assets": assets,
            "summary": {
                "liquid": totals["liquid"],
                "receivables": totals["receivables"],
                "payables": totals["payables"],
                "other": totals["other"],
                "inventory_value": inv_value,
                "asset_value": asset_value,
                "net_worth": totals["net_worth"] + inv_value + asset_value,
                "monthly_burn": monthly_burn,
                "asset_maintenance": asset_maint,
                "total_monthly_burn": total_monthly,
                "runway_months": round(runway, 1) if runway else None
            }
        }
        print(json.dumps(result, indent=2))
        return

    # Determine what to show (single view flags)
    if show_inventory:
        print(format_economy_inventory(faction))
    elif show_assets:
        print(format_economy_assets(faction))
    elif show_accounts and not show_costs:
        print(format_economy_accounts(faction))
    elif show_costs and not show_accounts:
        print(format_economy_costs(faction))
    elif show_accounts and show_costs:
        print(format_economy_full(faction))
    else:
        # Default: enhanced summary including inventory/asset values
        name = faction.get("name", faction.get("id", "Unknown"))
        totals = calculate_net_worth(economy)
        monthly_burn = calculate_monthly_burn(economy)
        inv_value = calculate_inventory_value(inventory)
        asset_value = calculate_asset_value(assets)
        asset_maint = calculate_asset_maintenance(assets)
        total_monthly = monthly_burn + asset_maint
        runway = calculate_runway(totals["liquid"], total_monthly)

        lines = [f"# {name} Economy", "", "## Summary"]

        # Assets and liabilities
        lines.append(f"Liquid Assets:     {format_number(totals['liquid']):>12} cr")
        lines.append(f"Receivables:       {format_number(totals['receivables']):>12} cr")
        lines.append(f"Payables:          {format_number(totals['payables']):>12} cr")
        if totals["other"] != 0:
            lines.append(f"Other:             {format_number(totals['other']):>12} cr")
        if inv_value > 0:
            lines.append(f"Inventory Value:   {format_number(inv_value):>12} cr")
        if asset_value > 0:
            lines.append(f"Asset Value:       {format_number(asset_value):>12} cr")
        lines.append("-" * 37)
        total_net_worth = totals["net_worth"] + inv_value + asset_value
        lines.append(f"Net Worth:         {format_number(total_net_worth):>12} cr")
        lines.append("")
        lines.append(f"Monthly Burn:      {format_number(monthly_burn):>12} cr")
        if asset_maint > 0:
            lines.append(f"Asset Maintenance: {format_number(asset_maint):>12} cr")
            lines.append(f"Total Monthly:     {format_number(total_monthly):>12} cr")

        if runway is not None:
            lines.append(f"Runway:            {runway:>11.1f} months")
        else:
            lines.append("Runway:                     N/A")

        print("\n".join(lines))


def cmd_add_account(
    faction_name: str,
    account_id: str,
    category: str,
    balance: int,
    interest: Optional[float] = None,
    notes: Optional[str] = None,
    reason: Optional[str] = None,
    session: Optional[str] = None,
    output_json: bool = False
) -> None:
    """Add an account to a faction's economy."""
    search_root = Path.cwd()

    faction = find_item(factions, faction_name, "Faction")
    faction_id = faction.get("id", faction_name)
    faction_display = faction.get("name", faction_id)

    # Validate category
    if category not in ACCOUNT_CATEGORIES:
        print(f"Error: Invalid category '{category}'. Must be one of: {', '.join(ACCOUNT_CATEGORIES)}", file=sys.stderr)
        sys.exit(1)

    # Initialize economy if needed
    if "economy" not in faction:
        faction["economy"] = {}
    if "accounts" not in faction["economy"]:
        faction["economy"]["accounts"] = []

    # Check for duplicate ID
    existing = find_account(faction["economy"], account_id)
    if existing:
        print(f"Error: Account '{account_id}' already exists", file=sys.stderr)
        sys.exit(1)

    # Build account
    account = {
        "id": account_id,
        "category": category,
        "balance": balance
    }

    if interest is not None:
        account["interest"] = interest

    if notes:
        account["notes"] = notes

    # Add to accounts
    faction["economy"]["accounts"].append(account)

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
        tier="state",
        field="economy.accounts",
        from_value=None,
        to_value=account,
        reason=reason or f"Added {category} account: {account_id}"
    )

    if output_json:
        print(json.dumps({
            "action": "add-account",
            "faction": faction_id,
            "account": account,
            "change_id": entry.id
        }, indent=2))
    else:
        print(f"Added account to {faction_display}")
        print(f"  ID: {account_id}")
        print(f"  Category: {category}")
        print(f"  Balance: {format_number(balance)} cr")
        if interest is not None:
            print(f"  Interest: {interest}")
        if notes:
            print(f"  Notes: {notes}")
        print(f"Change logged: {entry.id}")


def cmd_update_account(
    faction_name: str,
    account_id: str,
    balance: Optional[int] = None,
    interest: Optional[float] = None,
    notes: Optional[str] = None,
    reason: Optional[str] = None,
    session: Optional[str] = None,
    output_json: bool = False
) -> None:
    """Update an account's balance or other fields."""
    search_root = Path.cwd()

    faction = find_item(factions, faction_name, "Faction")
    faction_id = faction.get("id", faction_name)
    faction_display = faction.get("name", faction_id)

    economy = faction.get("economy", {})
    account = find_account(economy, account_id)

    if not account:
        print(f"Error: Account '{account_id}' not found", file=sys.stderr)
        sys.exit(1)

    # Track old values
    old_balance = account.get("balance")
    old_interest = account.get("interest")
    old_notes = account.get("notes")

    changes = []

    # Apply updates
    if balance is not None:
        account["balance"] = balance
        if old_balance != balance:
            changes.append(f"balance: {format_number(old_balance)} -> {format_number(balance)}")

    if interest is not None:
        account["interest"] = interest
        if old_interest != interest:
            changes.append(f"interest: {old_interest} -> {interest}")

    if notes is not None:
        if notes == "":
            # Remove notes if empty string
            account.pop("notes", None)
            if old_notes:
                changes.append(f"notes: removed")
        else:
            account["notes"] = notes
            if old_notes != notes:
                changes.append(f"notes: updated")

    if not changes:
        print("No changes made")
        return

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
        tier="state",
        field=f"economy.accounts[{account_id}].balance",
        from_value=old_balance,
        to_value=balance if balance is not None else old_balance,
        reason=reason or f"Updated account {account_id}"
    )

    if output_json:
        print(json.dumps({
            "action": "update-account",
            "faction": faction_id,
            "account_id": account_id,
            "changes": changes,
            "account": account,
            "change_id": entry.id
        }, indent=2))
    else:
        print(f"Updated account {account_id} for {faction_display}")
        for change in changes:
            print(f"  {change}")
        print(f"Change logged: {entry.id}")


def cmd_remove_account(
    faction_name: str,
    account_id: str,
    reason: Optional[str] = None,
    session: Optional[str] = None,
    output_json: bool = False
) -> None:
    """Remove an account from a faction's economy."""
    search_root = Path.cwd()

    faction = find_item(factions, faction_name, "Faction")
    faction_id = faction.get("id", faction_name)
    faction_display = faction.get("name", faction_id)

    economy = faction.get("economy", {})
    accounts = economy.get("accounts", [])

    # Find and remove account
    account_id_lower = account_id.lower()
    removed = None
    idx = -1

    for i, account in enumerate(accounts):
        if account.get("id", "").lower() == account_id_lower:
            removed = account
            idx = i
            break

    if removed is None:
        print(f"Error: Account '{account_id}' not found", file=sys.stderr)
        sys.exit(1)

    # Remove the account
    del accounts[idx]

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
        tier="state",
        field="economy.accounts",
        from_value=removed,
        to_value=None,
        reason=reason or f"Removed account {account_id}"
    )

    if output_json:
        print(json.dumps({
            "action": "remove-account",
            "faction": faction_id,
            "removed": removed,
            "change_id": entry.id
        }, indent=2))
    else:
        print(f"Removed account {account_id} from {faction_display}")
        print(f"  Balance was: {format_number(removed.get('balance', 0))} cr")
        print(f"Change logged: {entry.id}")


def cmd_add_cost(
    faction_name: str,
    cost_id: str,
    description: str,
    amount: int,
    period: str = "monthly",
    formula: Optional[str] = None,
    reason: Optional[str] = None,
    session: Optional[str] = None,
    output_json: bool = False
) -> None:
    """Add a running cost to a faction's economy."""
    search_root = Path.cwd()

    faction = find_item(factions, faction_name, "Faction")
    faction_id = faction.get("id", faction_name)
    faction_display = faction.get("name", faction_id)

    # Validate period
    if period.lower() not in ("monthly", "annual"):
        print(f"Error: Invalid period '{period}'. Must be 'monthly' or 'annual'", file=sys.stderr)
        sys.exit(1)

    # Initialize economy if needed
    if "economy" not in faction:
        faction["economy"] = {}
    if "running_costs" not in faction["economy"]:
        faction["economy"]["running_costs"] = []

    # Check for duplicate ID
    existing = find_running_cost(faction["economy"], cost_id)
    if existing:
        print(f"Error: Running cost '{cost_id}' already exists", file=sys.stderr)
        sys.exit(1)

    # Build cost
    cost = {
        "id": cost_id,
        "description": description,
        "amount": amount,
        "period": period.lower()
    }

    if formula:
        cost["formula"] = formula

    # Add to running costs
    faction["economy"]["running_costs"].append(cost)

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
        tier="state",
        field="economy.running_costs",
        from_value=None,
        to_value=cost,
        reason=reason or f"Added running cost: {description}"
    )

    if output_json:
        print(json.dumps({
            "action": "add-cost",
            "faction": faction_id,
            "cost": cost,
            "change_id": entry.id
        }, indent=2))
    else:
        print(f"Added running cost to {faction_display}")
        print(f"  ID: {cost_id}")
        print(f"  Description: {description}")
        print(f"  Amount: {format_number(amount)} cr/{period.lower()}")
        if formula:
            print(f"  Formula: {formula}")
        print(f"Change logged: {entry.id}")


def cmd_update_cost(
    faction_name: str,
    cost_id: str,
    amount: Optional[int] = None,
    description: Optional[str] = None,
    period: Optional[str] = None,
    formula: Optional[str] = None,
    reason: Optional[str] = None,
    session: Optional[str] = None,
    output_json: bool = False
) -> None:
    """Update a running cost's amount or other fields."""
    search_root = Path.cwd()

    faction = find_item(factions, faction_name, "Faction")
    faction_id = faction.get("id", faction_name)
    faction_display = faction.get("name", faction_id)

    economy = faction.get("economy", {})
    cost = find_running_cost(economy, cost_id)

    if not cost:
        print(f"Error: Running cost '{cost_id}' not found", file=sys.stderr)
        sys.exit(1)

    # Track old values
    old_amount = cost.get("amount")
    old_description = cost.get("description")
    old_period = cost.get("period")
    old_formula = cost.get("formula")

    changes = []

    # Apply updates
    if amount is not None:
        cost["amount"] = amount
        if old_amount != amount:
            changes.append(f"amount: {format_number(old_amount)} -> {format_number(amount)}")

    if description is not None:
        cost["description"] = description
        if old_description != description:
            changes.append(f"description: updated")

    if period is not None:
        if period.lower() not in ("monthly", "annual"):
            print(f"Error: Invalid period '{period}'. Must be 'monthly' or 'annual'", file=sys.stderr)
            sys.exit(1)
        cost["period"] = period.lower()
        if old_period != period.lower():
            changes.append(f"period: {old_period} -> {period.lower()}")

    if formula is not None:
        if formula == "":
            # Remove formula if empty string
            cost.pop("formula", None)
            if old_formula:
                changes.append(f"formula: removed")
        else:
            cost["formula"] = formula
            if old_formula != formula:
                changes.append(f"formula: updated")

    if not changes:
        print("No changes made")
        return

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
        tier="state",
        field=f"economy.running_costs[{cost_id}].amount",
        from_value=old_amount,
        to_value=amount if amount is not None else old_amount,
        reason=reason or f"Updated running cost {cost_id}"
    )

    if output_json:
        print(json.dumps({
            "action": "update-cost",
            "faction": faction_id,
            "cost_id": cost_id,
            "changes": changes,
            "cost": cost,
            "change_id": entry.id
        }, indent=2))
    else:
        print(f"Updated running cost {cost_id} for {faction_display}")
        for change in changes:
            print(f"  {change}")
        print(f"Change logged: {entry.id}")


def cmd_remove_cost(
    faction_name: str,
    cost_id: str,
    reason: Optional[str] = None,
    session: Optional[str] = None,
    output_json: bool = False
) -> None:
    """Remove a running cost from a faction's economy."""
    search_root = Path.cwd()

    faction = find_item(factions, faction_name, "Faction")
    faction_id = faction.get("id", faction_name)
    faction_display = faction.get("name", faction_id)

    economy = faction.get("economy", {})
    costs = economy.get("running_costs", [])

    # Find and remove cost
    cost_id_lower = cost_id.lower()
    removed = None
    idx = -1

    for i, cost in enumerate(costs):
        if cost.get("id", "").lower() == cost_id_lower:
            removed = cost
            idx = i
            break

    if removed is None:
        print(f"Error: Running cost '{cost_id}' not found", file=sys.stderr)
        sys.exit(1)

    # Remove the cost
    del costs[idx]

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
        tier="state",
        field="economy.running_costs",
        from_value=removed,
        to_value=None,
        reason=reason or f"Removed running cost {cost_id}"
    )

    if output_json:
        print(json.dumps({
            "action": "remove-cost",
            "faction": faction_id,
            "removed": removed,
            "change_id": entry.id
        }, indent=2))
    else:
        desc = removed.get("description", cost_id)
        print(f"Removed running cost from {faction_display}")
        print(f"  {desc}: {format_number(removed.get('amount', 0))} cr/{removed.get('period', 'monthly')}")
        print(f"Change logged: {entry.id}")


# Inventory and asset helpers

def format_inventory_item(item: Dict) -> List[str]:
    """Format a single inventory item for display."""
    lines = []
    name = item.get("item", item.get("id", "Unknown"))
    quantity = item.get("quantity", "")
    value = item.get("value")
    location = item.get("location")
    legality = item.get("legality", "legal")
    notes = item.get("notes")

    # Build main line
    parts = [f"- {name}"]
    if quantity:
        if isinstance(quantity, (int, float)):
            parts.append(f": {format_number(quantity)}")
        else:
            parts.append(f": {quantity}")
    if value is not None:
        parts.append(f", value: {format_number(value)} cr")

    # Add legality if not legal
    if legality and legality.lower() != "legal":
        parts.append(f" [{legality}]")

    # Add location
    if location:
        parts.append(f" (location: {location})")

    lines.append("".join(parts))

    # Add notes on separate line
    if notes:
        lines.append(f"  Notes: {notes}")

    return lines


def format_asset(asset: Dict) -> List[str]:
    """Format a single asset for display."""
    lines = []
    name = asset.get("name", asset.get("id", "Unknown"))
    asset_type = asset.get("type", "")
    value = asset.get("value")
    details = asset.get("details", {})

    # Build main line
    type_str = f" ({asset_type})" if asset_type else ""
    value_str = f": {format_number(value)} cr" if value is not None else ""
    lines.append(f"- {name}{type_str}{value_str}")

    # Format details based on type
    if asset_type == "vessel" and details:
        capacity = details.get("capacity")
        current_load = details.get("current_load")
        configuration = details.get("configuration")
        maintenance_cost = details.get("maintenance_cost")

        detail_parts = []
        if capacity is not None:
            if current_load is not None:
                pct = (current_load / capacity * 100) if capacity > 0 else 0
                detail_parts.append(f"Capacity: {format_number(capacity)}t, Load: {format_number(current_load)}t ({pct:.0f}%)")
            else:
                detail_parts.append(f"Capacity: {format_number(capacity)}t")
        if configuration:
            detail_parts.append(f"Configuration: {configuration}")
        if maintenance_cost is not None:
            detail_parts.append(f"Maintenance: {format_number(maintenance_cost)} cr/month")

        for part in detail_parts:
            lines.append(f"  {part}")
    elif details:
        # Generic details formatting
        for key, val in details.items():
            if isinstance(val, (dict, list)):
                lines.append(f"  {key}: {json.dumps(val)}")
            else:
                lines.append(f"  {key}: {val}")

    return lines


def find_inventory_item(faction: Dict, item_id: str) -> Optional[Dict]:
    """Find an inventory item by ID."""
    economy = faction.get("economy", {})
    inventory = economy.get("inventory", [])
    item_lower = item_id.lower()

    for item in inventory:
        if item.get("id", "").lower() == item_lower:
            return item

    return None


def find_asset(faction: Dict, asset_id: str) -> Optional[Dict]:
    """Find an asset by ID."""
    economy = faction.get("economy", {})
    assets = economy.get("assets", [])
    asset_lower = asset_id.lower()

    for asset in assets:
        if asset.get("id", "").lower() == asset_lower:
            return asset

    return None


def calculate_inventory_value(inventory: List[Dict]) -> int:
    """Calculate total value of inventory items."""
    total = 0
    for item in inventory:
        value = item.get("value")
        if value is not None and isinstance(value, (int, float)):
            total += value
    return int(total)


def calculate_asset_value(assets: List[Dict]) -> int:
    """Calculate total value of assets."""
    total = 0
    for asset in assets:
        value = asset.get("value")
        if value is not None and isinstance(value, (int, float)):
            total += value
    return int(total)


def calculate_asset_maintenance(assets: List[Dict]) -> int:
    """Calculate total maintenance cost of assets."""
    total = 0
    for asset in assets:
        details = asset.get("details", {})
        maintenance = details.get("maintenance_cost")
        if maintenance is not None and isinstance(maintenance, (int, float)):
            total += maintenance
    return int(total)


# ============================================================================
# Resource Management
# ============================================================================

def find_resource(faction: Dict, resource_name: str) -> Optional[Dict]:
    """Find a resource by name (case-insensitive)."""
    resources = faction.get("resources", {})
    name_lower = resource_name.lower()

    for name, resource in resources.items():
        if name.lower() == name_lower:
            return {"name": name, **resource}

    return None


def format_resource(name: str, resource: Any) -> str:
    """Format a single resource for display.

    Handles both structured format (dict with current/capacity/unit)
    and simple format (int/string value).
    """
    # Handle simple format (just a value)
    if isinstance(resource, (int, float)):
        return f"- {name.replace('_', ' ').title()}: {format_number(resource)}"
    elif isinstance(resource, str):
        return f"- {name.replace('_', ' ').title()}: {resource}"
    elif not isinstance(resource, dict):
        return f"- {name.replace('_', ' ').title()}: {resource}"

    # Handle structured format
    current = resource.get("current", 0)
    capacity = resource.get("capacity")
    unit = resource.get("unit", "")

    # Build the display string
    if capacity is not None and capacity > 0:
        pct = (current / capacity * 100) if capacity > 0 else 0
        if unit:
            return f"- {name.replace('_', ' ').title()}: {format_number(current)}/{format_number(capacity)} {unit} ({pct:.0f}%)"
        else:
            return f"- {name.replace('_', ' ').title()}: {format_number(current)}/{format_number(capacity)} ({pct:.0f}%)"
    else:
        if unit:
            return f"- {name.replace('_', ' ').title()}: {format_number(current)} {unit}"
        else:
            return f"- {name.replace('_', ' ').title()}: {format_number(current)}"


def format_resources(faction: Dict) -> str:
    """Format all resources for a faction."""
    name = faction.get("name", faction.get("id", "Unknown"))
    resources = faction.get("resources", {})

    lines = [f"# {name} Resources"]

    if not resources:
        lines.append("\nNo resources defined")
        return "\n".join(lines)

    lines.append("")
    for res_name, res_data in resources.items():
        lines.append(format_resource(res_name, res_data))

    return "\n".join(lines)


def cmd_resources(
    faction_name: str,
    output_json: bool = False
) -> None:
    """Show faction resources."""
    faction = find_item(factions, faction_name, "Faction")
    faction_id = faction.get("id", faction_name)

    resources = faction.get("resources", {})

    if output_json:
        result = {
            "faction": faction_id,
            "resources": resources
        }
        print(json.dumps(result, indent=2))
        return

    print(format_resources(faction))


def cmd_resources_set(
    faction_name: str,
    resource_name: str,
    current: int,
    capacity: Optional[int] = None,
    unit: Optional[str] = None,
    reason: Optional[str] = None,
    session: Optional[str] = None,
    output_json: bool = False
) -> None:
    """Set (create or replace) a resource for a faction."""
    search_root = Path.cwd()

    faction = find_item(factions, faction_name, "Faction")
    faction_id = faction.get("id", faction_name)
    faction_display = faction.get("name", faction_id)

    # Initialize resources if needed
    if "resources" not in faction:
        faction["resources"] = {}

    # Get old value if exists
    old_resource = faction["resources"].get(resource_name)

    # Build new resource
    resource: Dict[str, Any] = {"current": current}
    if capacity is not None:
        resource["capacity"] = capacity
    if unit is not None:
        resource["unit"] = unit

    # Set the resource
    faction["resources"][resource_name] = resource

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
        tier="state",
        field=f"resources.{resource_name}",
        from_value=old_resource,
        to_value=resource,
        reason=reason or f"Set resource: {resource_name}"
    )

    if output_json:
        print(json.dumps({
            "action": "set-resource",
            "faction": faction_id,
            "resource_name": resource_name,
            "resource": resource,
            "replaced": old_resource is not None,
            "change_id": entry.id
        }, indent=2))
    else:
        action = "Updated" if old_resource else "Added"
        print(f"{action} resource for {faction_display}")
        print(f"  Name: {resource_name}")
        print(f"  Current: {format_number(current)}")
        if capacity is not None:
            print(f"  Capacity: {format_number(capacity)}")
        if unit:
            print(f"  Unit: {unit}")
        print(f"Change logged: {entry.id}")


def cmd_resources_update(
    faction_name: str,
    resource_name: str,
    current: int,
    reason: Optional[str] = None,
    session: Optional[str] = None,
    output_json: bool = False
) -> None:
    """Update a resource's current value."""
    search_root = Path.cwd()

    faction = find_item(factions, faction_name, "Faction")
    faction_id = faction.get("id", faction_name)
    faction_display = faction.get("name", faction_id)

    resources = faction.get("resources", {})

    # Find the resource (case-insensitive)
    actual_name = None
    for name in resources.keys():
        if name.lower() == resource_name.lower():
            actual_name = name
            break

    if not actual_name:
        print(f"Error: Resource '{resource_name}' not found", file=sys.stderr)
        sys.exit(1)

    resource = resources[actual_name]
    old_current = resource.get("current")

    # Update current value
    resource["current"] = current

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
        tier="state",
        field=f"resources.{actual_name}.current",
        from_value=old_current,
        to_value=current,
        reason=reason or f"Updated resource {actual_name}: {old_current} -> {current}"
    )

    if output_json:
        print(json.dumps({
            "action": "update-resource",
            "faction": faction_id,
            "resource_name": actual_name,
            "from": old_current,
            "to": current,
            "change_id": entry.id
        }, indent=2))
    else:
        unit = resource.get("unit", "")
        capacity = resource.get("capacity")
        print(f"Updated resource {actual_name} for {faction_display}")
        if capacity:
            old_pct = (old_current / capacity * 100) if capacity > 0 and old_current else 0
            new_pct = (current / capacity * 100) if capacity > 0 else 0
            print(f"  {format_number(old_current)}/{format_number(capacity)} ({old_pct:.0f}%) -> {format_number(current)}/{format_number(capacity)} ({new_pct:.0f}%)")
        else:
            print(f"  {format_number(old_current)} -> {format_number(current)}{' ' + unit if unit else ''}")
        print(f"Change logged: {entry.id}")


def cmd_resources_remove(
    faction_name: str,
    resource_name: str,
    reason: Optional[str] = None,
    session: Optional[str] = None,
    output_json: bool = False
) -> None:
    """Remove a resource from a faction."""
    search_root = Path.cwd()

    faction = find_item(factions, faction_name, "Faction")
    faction_id = faction.get("id", faction_name)
    faction_display = faction.get("name", faction_id)

    resources = faction.get("resources", {})

    # Find the resource (case-insensitive)
    actual_name = None
    for name in resources.keys():
        if name.lower() == resource_name.lower():
            actual_name = name
            break

    if not actual_name:
        print(f"Error: Resource '{resource_name}' not found", file=sys.stderr)
        sys.exit(1)

    removed = resources.pop(actual_name)

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
        tier="state",
        field=f"resources.{actual_name}",
        from_value=removed,
        to_value=None,
        reason=reason or f"Removed resource: {actual_name}"
    )

    if output_json:
        print(json.dumps({
            "action": "remove-resource",
            "faction": faction_id,
            "resource_name": actual_name,
            "removed": removed,
            "change_id": entry.id
        }, indent=2))
    else:
        print(f"Removed resource {actual_name} from {faction_display}")
        current = removed.get("current", 0)
        capacity = removed.get("capacity")
        unit = removed.get("unit", "")
        if capacity:
            print(f"  Was: {format_number(current)}/{format_number(capacity)} {unit}")
        else:
            print(f"  Was: {format_number(current)} {unit}")
        print(f"Change logged: {entry.id}")


def format_economy_inventory(faction: Dict) -> str:
    """Format economy inventory view."""
    name = faction.get("name", faction.get("id", "Unknown"))
    economy = faction.get("economy", {})
    inventory = economy.get("inventory", [])

    lines = [f"# {name} Economy", "", "## Inventory"]

    if not inventory:
        lines.append("No inventory items")
        return "\n".join(lines)

    for item in inventory:
        lines.extend(format_inventory_item(item))

    inv_value = calculate_inventory_value(inventory)
    lines.append(f"\nTotal Inventory Value: {format_number(inv_value)} cr")

    return "\n".join(lines)


def format_economy_assets(faction: Dict) -> str:
    """Format economy assets view."""
    name = faction.get("name", faction.get("id", "Unknown"))
    economy = faction.get("economy", {})
    assets = economy.get("assets", [])

    lines = [f"# {name} Economy", "", "## Assets"]

    if not assets:
        lines.append("No assets")
        return "\n".join(lines)

    for asset in assets:
        lines.extend(format_asset(asset))

    asset_value = calculate_asset_value(assets)
    asset_maint = calculate_asset_maintenance(assets)
    lines.append(f"\nTotal Asset Value: {format_number(asset_value)} cr")
    if asset_maint > 0:
        lines.append(f"Total Asset Maintenance: {format_number(asset_maint)} cr/month")

    return "\n".join(lines)


def cmd_add_item(
    faction_name: str,
    item_id: str,
    item_name: str,
    quantity: str,
    value: Optional[int] = None,
    location: Optional[str] = None,
    legality: str = "legal",
    notes: Optional[str] = None,
    reason: Optional[str] = None,
    session: Optional[str] = None,
    output_json: bool = False
) -> None:
    """Add an inventory item to a faction."""
    search_root = Path.cwd()

    faction = find_item(factions, faction_name, "Faction")
    faction_id = faction.get("id", faction_name)
    faction_display = faction.get("name", faction_id)

    # Check for existing item with same ID
    existing = find_inventory_item(faction, item_id)
    if existing:
        print(f"Error: Inventory item '{item_id}' already exists", file=sys.stderr)
        print("  Use update-item to modify it, or remove-item first", file=sys.stderr)
        sys.exit(1)

    # Parse quantity (could be number or string like "15% capacity")
    parsed_quantity: Any = quantity
    try:
        if '.' in quantity:
            parsed_quantity = float(quantity)
        else:
            parsed_quantity = int(quantity)
    except ValueError:
        pass  # Keep as string

    # Build item
    item: Dict[str, Any] = {
        "id": item_id,
        "item": item_name,
        "quantity": parsed_quantity
    }

    if value is not None:
        item["value"] = value
    if location:
        item["location"] = location
    if legality and legality.lower() != "legal":
        item["legality"] = legality
    if notes:
        item["notes"] = notes

    # Ensure economy.inventory exists
    if "economy" not in faction:
        faction["economy"] = {}
    if "inventory" not in faction["economy"]:
        faction["economy"]["inventory"] = []

    faction["economy"]["inventory"].append(item)

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
        tier="state",
        field="economy.inventory",
        from_value=None,
        to_value=item,
        reason=reason or f"Added inventory item: {item_name}"
    )

    if output_json:
        print(json.dumps({
            "action": "add-item",
            "faction": faction_id,
            "item": item,
            "change_id": entry.id
        }, indent=2))
    else:
        print(f"Added inventory item to {faction_display}")
        print(f"  ID: {item_id}")
        print(f"  Item: {item_name}")
        print(f"  Quantity: {parsed_quantity}")
        if value is not None:
            print(f"  Value: {format_number(value)} cr")
        if location:
            print(f"  Location: {location}")
        if legality and legality.lower() != "legal":
            print(f"  Legality: {legality}")
        if notes:
            print(f"  Notes: {notes}")
        print(f"Change logged: {entry.id}")


def cmd_update_item(
    faction_name: str,
    item_id: str,
    quantity: Optional[str] = None,
    value: Optional[int] = None,
    reason: Optional[str] = None,
    session: Optional[str] = None,
    output_json: bool = False
) -> None:
    """Update an inventory item."""
    search_root = Path.cwd()

    faction = find_item(factions, faction_name, "Faction")
    faction_id = faction.get("id", faction_name)
    faction_display = faction.get("name", faction_id)

    # Find the item
    item = find_inventory_item(faction, item_id)
    if not item:
        print(f"Error: Inventory item '{item_id}' not found", file=sys.stderr)
        sys.exit(1)

    changes = []

    if quantity is not None:
        old_quantity = item.get("quantity")
        # Parse quantity
        parsed_quantity: Any = quantity
        try:
            if '.' in quantity:
                parsed_quantity = float(quantity)
            else:
                parsed_quantity = int(quantity)
        except ValueError:
            pass  # Keep as string
        item["quantity"] = parsed_quantity
        changes.append({"field": "quantity", "from": old_quantity, "to": parsed_quantity})

    if value is not None:
        old_value = item.get("value")
        item["value"] = value
        changes.append({"field": "value", "from": old_value, "to": value})

    if not changes:
        print("Error: No changes specified (use --quantity or --value)", file=sys.stderr)
        sys.exit(1)

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
        tier="state",
        field=f"economy.inventory[{item_id}]",
        from_value={c["field"]: c["from"] for c in changes},
        to_value={c["field"]: c["to"] for c in changes},
        reason=reason or f"Updated inventory item: {item_id}"
    )

    if output_json:
        print(json.dumps({
            "action": "update-item",
            "faction": faction_id,
            "item_id": item_id,
            "changes": changes,
            "change_id": entry.id
        }, indent=2))
    else:
        item_name = item.get("item", item_id)
        print(f"Updated inventory item in {faction_display}")
        print(f"  Item: {item_name}")
        for change in changes:
            fld = change["field"]
            from_val = change["from"]
            to_val = change["to"]
            if fld == "value":
                from_str = f"{format_number(from_val)} cr" if from_val is not None else "none"
                to_str = f"{format_number(to_val)} cr"
                print(f"  {fld}: {from_str} -> {to_str}")
            else:
                print(f"  {fld}: {from_val} -> {to_val}")
        print(f"Change logged: {entry.id}")


def cmd_remove_item(
    faction_name: str,
    item_id: str,
    reason: Optional[str] = None,
    session: Optional[str] = None,
    output_json: bool = False
) -> None:
    """Remove an inventory item from a faction."""
    search_root = Path.cwd()

    faction = find_item(factions, faction_name, "Faction")
    faction_id = faction.get("id", faction_name)
    faction_display = faction.get("name", faction_id)

    # Find the item
    economy = faction.get("economy", {})
    inventory = economy.get("inventory", [])
    item_lower = item_id.lower()

    removed = None
    idx = -1
    for i, item in enumerate(inventory):
        if item.get("id", "").lower() == item_lower:
            removed = item
            idx = i
            break

    if removed is None:
        print(f"Error: Inventory item '{item_id}' not found", file=sys.stderr)
        sys.exit(1)

    # Remove the item
    del inventory[idx]

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
        tier="state",
        field="economy.inventory",
        from_value=removed,
        to_value=None,
        reason=reason or f"Removed inventory item: {removed.get('item', item_id)}"
    )

    if output_json:
        print(json.dumps({
            "action": "remove-item",
            "faction": faction_id,
            "removed": removed,
            "change_id": entry.id
        }, indent=2))
    else:
        item_name = removed.get("item", item_id)
        print(f"Removed inventory item from {faction_display}")
        print(f"  Item: {item_name}")
        print(f"Change logged: {entry.id}")


def cmd_add_asset(
    faction_name: str,
    asset_id: str,
    asset_name: str,
    asset_type: str,
    value: int,
    details: Optional[str] = None,
    reason: Optional[str] = None,
    session: Optional[str] = None,
    output_json: bool = False
) -> None:
    """Add an asset to a faction."""
    search_root = Path.cwd()

    faction = find_item(factions, faction_name, "Faction")
    faction_id = faction.get("id", faction_name)
    faction_display = faction.get("name", faction_id)

    # Check for existing asset with same ID
    existing = find_asset(faction, asset_id)
    if existing:
        print(f"Error: Asset '{asset_id}' already exists", file=sys.stderr)
        print("  Use update-asset to modify it, or remove-asset first", file=sys.stderr)
        sys.exit(1)

    # Parse details JSON if provided
    details_dict = {}
    if details:
        try:
            details_dict = json.loads(details)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in --details: {e}", file=sys.stderr)
            sys.exit(1)

    # Build asset
    asset: Dict[str, Any] = {
        "id": asset_id,
        "name": asset_name,
        "type": asset_type,
        "value": value
    }

    if details_dict:
        asset["details"] = details_dict

    # Ensure economy.assets exists
    if "economy" not in faction:
        faction["economy"] = {}
    if "assets" not in faction["economy"]:
        faction["economy"]["assets"] = []

    faction["economy"]["assets"].append(asset)

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
        tier="state",
        field="economy.assets",
        from_value=None,
        to_value=asset,
        reason=reason or f"Added asset: {asset_name}"
    )

    if output_json:
        print(json.dumps({
            "action": "add-asset",
            "faction": faction_id,
            "asset": asset,
            "change_id": entry.id
        }, indent=2))
    else:
        print(f"Added asset to {faction_display}")
        print(f"  ID: {asset_id}")
        print(f"  Name: {asset_name}")
        print(f"  Type: {asset_type}")
        print(f"  Value: {format_number(value)} cr")
        if details_dict:
            print(f"  Details: {details_dict}")
        print(f"Change logged: {entry.id}")


def cmd_update_asset(
    faction_name: str,
    asset_id: str,
    field: str,
    value: str,
    reason: Optional[str] = None,
    session: Optional[str] = None,
    output_json: bool = False
) -> None:
    """Update an asset field."""
    search_root = Path.cwd()

    faction = find_item(factions, faction_name, "Faction")
    faction_id = faction.get("id", faction_name)
    faction_display = faction.get("name", faction_id)

    # Find the asset
    asset = find_asset(faction, asset_id)
    if not asset:
        print(f"Error: Asset '{asset_id}' not found", file=sys.stderr)
        sys.exit(1)

    # Navigate to the field (supports dot notation like details.capacity)
    parts = field.split('.')
    obj = asset
    for part in parts[:-1]:
        if part not in obj:
            obj[part] = {}
        obj = obj[part]

    final_key = parts[-1]
    old_value = obj.get(final_key)

    # Try to parse value as JSON or number
    parsed_value: Any = value
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
        tier="state",
        field=f"economy.assets[{asset_id}].{field}",
        from_value=old_value,
        to_value=parsed_value,
        reason=reason or f"Updated asset: {asset_id}"
    )

    if output_json:
        print(json.dumps({
            "action": "update-asset",
            "faction": faction_id,
            "asset_id": asset_id,
            "field": field,
            "from": old_value,
            "to": parsed_value,
            "change_id": entry.id
        }, indent=2))
    else:
        asset_name = asset.get("name", asset_id)
        print(f"Updated asset in {faction_display}")
        print(f"  Asset: {asset_name}")
        print(f"  {field}: {old_value} -> {parsed_value}")
        print(f"Change logged: {entry.id}")


def cmd_remove_asset(
    faction_name: str,
    asset_id: str,
    reason: Optional[str] = None,
    session: Optional[str] = None,
    output_json: bool = False
) -> None:
    """Remove an asset from a faction."""
    search_root = Path.cwd()

    faction = find_item(factions, faction_name, "Faction")
    faction_id = faction.get("id", faction_name)
    faction_display = faction.get("name", faction_id)

    # Find the asset
    economy = faction.get("economy", {})
    assets = economy.get("assets", [])
    asset_lower = asset_id.lower()

    removed = None
    idx = -1
    for i, asset in enumerate(assets):
        if asset.get("id", "").lower() == asset_lower:
            removed = asset
            idx = i
            break

    if removed is None:
        print(f"Error: Asset '{asset_id}' not found", file=sys.stderr)
        sys.exit(1)

    # Remove the asset
    del assets[idx]

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
        tier="state",
        field="economy.assets",
        from_value=removed,
        to_value=None,
        reason=reason or f"Removed asset: {removed.get('name', asset_id)}"
    )

    if output_json:
        print(json.dumps({
            "action": "remove-asset",
            "faction": faction_id,
            "removed": removed,
            "change_id": entry.id
        }, indent=2))
    else:
        asset_name = removed.get("name", asset_id)
        print(f"Removed asset from {faction_display}")
        print(f"  Asset: {asset_name}")
        print(f"Change logged: {entry.id}")


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


def cmd_validate(
    faction_name: str,
    fix: bool = False,
    output_json: bool = False
) -> None:
    """Validate a faction's data integrity."""
    search_root = Path.cwd()

    # Discover characters if not already loaded
    if not characters:
        discover_characters(search_root)

    faction = find_item(factions, faction_name, "Faction")
    faction_id = faction.get("id", faction_name)
    faction_display = faction.get("name", faction_id)

    issues = []
    fixes_applied = []

    # Check required fields
    if not faction.get("id"):
        issues.append({"type": "missing_field", "field": "id", "severity": "error"})
    if not faction.get("name"):
        issues.append({"type": "missing_field", "field": "name", "severity": "error"})
    if not faction.get("type"):
        issues.append({"type": "missing_field", "field": "type", "severity": "warning"})
    minimal = faction.get("minimal", {})
    if not minimal.get("essence"):
        issues.append({"type": "missing_field", "field": "minimal.essence", "severity": "warning"})

    # Check parent faction exists
    parent_id = faction.get("parent")
    if parent_id:
        if parent_id not in factions:
            # Try case-insensitive search
            parent_found = False
            for f in factions.values():
                if f.get("id", "").lower() == parent_id.lower():
                    parent_found = True
                    break
            if not parent_found:
                issues.append({
                    "type": "parent_not_found",
                    "parent_id": parent_id,
                    "severity": "error"
                })

    # Check relationship targets exist
    relationships = faction.get("relationships", [])
    for rel in relationships:
        target = rel.get("target", "")
        if target:
            target_exists, _ = validate_target_exists(target)
            if not target_exists:
                issues.append({
                    "type": "relationship_target_not_found",
                    "target": target,
                    "relationship_type": rel.get("type", "unknown"),
                    "severity": "warning"
                })

    # Check member characters exist and have matching faction field
    members = faction.get("members", {})
    named_members = members.get("named", [])
    for member_id in named_members:
        # Find character
        char = None
        member_lower = member_id.lower()
        for c in characters.values():
            if c.get("id", "").lower() == member_lower:
                char = c
                break
            if c.get("name", "").lower() == member_lower:
                char = c
                break

        if not char:
            issues.append({
                "type": "member_character_not_found",
                "member_id": member_id,
                "severity": "warning"
            })
        else:
            char_faction = char.get("faction", "")
            if char_faction.lower() != faction_id.lower():
                issues.append({
                    "type": "member_faction_mismatch",
                    "member_id": member_id,
                    "character_name": char.get("name", member_id),
                    "expected_faction": faction_id,
                    "actual_faction": char_faction or "(none)",
                    "severity": "warning",
                    "fixable": True
                })

                # Apply fix if requested
                if fix:
                    char["faction"] = faction_id
                    char_file = find_source_file("characters", char.get("id", member_id), search_root)
                    if char_file:
                        with open(char_file, 'w', encoding='utf-8') as f:
                            json.dump(char, f, indent=2)
                        fixes_applied.append({
                            "type": "set_character_faction",
                            "character_id": char.get("id", member_id),
                            "faction": faction_id
                        })

    # Check for orphaned subfactions (this faction has parent that doesn't exist)
    # Already handled above in parent check

    if output_json:
        result = {
            "faction": faction_id,
            "valid": len([i for i in issues if i.get("severity") == "error"]) == 0,
            "issues": issues,
            "fixes_applied": fixes_applied if fix else []
        }
        print(json.dumps(result, indent=2))
        return

    # Human-readable output
    errors = [i for i in issues if i.get("severity") == "error"]
    warnings = [i for i in issues if i.get("severity") == "warning"]

    if not issues:
        print(f"Validation passed: {faction_display}")
        return

    print(f"Validation results for {faction_display}:")
    print()

    if errors:
        print(f"Errors ({len(errors)}):")
        for issue in errors:
            if issue["type"] == "missing_field":
                print(f"  - Missing required field: {issue['field']}")
            elif issue["type"] == "parent_not_found":
                print(f"  - Parent faction not found: {issue['parent_id']}")

    if warnings:
        print(f"\nWarnings ({len(warnings)}):")
        for issue in warnings:
            if issue["type"] == "missing_field":
                print(f"  - Missing recommended field: {issue['field']}")
            elif issue["type"] == "relationship_target_not_found":
                print(f"  - Relationship target not found: {issue['target']} ({issue['relationship_type']})")
            elif issue["type"] == "member_character_not_found":
                print(f"  - Member character not found: {issue['member_id']}")
            elif issue["type"] == "member_faction_mismatch":
                fixable_str = " [fixable]" if issue.get("fixable") else ""
                print(f"  - Member {issue['character_name']} has faction '{issue['actual_faction']}', expected '{issue['expected_faction']}'{fixable_str}")

    if fixes_applied:
        print(f"\nFixes applied ({len(fixes_applied)}):")
        for fix_item in fixes_applied:
            if fix_item["type"] == "set_character_faction":
                print(f"  - Set {fix_item['character_id']}.faction = {fix_item['faction']}")

    if not fix:
        fixable = [i for i in issues if i.get("fixable")]
        if fixable:
            print(f"\n{len(fixable)} issue(s) can be auto-fixed with --fix")


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
        print("  get <name> --format md         Get full markdown 'character sheet'")
        print("  sections <name>                List available sections")
        print("  validate <name> [--fix]        Validate faction data integrity")
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
        print("\nEconomy management:")
        print("  economy <name> [--accounts] [--costs] [--inventory] [--assets]")
        print("                   [--summary] [--json]   Show faction economy")
        print("  economy <name> add-account --id ID --category CAT --balance N")
        print("                   [--interest RATE] [--notes '...']")
        print("                                 Add an economy account")
        print("  economy <name> update-account ID --balance N [--reason '...']")
        print("                                 Update account balance")
        print("  economy <name> remove-account ID [--reason '...']")
        print("                                 Remove an account")
        print("  economy <name> add-cost --id ID --description '...' --amount N")
        print("                   [--period monthly|annual] [--formula '...']")
        print("                                 Add a running cost")
        print("  economy <name> update-cost ID --amount N [--reason '...']")
        print("                                 Update running cost")
        print("  economy <name> remove-cost ID [--reason '...']")
        print("                                 Remove a running cost")
        print("  economy <name> add-item --id ID --item NAME --quantity Q --value V")
        print("                   [--location LOC] [--legality LEG] [--notes '...']")
        print("                                 Add inventory item")
        print("  economy <name> update-item ID [--quantity Q] [--value V] [--location LOC]")
        print("                   [--legality LEG] [--notes '...'] [--reason '...']")
        print("                                 Update inventory item")
        print("  economy <name> remove-item ID [--reason '...']")
        print("                                 Remove inventory item")
        print("  economy <name> add-asset --id ID --name NAME --asset-type TYPE --value V")
        print("                   [--details '{...}'] [--notes '...']")
        print("                                 Add an asset (ships, property, etc.)")
        print("  economy <name> update-asset ID [--value V] [--details '{...}']")
        print("                   [--notes '...'] [--reason '...']")
        print("                                 Update asset fields")
        print("  economy <name> remove-asset ID [--reason '...']")
        print("                                 Remove an asset")
        print("\nResource management:")
        print("  resources <name> [--json]      Show faction resources")
        print("  resources <name> set RESOURCE_NAME --current N [--capacity N] [--unit UNIT]")
        print("                   [--reason '...']   Set/create a resource")
        print("  resources <name> update RESOURCE_NAME --current N [--reason '...']")
        print("                                 Update resource current value")
        print("  resources <name> remove RESOURCE_NAME [--reason '...']")
        print("                                 Remove a resource")
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
        print("\nEconomy options:")
        print("  --accounts                     Show accounts only")
        print("  --costs                        Show running costs only")
        print("  --inventory                    Show inventory only")
        print("  --assets                       Show assets only")
        print("  --summary                      Show summary (default)")
        print("  --id ID                        Account, cost, item, or asset ID")
        print("  --category CAT                 Account category: liquid|receivable|payable|other")
        print("  --balance N                    Account balance (positive for assets, negative for liabilities)")
        print("  --interest RATE                Interest rate (decimal, e.g., 0.19 for 19%)")
        print("  --amount N                     Running cost amount")
        print("  --period PERIOD                Cost period: monthly|annual (default: monthly)")
        print("  --description TEXT             Cost description")
        print("  --formula TEXT                 Cost formula (documentation only)")
        print("\nInventory/Asset options:")
        print("  --item NAME                    Item name for inventory")
        print("  --quantity Q                   Quantity (number or string like '15% capacity')")
        print("  --location LOC                 Storage location")
        print("  --legality LEG                 Legality status (legal, restricted, contraband)")
        print("  --asset-type TYPE              Asset type (ship, property, vehicle, etc.)")
        print("  --details '{...}'              JSON object with asset details (e.g., class, tonnage)")
        print("  --notes '...'                  Freeform notes")
        print("\nResource options:")
        print("  --current N                    Current resource amount")
        print("  --capacity N                   Maximum capacity (optional)")
        print("  --unit UNIT                    Unit label (e.g., months, missiles, jumps)")
        print("\nValidate options:")
        print("  --fix                          Auto-fix fixable issues")
        print("\nFormat options:")
        print("  --format md                    Output as markdown 'character sheet'")
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
    # Economy command options
    show_accounts = False
    show_costs = False
    show_inventory = False
    show_assets = False
    show_summary = False
    item_id = None
    category = None
    balance = None
    interest = None
    amount = None
    period = None
    description = None
    formula = None
    # Inventory/asset specific options
    item_name = None
    quantity = None
    location = None
    legality = None
    details_json = None
    asset_type = None
    # Economy subcommand (add-account, update-account, etc.)
    economy_subcommand = None
    # Resource command options
    resource_subcommand = None
    resource_name = None
    current = None
    capacity = None
    unit = None
    # Format option
    output_format = None

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
        elif arg == "--accounts":
            show_accounts = True
            i += 1
        elif arg == "--costs":
            show_costs = True
            i += 1
        elif arg == "--summary":
            show_summary = True
            i += 1
        elif arg == "--id" and i + 1 < len(sys.argv):
            item_id = sys.argv[i + 1]
            i += 2
        elif arg == "--category" and i + 1 < len(sys.argv):
            category = sys.argv[i + 1]
            i += 2
        elif arg == "--balance" and i + 1 < len(sys.argv):
            try:
                balance = int(sys.argv[i + 1])
            except ValueError:
                print(f"Error: --balance must be an integer", file=sys.stderr)
                sys.exit(1)
            i += 2
        elif arg == "--interest" and i + 1 < len(sys.argv):
            try:
                interest = float(sys.argv[i + 1])
            except ValueError:
                print(f"Error: --interest must be a number", file=sys.stderr)
                sys.exit(1)
            i += 2
        elif arg == "--amount" and i + 1 < len(sys.argv):
            try:
                amount = int(sys.argv[i + 1])
            except ValueError:
                print(f"Error: --amount must be an integer", file=sys.stderr)
                sys.exit(1)
            i += 2
        elif arg == "--period" and i + 1 < len(sys.argv):
            period = sys.argv[i + 1]
            i += 2
        elif arg == "--description" and i + 1 < len(sys.argv):
            description = sys.argv[i + 1]
            i += 2
        elif arg == "--formula" and i + 1 < len(sys.argv):
            formula = sys.argv[i + 1]
            i += 2
        elif arg == "--inventory":
            show_inventory = True
            i += 1
        elif arg == "--assets":
            show_assets = True
            i += 1
        elif arg == "--item" and i + 1 < len(sys.argv):
            item_name = sys.argv[i + 1]
            i += 2
        elif arg == "--quantity" and i + 1 < len(sys.argv):
            quantity = sys.argv[i + 1]
            i += 2
        elif arg == "--location" and i + 1 < len(sys.argv):
            location = sys.argv[i + 1]
            i += 2
        elif arg == "--legality" and i + 1 < len(sys.argv):
            legality = sys.argv[i + 1]
            i += 2
        elif arg == "--details" and i + 1 < len(sys.argv):
            details_json = sys.argv[i + 1]
            i += 2
        elif arg == "--asset-type" and i + 1 < len(sys.argv):
            asset_type = sys.argv[i + 1]
            i += 2
        elif arg == "--current" and i + 1 < len(sys.argv):
            try:
                current = int(sys.argv[i + 1])
            except ValueError:
                print(f"Error: --current must be an integer", file=sys.stderr)
                sys.exit(1)
            i += 2
        elif arg == "--capacity" and i + 1 < len(sys.argv):
            try:
                capacity = int(sys.argv[i + 1])
            except ValueError:
                print(f"Error: --capacity must be an integer", file=sys.stderr)
                sys.exit(1)
            i += 2
        elif arg == "--unit" and i + 1 < len(sys.argv):
            unit = sys.argv[i + 1]
            i += 2
        elif arg == "--format" and i + 1 < len(sys.argv):
            output_format = sys.argv[i + 1]
            i += 2
        elif not arg.startswith("--"):
            # Positional argument
            if positional_count == 0:
                faction_name = arg
            elif positional_count == 1:
                # Check if this is an economy subcommand
                if command == "economy" and arg in ("add-account", "update-account", "remove-account",
                                                     "add-cost", "update-cost", "remove-cost",
                                                     "add-item", "update-item", "remove-item",
                                                     "add-asset", "update-asset", "remove-asset"):
                    economy_subcommand = arg
                # Check if this is a resources subcommand
                elif command == "resources" and arg in ("set", "update", "remove"):
                    resource_subcommand = arg
                else:
                    character_name = arg
            elif positional_count == 2:
                # For economy subcommands that need an ID as third positional
                if economy_subcommand in ("update-account", "remove-account", "update-cost", "remove-cost",
                                          "update-item", "remove-item", "update-asset", "remove-asset"):
                    item_id = arg
                # For resources subcommands that need a resource name as third positional
                elif resource_subcommand in ("set", "update", "remove"):
                    resource_name = arg
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
        cmd_get(faction_name, depth, section, output_format)
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

        if economy_subcommand == "add-account":
            if not item_id:
                print("Error: --id required for add-account", file=sys.stderr)
                sys.exit(1)
            if not category:
                print("Error: --category required for add-account", file=sys.stderr)
                sys.exit(1)
            if balance is None:
                print("Error: --balance required for add-account", file=sys.stderr)
                sys.exit(1)
            cmd_add_account(
                faction_name, item_id, category, balance,
                interest, notes, reason, session_name, output_json
            )
        elif economy_subcommand == "update-account":
            if not item_id:
                print("Error: account ID required for update-account", file=sys.stderr)
                sys.exit(1)
            cmd_update_account(
                faction_name, item_id, balance, interest, notes,
                reason, session_name, output_json
            )
        elif economy_subcommand == "remove-account":
            if not item_id:
                print("Error: account ID required for remove-account", file=sys.stderr)
                sys.exit(1)
            cmd_remove_account(faction_name, item_id, reason, session_name, output_json)
        elif economy_subcommand == "add-cost":
            if not item_id:
                print("Error: --id required for add-cost", file=sys.stderr)
                sys.exit(1)
            if not description:
                print("Error: --description required for add-cost", file=sys.stderr)
                sys.exit(1)
            if amount is None:
                print("Error: --amount required for add-cost", file=sys.stderr)
                sys.exit(1)
            cmd_add_cost(
                faction_name, item_id, description, amount,
                period or "monthly", formula, reason, session_name, output_json
            )
        elif economy_subcommand == "update-cost":
            if not item_id:
                print("Error: cost ID required for update-cost", file=sys.stderr)
                sys.exit(1)
            cmd_update_cost(
                faction_name, item_id, amount, description, period,
                formula, reason, session_name, output_json
            )
        elif economy_subcommand == "remove-cost":
            if not item_id:
                print("Error: cost ID required for remove-cost", file=sys.stderr)
                sys.exit(1)
            cmd_remove_cost(faction_name, item_id, reason, session_name, output_json)
        elif economy_subcommand == "add-item":
            if not item_id:
                print("Error: --id required for add-item", file=sys.stderr)
                sys.exit(1)
            if not item_name:
                print("Error: --item required for add-item", file=sys.stderr)
                sys.exit(1)
            if not quantity:
                print("Error: --quantity required for add-item", file=sys.stderr)
                sys.exit(1)
            # Parse value from --value if provided (reuse value variable)
            item_value = None
            if value:
                try:
                    item_value = int(value)
                except ValueError:
                    print(f"Error: --value must be an integer for add-item", file=sys.stderr)
                    sys.exit(1)
            cmd_add_item(
                faction_name, item_id, item_name, quantity, item_value,
                location, legality or "legal", notes, reason, session_name, output_json
            )
        elif economy_subcommand == "update-item":
            if not item_id:
                print("Error: item ID required for update-item", file=sys.stderr)
                sys.exit(1)
            # Parse value if provided
            item_value = None
            if value:
                try:
                    item_value = int(value)
                except ValueError:
                    print(f"Error: --value must be an integer for update-item", file=sys.stderr)
                    sys.exit(1)
            cmd_update_item(
                faction_name, item_id, quantity, item_value,
                reason, session_name, output_json
            )
        elif economy_subcommand == "remove-item":
            if not item_id:
                print("Error: item ID required for remove-item", file=sys.stderr)
                sys.exit(1)
            cmd_remove_item(faction_name, item_id, reason, session_name, output_json)
        elif economy_subcommand == "add-asset":
            if not item_id:
                print("Error: --id required for add-asset", file=sys.stderr)
                sys.exit(1)
            if not name:
                print("Error: --name required for add-asset", file=sys.stderr)
                sys.exit(1)
            if not asset_type:
                print("Error: --asset-type required for add-asset", file=sys.stderr)
                sys.exit(1)
            if not value:
                print("Error: --value required for add-asset", file=sys.stderr)
                sys.exit(1)
            try:
                asset_value = int(value)
            except ValueError:
                print(f"Error: --value must be an integer for add-asset", file=sys.stderr)
                sys.exit(1)
            cmd_add_asset(
                faction_name, item_id, name, asset_type, asset_value,
                details_json, reason, session_name, output_json
            )
        elif economy_subcommand == "update-asset":
            if not item_id:
                print("Error: asset ID required for update-asset", file=sys.stderr)
                sys.exit(1)
            if not field:
                print("Error: --field required for update-asset", file=sys.stderr)
                sys.exit(1)
            if not value:
                print("Error: --value required for update-asset", file=sys.stderr)
                sys.exit(1)
            cmd_update_asset(
                faction_name, item_id, field, value,
                reason, session_name, output_json
            )
        elif economy_subcommand == "remove-asset":
            if not item_id:
                print("Error: asset ID required for remove-asset", file=sys.stderr)
                sys.exit(1)
            cmd_remove_asset(faction_name, item_id, reason, session_name, output_json)
        else:
            # Default: show economy (summary, accounts, costs, inventory, or assets)
            cmd_economy(faction_name, show_accounts, show_costs, show_inventory, show_assets, show_summary, output_json)
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
    elif command == "resources":
        if not faction_name:
            print("Error: faction name required", file=sys.stderr)
            sys.exit(1)

        if resource_subcommand == "set":
            if not resource_name:
                print("Error: resource name required for set", file=sys.stderr)
                sys.exit(1)
            if current is None:
                print("Error: --current required for set", file=sys.stderr)
                sys.exit(1)
            cmd_resources_set(
                faction_name, resource_name, current, capacity, unit,
                reason, session_name, output_json
            )
        elif resource_subcommand == "update":
            if not resource_name:
                print("Error: resource name required for update", file=sys.stderr)
                sys.exit(1)
            if current is None:
                print("Error: --current required for update", file=sys.stderr)
                sys.exit(1)
            cmd_resources_update(
                faction_name, resource_name, current, reason, session_name, output_json
            )
        elif resource_subcommand == "remove":
            if not resource_name:
                print("Error: resource name required for remove", file=sys.stderr)
                sys.exit(1)
            cmd_resources_remove(
                faction_name, resource_name, reason, session_name, output_json
            )
        else:
            # Default: show resources
            cmd_resources(faction_name, output_json)
    elif command == "validate":
        if not faction_name:
            print("Error: faction name required", file=sys.stderr)
            sys.exit(1)
        cmd_validate(faction_name, force, output_json)
    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
