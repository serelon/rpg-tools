#!/usr/bin/env python3
"""Name generation tool for solo RPG games. Uses namesets only."""

import random
import re
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional

from lib import discover_data


# Custom namesets storage
custom_namesets = {}


def discover_namesets(repo_root: Path):
    """Discover namesets from campaign folders, tools/data, root namesets/, and user uploads."""
    global custom_namesets

    def on_warning(msg: str) -> None:
        # Suppress the standard "not found" warning, we have custom messaging
        if "No namesets files found" not in msg:
            print(msg, file=sys.stderr)

    custom_namesets = discover_data(
        "namesets",
        repo_root,
        loose_pattern="*-names.json",
        on_warning=on_warning
    )

    if not custom_namesets:
        print("Warning: No namesets found", file=sys.stderr)
    else:
        print(f"Loaded {len(custom_namesets)} namesets", file=sys.stderr)


def parse_format(format_str: str) -> List[Dict[str, Any]]:
    """Parse a format string into tokens."""
    tokens = []
    pattern = r'\{(\w+)\}|\[([^\]]+)\]|([^\{\[]+)'

    for match in re.finditer(pattern, format_str):
        if match.group(1):  # Placeholder {category}
            tokens.append({"type": "placeholder", "value": match.group(1)})
        elif match.group(2):  # Optional section [text]
            tokens.append({"type": "optional", "value": match.group(2)})
        elif match.group(3):  # Literal text
            tokens.append({"type": "literal", "value": match.group(3)})

    return tokens


def select_weighted(entries: List[Dict]) -> Dict:
    """Select an entry using frequency weighting."""
    total_frequency = sum(entry.get("frequency", 1) for entry in entries)
    rand = random.random() * total_frequency

    for entry in entries:
        rand -= entry.get("frequency", 1)
        if rand <= 0:
            return entry

    return entries[-1]


def select_weighted_group(groups: Dict[str, Dict]) -> str:
    """Select a group using weight values."""
    total_weight = sum(g.get("weight", 1) for g in groups.values())
    rand = random.random() * total_weight

    for group_id, group in groups.items():
        rand -= group.get("weight", 1)
        if rand <= 0:
            return group_id

    return list(groups.keys())[-1]


def select_weighted_source(sources: List[Dict]) -> Dict:
    """Select a source from aggregate nameset by weight."""
    total_weight = sum(s.get("weight", 1) for s in sources)
    rand = random.random() * total_weight

    for source in sources:
        rand -= source.get("weight", 1)
        if rand <= 0:
            return source

    return sources[-1]


def select_gender(gender_weights: Dict[str, int]) -> str:
    """Select gender using weights."""
    total = sum(gender_weights.values())
    rand = random.random() * total

    for gender, weight in gender_weights.items():
        rand -= weight
        if rand <= 0:
            return gender

    return list(gender_weights.keys())[-1]


def filter_by_gender(entries: List[Dict], gender: str) -> List[Dict]:
    """Filter name entries by gender. Includes unisex and unspecified names."""
    filtered = [e for e in entries if e.get("gender") in {gender, None, "unisex"}]
    return filtered if filtered else entries


def generate_single_name(
    nameset: Dict,
    format_str: str,
    gender: str
) -> str:
    """Generate a single name from a source nameset."""
    categories = nameset.get("nameCategories", {})

    # Legacy support for old format
    if not categories and "firstNames" in nameset:
        categories = {
            "firstName": nameset["firstNames"],
            "lastName": nameset.get("lastNames", [])
        }

    # Filter first names by gender
    first_names = categories.get("firstName", [])
    first_names = filter_by_gender(first_names, gender)

    filtered_categories = {
        "firstName": first_names,
        "lastName": categories.get("lastName", [])
    }

    return build_name_from_format(format_str, filtered_categories)


def generate_from_aggregate(
    nameset_id: str,
    count: int = 1,
    source_label: Optional[str] = None,
    gender: Optional[str] = None,
    return_source: bool = False
) -> List:
    """Generate names from an aggregate nameset by selecting source, then generating."""
    nameset = custom_namesets[nameset_id]
    sources = nameset.get("sources", [])
    gender_weights = nameset.get("genderWeights", {"male": 50, "female": 50})
    format_str = nameset.get("format", "{firstName} {lastName}")

    results = []
    used = set()

    for _ in range(count):
        attempts = 0
        while attempts < 100:
            # Select source by weight (or use forced source)
            if source_label:
                selected = next((s for s in sources if s.get("label") == source_label), None)
                if not selected:
                    print(f"Error: Source '{source_label}' not found", file=sys.stderr)
                    sys.exit(1)
            else:
                selected = select_weighted_source(sources)

            source_nameset_id = selected["nameset"]
            if source_nameset_id not in custom_namesets:
                print(f"Error: Source nameset '{source_nameset_id}' not found", file=sys.stderr)
                sys.exit(1)

            source_nameset = custom_namesets[source_nameset_id]
            label = selected.get("label", source_nameset_id)

            # Select gender
            selected_gender = gender if gender else select_gender(gender_weights)

            # Generate from source
            name = generate_single_name(source_nameset, format_str, selected_gender)

            if name.lower() not in used:
                if return_source:
                    results.append((name, label))
                else:
                    results.append(name)
                used.add(name.lower())
                break
            attempts += 1
        else:
            # Ran out of attempts, add anyway
            if return_source:
                results.append((name, label))
            else:
                results.append(name)

    return results


def generate_from_nameset_with_groups(
    nameset_id: str,
    count: int = 1,
    group: Optional[str] = None,
    gender: Optional[str] = None,
    return_group: bool = False
) -> List:
    """Generate names from a nameset that uses nameGroups.

    If return_group is True, returns list of (name, group) tuples.
    Otherwise returns list of names.
    """
    nameset = custom_namesets[nameset_id]
    groups = nameset.get("nameGroups", {})
    gender_weights = nameset.get("genderWeights", {"male": 50, "female": 50})
    format_str = nameset.get("format", "{firstName} {lastName}")

    results = []
    used = set()

    for _ in range(count):
        attempts = 0
        while attempts < 100:
            # Select group
            selected_group = group if group else select_weighted_group(groups)
            if selected_group not in groups:
                print(f"Error: Group '{selected_group}' not found", file=sys.stderr)
                sys.exit(1)

            group_data = groups[selected_group]

            # Select gender
            selected_gender = gender if gender else select_gender(gender_weights)

            # Build categories from group
            first_names = group_data.get("firstNames", [])
            last_names = group_data.get("lastNames", [])

            # Filter by gender
            first_names = filter_by_gender(first_names, selected_gender)

            categories = {
                "firstName": first_names,
                "lastName": last_names
            }

            name = build_name_from_format(format_str, categories)
            if name.lower() not in used or count > len(first_names):
                if return_group:
                    results.append((name, selected_group))
                else:
                    results.append(name)
                used.add(name.lower())
                break
            attempts += 1
        else:
            if return_group:
                results.append((name, selected_group))
            else:
                results.append(name)

    return results


def generate_from_nameset(nameset_id: str, count: int = 1, gender: Optional[str] = None) -> List[str]:
    """Generate names from a custom nameset."""
    if nameset_id not in custom_namesets:
        print(f"Error: Nameset '{nameset_id}' not found", file=sys.stderr)
        print(f"Available namesets: {', '.join(sorted(custom_namesets.keys()))}", file=sys.stderr)
        sys.exit(1)

    nameset = custom_namesets[nameset_id]
    format_str = nameset.get("format", "{firstName} {lastName}")
    categories = nameset.get("nameCategories", {})

    # Legacy support for old format
    if not categories and "firstNames" in nameset:
        categories = {
            "firstName": nameset["firstNames"],
            "lastName": nameset.get("lastNames", [])
        }

    # Filter first names by gender if specified
    if gender and "firstName" in categories:
        categories = categories.copy()
        categories["firstName"] = filter_by_gender(categories["firstName"], gender)

    names = []
    used = set()

    for _ in range(count):
        attempts = 0
        while attempts < 100:
            name = build_name_from_format(format_str, categories)
            if name.lower() not in used or count > len(categories.get("firstName", [])):
                names.append(name)
                used.add(name.lower())
                break
            attempts += 1
        else:
            # Ran out of attempts
            names.append(build_name_from_format(format_str, categories))

    return names


def build_name_from_format(format_str: str, categories: Dict[str, List[Dict]]) -> str:
    """Build a name from format string and name categories."""
    tokens = parse_format(format_str)
    result = []

    for token in tokens:
        if token["type"] == "literal":
            result.append(token["value"])
        elif token["type"] == "placeholder":
            category = token["value"]
            if category in categories and categories[category]:
                entry = select_weighted(categories[category])
                result.append(entry["name"])
        elif token["type"] == "optional":
            # For now, just parse the optional section like normal
            result.append(build_name_from_format(token["value"], categories))

    return "".join(result).strip()


def safe_print(text: str):
    """Print text, replacing unencodable characters."""
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode('ascii', 'replace').decode('ascii'))


def list_namesets():
    """List all available namesets."""
    if not custom_namesets:
        print("No namesets found")
        return

    print("Available namesets:")
    for nameset_id, nameset in sorted(custom_namesets.items()):
        name = nameset.get("name", nameset_id)
        setting = nameset.get("setting", "")
        desc = nameset.get("description", "")
        ns_type = nameset.get("type", "")
        has_groups = "nameGroups" in nameset

        print(f"\n  {nameset_id}")
        safe_print(f"    Name: {name}")
        if setting:
            safe_print(f"    Setting: {setting}")
        if desc:
            safe_print(f"    Description: {desc}")
        if ns_type == "aggregate":
            sources = nameset.get("sources", [])
            labels = [s.get("label", s["nameset"]) for s in sources]
            print(f"    Type: aggregate ({len(sources)} sources)")
            print(f"    Sources: {', '.join(labels)}")
        elif has_groups:
            print(f"    Groups: {', '.join(nameset['nameGroups'].keys())}")


def list_groups(nameset_id: str):
    """List groups/sources in a nameset."""
    if nameset_id not in custom_namesets:
        print(f"Error: Nameset '{nameset_id}' not found", file=sys.stderr)
        sys.exit(1)

    nameset = custom_namesets[nameset_id]

    # Handle aggregate namesets
    if nameset.get("type") == "aggregate":
        sources = nameset.get("sources", [])
        if not sources:
            print(f"Nameset '{nameset_id}' has no sources")
            return

        print(f"Sources in '{nameset_id}' (aggregate):")
        total_weight = sum(s.get("weight", 1) for s in sources)

        for source in sorted(sources, key=lambda s: s.get("weight", 1), reverse=True):
            weight = source.get("weight", 1)
            pct = (weight / total_weight) * 100
            label = source.get("label", source["nameset"])
            source_id = source["nameset"]

            # Check if source exists and get counts
            if source_id in custom_namesets:
                src_ns = custom_namesets[source_id]
                categories = src_ns.get("nameCategories", {})
                first_names = categories.get("firstName", [])
                male_count = len([n for n in first_names if n.get("gender") == "male"])
                female_count = len([n for n in first_names if n.get("gender") == "female"])
                last_count = len(categories.get("lastName", []))
                print(f"\n  {label} ({pct:.1f}%) -> {source_id}")
                print(f"    Names: {male_count}M / {female_count}F / {last_count}L")
            else:
                print(f"\n  {label} ({pct:.1f}%) -> {source_id} [NOT LOADED]")

        return

    # Handle grouped namesets
    groups = nameset.get("nameGroups", {})

    if not groups:
        print(f"Nameset '{nameset_id}' does not use groups")
        return

    print(f"Groups in '{nameset_id}':")
    total_weight = sum(g.get("weight", 1) for g in groups.values())

    for group_id, group in sorted(groups.items()):
        weight = group.get("weight", 1)
        pct = (weight / total_weight) * 100
        male_count = len([n for n in group.get("firstNames", []) if n.get("gender") == "male"])
        female_count = len([n for n in group.get("firstNames", []) if n.get("gender") == "female"])
        last_count = len(group.get("lastNames", []))

        print(f"\n  {group_id} ({pct:.0f}%)")
        print(f"    First names: {male_count}M / {female_count}F")
        print(f"    Last names: {last_count}")


def main():
    # Find repo root (look for .git or assume parent of tools/)
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent

    # Load namesets
    discover_namesets(repo_root)

    # Parse command line
    if len(sys.argv) < 2 or sys.argv[1] in ('--help', '-h'):
        print("Usage: python namegen.py <command> [options]")
        print("\nCommands:")
        print("  full --nameset NAME [--count N] [--group G] [--gender G]")
        print("       Generate name(s) from nameset")
        print("  groups --nameset NAME")
        print("       List groups in a nameset")
        print("  list")
        print("       List available namesets")
        sys.exit(0 if len(sys.argv) > 1 and sys.argv[1] in ('--help', '-h') else 1)

    command = sys.argv[1]

    # Parse options
    count = 1
    nameset = None
    group = None
    gender = None
    show_group = False

    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == "--count" and i + 1 < len(sys.argv):
            count = int(sys.argv[i + 1])
            i += 2
        elif sys.argv[i] == "--nameset" and i + 1 < len(sys.argv):
            nameset = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--group" and i + 1 < len(sys.argv):
            group = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--gender" and i + 1 < len(sys.argv):
            gender = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--show-group":
            show_group = True
            i += 1
        else:
            print(f"Unknown option: {sys.argv[i]}", file=sys.stderr)
            sys.exit(1)

    # Execute command
    if command == "full":
        if not nameset:
            print("Error: --nameset is required", file=sys.stderr)
            print("Use 'python namegen.py list' to see available namesets", file=sys.stderr)
            sys.exit(1)

        # Check nameset type and generate accordingly
        ns = custom_namesets.get(nameset, {})
        if ns.get("type") == "aggregate":
            # Aggregate nameset - select from sources
            results = generate_from_aggregate(nameset, count, group, gender, return_source=show_group)
            if show_group:
                for name, src in results:
                    print(f"{name}|{src}")
            else:
                for name in results:
                    print(name)
        elif "nameGroups" in ns:
            # Grouped nameset - select from groups
            results = generate_from_nameset_with_groups(nameset, count, group, gender, return_group=show_group)
            if show_group:
                for name, grp in results:
                    print(f"{name}|{grp}")
            else:
                for name in results:
                    print(name)
        else:
            # Simple nameset
            names = generate_from_nameset(nameset, count, gender)
            for name in names:
                print(name)

    elif command == "groups":
        if not nameset:
            print("Error: --nameset is required", file=sys.stderr)
            sys.exit(1)
        list_groups(nameset)

    elif command == "list":
        list_namesets()

    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
