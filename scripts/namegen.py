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
    """Parse a format string into tokens.

    Supports per-placeholder gender override: {category:gender}
    Examples: {firstName:male}, {firstName:female}, {firstName}

    Supports random pattern placeholders: {random:pattern}
    Examples: {random:1-99} for range, {random:AAA} for pattern

    Supports optional sections with weight: [ {epithet}:30%]
    The :N% at the END of bracket content specifies inclusion probability.
    Default weight is 100 (always include if content resolves).
    """
    tokens = []
    pattern = r'\{(\w+)(?::([^}]+))?\}|\[([^\]]+)\]|([^\{\[]+)'

    for match in re.finditer(pattern, format_str):
        if match.group(1):  # Placeholder {category} or {category:...}
            category = match.group(1)
            arg = match.group(2)  # Could be gender, range, or pattern

            if category == "random" and arg:
                # Check if arg is a range (e.g., "1-99", "0-255")
                range_match = re.match(r'^(\d+)-(\d+)$', arg)
                if range_match:
                    tokens.append({
                        "type": "random",
                        "range": [int(range_match.group(1)), int(range_match.group(2))]
                    })
                else:
                    # It's a pattern (e.g., "AAA", "000", "XXX")
                    tokens.append({
                        "type": "random",
                        "pattern": arg
                    })
            else:
                tokens.append({
                    "type": "placeholder",
                    "value": category,
                    "gender": arg  # None if no gender specified
                })
        elif match.group(3):  # Optional section [text]
            content = match.group(3)
            weight = 100  # Default: always include

            # Check for weight suffix like :30% at end of content
            weight_match = re.search(r':(\d+)%$', content)
            if weight_match:
                weight = int(weight_match.group(1))
                content = content[:weight_match.start()]

            # Parse the inner content as nested tokens
            inner_tokens = parse_format(content)
            tokens.append({
                "type": "optional",
                "content": inner_tokens,
                "weight": weight
            })
        elif match.group(4):  # Literal text
            tokens.append({"type": "literal", "value": match.group(4)})

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
    """Select gender using weights.

    Supports arbitrary gender strings. The keys in gender_weights can be any
    gender identifier (e.g., "male", "female", "neuter", "construct", "machine").
    """
    total = sum(gender_weights.values())
    rand = random.random() * total

    for gender, weight in gender_weights.items():
        rand -= weight
        if rand <= 0:
            return gender

    return list(gender_weights.keys())[-1]


def filter_by_gender(entries: List[Dict], gender: str, category: Optional[str] = None) -> List[Dict]:
    """Filter name entries by gender. Includes unisex and unspecified names.

    Supports arbitrary gender strings (e.g., "male", "female", "neuter", "construct").
    Matching rules:
    - Exact match: entry gender equals requested gender
    - Unisex: entries with gender="unisex" match any requested gender
    - Untagged: entries with no gender (None) match any requested gender

    If filtering results in empty list, falls back to unfiltered with warning.
    """
    filtered = [e for e in entries if e.get("gender") in {gender, None, "unisex"}]
    if filtered:
        return filtered
    else:
        if category:
            print(f"Warning: {category} has no entries for gender '{gender}', using unfiltered", file=sys.stderr)
        return entries


def generate_pattern(pattern: str) -> str:
    """Generate a random string from a pattern.

    Pattern characters:
    - A: random uppercase letter (A-Z)
    - a: random lowercase letter (a-z)
    - 0: random digit (0-9)
    - X: random hex digit (0-9, A-F)
    - Anything else: literal (preserved as-is)
    """
    result = []
    for char in pattern:
        if char == 'A':
            result.append(random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ'))
        elif char == 'a':
            result.append(random.choice('abcdefghijklmnopqrstuvwxyz'))
        elif char == '0':
            result.append(random.choice('0123456789'))
        elif char == 'X':
            result.append(random.choice('0123456789ABCDEF'))
        else:
            result.append(char)
    return ''.join(result)


def generate_range(min_val: int, max_val: int) -> str:
    """Generate a random integer in range and return as string."""
    return str(random.randint(min_val, max_val))


def generate_single_name(
    nameset: Dict,
    gender: str
) -> str:
    """Generate a single name from a source nameset using its own format and categories."""
    format_str = nameset.get("format", "{firstName} {lastName}")
    categories = nameset.get("nameCategories", {})

    # Legacy support for old format
    if not categories and "firstNames" in nameset:
        categories = {
            "firstName": nameset["firstNames"],
            "lastName": nameset.get("lastNames", [])
        }

    # Pass gender to build_name_from_format for filtering at selection time
    return build_name_from_format(format_str, categories, gender)


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

            # Generate from source using source's own format and categories
            name = generate_single_name(source_nameset, selected_gender)

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

            categories = {
                "firstName": first_names,
                "lastName": last_names
            }

            # Pass gender to build_name_from_format for filtering at selection time
            name = build_name_from_format(format_str, categories, selected_gender)
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

    names = []
    used = set()

    for _ in range(count):
        attempts = 0
        while attempts < 100:
            # Pass gender to build_name_from_format for filtering at selection time
            name = build_name_from_format(format_str, categories, gender)
            if name.lower() not in used or count > len(categories.get("firstName", [])):
                names.append(name)
                used.add(name.lower())
                break
            attempts += 1
        else:
            # Ran out of attempts
            names.append(build_name_from_format(format_str, categories, gender))

    return names


def build_name_from_tokens(
    tokens: List[Dict[str, Any]],
    categories: Dict[str, List[Dict]],
    gender: Optional[str] = None,
    in_optional: bool = False
) -> str:
    """Build a name from parsed tokens and name categories.

    Gender filtering priority:
    1. Per-placeholder override: {firstName:male} forces male filtering
    2. Character gender: passed as parameter, applies to placeholders without override
    3. No filtering: if neither is specified

    When in_optional is True, missing categories are silently skipped.
    """
    result = []

    for token in tokens:
        if token["type"] == "literal":
            result.append(token["value"])
        elif token["type"] == "placeholder":
            category = token["value"]
            if category in categories and categories[category]:
                entries = categories[category]
                # Determine effective gender: per-placeholder override takes precedence
                effective_gender = token.get("gender") or gender
                # Apply gender filtering if gender specified and category has gendered entries
                if effective_gender and any(e.get("gender") for e in entries):
                    entries = filter_by_gender(entries, effective_gender, category)
                entry = select_weighted(entries)
                result.append(entry["name"])
            elif not in_optional:
                # Warn only for top-level missing categories, not optional content
                print(f"Warning: Format references undefined or empty category '{category}'", file=sys.stderr)
        elif token["type"] == "random":
            if "range" in token:
                result.append(generate_range(token["range"][0], token["range"][1]))
            elif "pattern" in token:
                result.append(generate_pattern(token["pattern"]))
        elif token["type"] == "optional":
            weight = token.get("weight", 100)
            # Roll against weight percentage
            if random.random() * 100 < weight:
                inner_result = build_name_from_tokens(token["content"], categories, gender, in_optional=True)
                if inner_result.strip():  # Only include if non-empty
                    result.append(inner_result)

    return "".join(result)


def build_name_from_format(
    format_str: str,
    categories: Dict[str, List[Dict]],
    gender: Optional[str] = None
) -> str:
    """Build a name from format string and name categories.

    Gender filtering priority:
    1. Per-placeholder override: {firstName:male} forces male filtering
    2. Character gender: passed as parameter, applies to placeholders without override
    3. No filtering: if neither is specified
    """
    tokens = parse_format(format_str)
    result = build_name_from_tokens(tokens, categories, gender)
    # Clean up whitespace: collapse multiple spaces and strip
    return " ".join(result.split())


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
                last_count = len(categories.get("lastName", []))
                # Count names by gender (supports arbitrary genders)
                gender_counts = {}
                for n in first_names:
                    g = n.get("gender") or "untagged"
                    gender_counts[g] = gender_counts.get(g, 0) + 1
                print(f"\n  {label} ({pct:.1f}%) -> {source_id}")
                if gender_counts:
                    counts_str = " / ".join(f"{c}{g[0].upper()}" for g, c in sorted(gender_counts.items()))
                    print(f"    Names: {counts_str} / {last_count}L")
                else:
                    print(f"    Names: {len(first_names)} first / {last_count} last")
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
        first_names = group.get("firstNames", [])
        last_count = len(group.get("lastNames", []))
        # Count names by gender (supports arbitrary genders)
        gender_counts = {}
        for n in first_names:
            g = n.get("gender") or "untagged"
            gender_counts[g] = gender_counts.get(g, 0) + 1

        print(f"\n  {group_id} ({pct:.0f}%)")
        if gender_counts:
            counts_str = " / ".join(f"{c}{g[0].upper()}" for g, c in sorted(gender_counts.items()))
            print(f"    First names: {counts_str}")
        else:
            print(f"    First names: {len(first_names)}")
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

    # Validate count
    if count < 1:
        print("Error: --count must be at least 1", file=sys.stderr)
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
