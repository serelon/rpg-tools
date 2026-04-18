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
        multi_collection_key="namesets",
        on_warning=on_warning
    )

    if not custom_namesets:
        print("Warning: No namesets found", file=sys.stderr)
    else:
        print(f"Loaded {len(custom_namesets)} namesets", file=sys.stderr)


def resolve_nameset_ref(ref: str, current_namespace: str = "") -> Optional[str]:
    """Resolve a nameset reference to a fully-qualified key.

    Rules:
    - If ref contains ':', it's already qualified - return if exists, else None.
    - If ref is bare, try current_namespace first, then root ('').
    """
    if ':' in ref:
        return ref if ref in custom_namesets else None
    candidate = f"{current_namespace}:{ref}"
    if candidate in custom_namesets:
        return candidate
    candidate = f":{ref}"
    if candidate in custom_namesets:
        return candidate
    return None


def get_format_template(nameset: Dict, format_name: str = "default") -> str:
    """Resolve a nameset's named format to a template string.

    Priority:
    1. nameset['formats'][format_name] (object with 'template' or string shorthand)
    2. nameset['formats']['default']
    3. nameset['format'] (legacy single string)
    4. Built-in default '{firstName} {lastName}'
    """
    formats = nameset.get("formats")
    if formats:
        entry = formats.get(format_name)
        if entry is None and format_name != "default":
            print(f"Warning: format '{format_name}' not defined, using 'default'", file=sys.stderr)
            entry = formats.get("default")
        if entry is None:
            return "{firstName} {lastName}"
        if isinstance(entry, str):
            return entry
        if isinstance(entry, dict):
            return entry.get("template", "{firstName} {lastName}")
    # Legacy fallback
    return nameset.get("format", "{firstName} {lastName}")


def parse_format(format_str: str) -> List[Dict[str, Any]]:
    """Parse a format string into tokens.

    Supports per-placeholder gender override: {category:gender}
    Examples: {firstName:male}, {firstName:female}, {firstName}

    Supports random pattern placeholders: {random:pattern}
    Examples: {random:1-99} for range, {random:AAA} for pattern

    Supports optional sections with weight: [ {epithet}:30%]
    The :N% at the END of bracket content specifies inclusion probability.
    Default weight is 100 (always include if content resolves).
    Nested optional sections are supported: [{title}[ {epithet}]]
    """
    tokens = []
    i = 0

    while i < len(format_str):
        char = format_str[i]

        if char == '{':
            # Find matching closing brace
            end = format_str.find('}', i)
            if end == -1:
                # No closing brace, treat as literal
                tokens.append({"type": "literal", "value": char})
                i += 1
                continue

            content = format_str[i+1:end]

            # Check for category:arg pattern
            if ':' in content:
                category, arg = content.split(':', 1)
            else:
                category, arg = content, None

            if category == "random":
                # Handle {random}, {random:}, or {random:pattern}
                effective_arg = arg or ""
                # Check if arg is a range (e.g., "1-99", "0-255")
                range_match = re.match(r'^(\d+)-(\d+)$', effective_arg)
                if range_match:
                    min_val = int(range_match.group(1))
                    max_val = int(range_match.group(2))
                    # Swap if reversed to prevent randint crash
                    if min_val > max_val:
                        min_val, max_val = max_val, min_val
                    tokens.append({
                        "type": "random",
                        "range": [min_val, max_val]
                    })
                else:
                    # It's a pattern (e.g., "AAA", "000", "XXX", or empty)
                    tokens.append({
                        "type": "random",
                        "pattern": effective_arg
                    })
            else:
                tokens.append({
                    "type": "placeholder",
                    "value": category,
                    "gender": arg  # None if no gender specified
                })

            i = end + 1

        elif char == '[':
            # Find matching closing bracket, accounting for nesting
            depth = 1
            start = i + 1
            j = start
            while j < len(format_str) and depth > 0:
                if format_str[j] == '[':
                    depth += 1
                elif format_str[j] == ']':
                    depth -= 1
                j += 1

            if depth != 0:
                # Unmatched bracket, treat as literal
                tokens.append({"type": "literal", "value": char})
                i += 1
                continue

            content = format_str[start:j-1]
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

            i = j

        else:
            # Literal text - collect until next special character
            end = i
            while end < len(format_str) and format_str[end] not in '{[':
                end += 1
            tokens.append({"type": "literal", "value": format_str[i:end]})
            i = end

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


def filter_by_tags(entries: List[Dict], tag_filter: Optional[List[str]], category: Optional[str] = None) -> List[Dict]:
    """Keep only entries whose 'tags' include ALL listed filter tags. Untagged entries don't match.

    If filter is empty/None, returns entries unchanged. If filter excludes everything,
    warns and returns entries unfiltered.
    """
    if not tag_filter:
        return entries
    required = set(tag_filter)
    filtered = [e for e in entries if required.issubset(set(e.get("tags", [])))]
    if filtered:
        return filtered
    if category:
        print(f"Warning: {category} has no entries matching tags {tag_filter}, using unfiltered", file=sys.stderr)
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
    char_map = {
        'A': 'ABCDEFGHIJKLMNOPQRSTUVWXYZ',
        'a': 'abcdefghijklmnopqrstuvwxyz',
        '0': '0123456789',
        'X': '0123456789ABCDEF',
    }
    result = []
    for char in pattern:
        char_set = char_map.get(char)
        if char_set:
            result.append(random.choice(char_set))
        else:
            result.append(char)
    return ''.join(result)


def generate_range(min_val: int, max_val: int) -> str:
    """Generate a random integer in range and return as string."""
    return str(random.randint(min_val, max_val))


def generate_single_name(
    nameset: Dict,
    gender: str,
    tag_filter: Optional[List[str]] = None,
    format_name: str = "default"
) -> str:
    """Generate a single name from a source nameset using its own format and categories."""
    format_str = get_format_template(nameset, format_name)
    categories = nameset.get("nameCategories", {})

    # Legacy support for old format
    if not categories and "firstNames" in nameset:
        categories = {
            "firstName": nameset["firstNames"],
            "lastName": nameset.get("lastNames", [])
        }

    # Pass gender to build_name_from_format for filtering at selection time
    return build_name_from_format(format_str, categories, gender, tag_filter=tag_filter)


def generate_from_aggregate(
    nameset_id: str,
    count: int = 1,
    source_label: Optional[str] = None,
    gender: Optional[str] = None,
    return_source: bool = False,
    tag_filter: Optional[List[str]] = None,
    format_name: str = "default"
) -> List:
    """Generate names from an aggregate nameset by selecting source, then generating.

    Accepts both bare IDs (resolved via root namespace fallback) and
    fully-qualified ``namespace:id`` keys. Source nameset references inside
    the aggregate are resolved relative to the aggregate's own namespace,
    falling back to root.
    """
    resolved_id = resolve_nameset_ref(nameset_id)
    if resolved_id is None:
        print(f"Error: Nameset '{nameset_id}' not found", file=sys.stderr)
        sys.exit(1)
    nameset = custom_namesets[resolved_id]
    parent_namespace = resolved_id.split(":", 1)[0]
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

            source_nameset_ref = selected["nameset"]
            resolved_source = resolve_nameset_ref(source_nameset_ref, current_namespace=parent_namespace)
            if resolved_source is None:
                print(f"Error: Source nameset '{source_nameset_ref}' not found", file=sys.stderr)
                sys.exit(1)

            source_nameset = custom_namesets[resolved_source]
            label = selected.get("label", source_nameset_ref)

            # Select gender
            selected_gender = gender if gender else select_gender(gender_weights)

            # Generate from source using source's own format and categories
            name = generate_single_name(source_nameset, selected_gender, tag_filter=tag_filter, format_name=format_name)

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
    return_group: bool = False,
    tag_filter: Optional[List[str]] = None,
    format_name: str = "default"
) -> List:
    """Generate names from a nameset that uses nameGroups.

    If return_group is True, returns list of (name, group) tuples.
    Otherwise returns list of names.

    Accepts both bare IDs (resolved via root namespace fallback) and
    fully-qualified ``namespace:id`` keys.
    """
    resolved = resolve_nameset_ref(nameset_id)
    if resolved is None:
        print(f"Error: Nameset '{nameset_id}' not found", file=sys.stderr)
        sys.exit(1)
    nameset = custom_namesets[resolved]
    groups = nameset.get("nameGroups", {})
    gender_weights = nameset.get("genderWeights", {"male": 50, "female": 50})
    format_str = get_format_template(nameset, format_name)

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
            name = build_name_from_format(format_str, categories, selected_gender, tag_filter=tag_filter)
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


def generate_from_nameset(nameset_id: str, count: int = 1, gender: Optional[str] = None, tag_filter: Optional[List[str]] = None, format_name: str = "default") -> List[str]:
    """Generate names from a custom nameset.

    Accepts both bare IDs (resolved via root namespace fallback) and
    fully-qualified ``namespace:id`` keys.
    """
    resolved = resolve_nameset_ref(nameset_id)
    if resolved is None:
        print(f"Error: Nameset '{nameset_id}' not found", file=sys.stderr)
        print(f"Available namesets: {', '.join(sorted(custom_namesets.keys()))}", file=sys.stderr)
        sys.exit(1)

    nameset = custom_namesets[resolved]
    format_str = get_format_template(nameset, format_name)
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
            name = build_name_from_format(format_str, categories, gender, tag_filter=tag_filter)
            if name.lower() not in used or count > len(categories.get("firstName", [])):
                names.append(name)
                used.add(name.lower())
                break
            attempts += 1
        else:
            # Ran out of attempts
            names.append(build_name_from_format(format_str, categories, gender, tag_filter=tag_filter))

    return names


def build_name_from_tokens(
    tokens: List[Dict[str, Any]],
    categories: Dict[str, List[Dict]],
    gender: Optional[str] = None,
    in_optional: bool = False,
    tag_filter: Optional[List[str]] = None
) -> str:
    """Build a name from parsed tokens and name categories.

    Gender filtering priority:
    1. Per-placeholder override: {firstName:male} forces male filtering
    2. Character gender: passed as parameter, applies to placeholders without override
    3. No filtering: if neither is specified

    Tag filtering: when tag_filter is provided, only entries whose 'tags' include
    ALL listed filter tags are eligible. If filtering excludes everything, falls
    back to unfiltered with a warning.

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
                entries = filter_by_tags(entries, tag_filter, category)
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
                inner_result = build_name_from_tokens(token["content"], categories, gender, in_optional=True, tag_filter=tag_filter)
                if inner_result.strip():  # Only include if non-empty
                    result.append(inner_result)

    return "".join(result)


def build_name_from_format(
    format_str: str,
    categories: Dict[str, List[Dict]],
    gender: Optional[str] = None,
    tag_filter: Optional[List[str]] = None
) -> str:
    """Build a name from format string and name categories.

    Gender filtering priority:
    1. Per-placeholder override: {firstName:male} forces male filtering
    2. Character gender: passed as parameter, applies to placeholders without override
    3. No filtering: if neither is specified

    Tag filtering: when tag_filter is provided, only entries whose 'tags' include
    ALL listed filter tags are eligible.
    """
    tokens = parse_format(format_str)
    result = build_name_from_tokens(tokens, categories, gender, tag_filter=tag_filter)
    # Clean up whitespace: collapse multiple spaces and strip
    return " ".join(result.split())


def safe_print(text: str):
    """Print text, replacing unencodable characters."""
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode('ascii', 'replace').decode('ascii'))


def list_namesets(namespace_filter: Optional[str] = None, show_hidden: bool = False):
    """List all available namesets, optionally filtered by namespace prefix.

    Hidden namesets (with ``"hidden": true``) are excluded by default.
    Pass ``show_hidden=True`` to include them.
    """
    if not custom_namesets:
        print("No namesets found")
        return

    items = sorted(custom_namesets.items())
    if namespace_filter is not None:
        items = [(k, v) for k, v in items if k.startswith(f"{namespace_filter}:")]
    if not show_hidden:
        items = [(k, v) for k, v in items if not v.get("hidden", False)]

    print("Available namesets:")
    for nameset_id, nameset in items:
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
    """List groups/sources in a nameset.

    Accepts both bare IDs (resolved via root namespace fallback) and
    fully-qualified ``namespace:id`` keys.
    """
    resolved = resolve_nameset_ref(nameset_id)
    if resolved is None:
        print(f"Error: Nameset '{nameset_id}' not found", file=sys.stderr)
        sys.exit(1)

    nameset = custom_namesets[resolved]
    parent_namespace = resolved.split(":", 1)[0]

    # Handle aggregate namesets
    if nameset.get("type") == "aggregate":
        sources = nameset.get("sources", [])
        if not sources:
            print(f"Nameset '{resolved}' has no sources")
            return

        print(f"Sources in '{resolved}' (aggregate):")
        total_weight = sum(s.get("weight", 1) for s in sources)

        for source in sorted(sources, key=lambda s: s.get("weight", 1), reverse=True):
            weight = source.get("weight", 1)
            pct = (weight / total_weight) * 100
            label = source.get("label", source["nameset"])
            source_ref = source["nameset"]
            source_resolved = resolve_nameset_ref(source_ref, current_namespace=parent_namespace)

            # Check if source exists and get counts
            if source_resolved is not None:
                src_ns = custom_namesets[source_resolved]
                categories = src_ns.get("nameCategories", {})
                first_names = categories.get("firstName", [])
                last_count = len(categories.get("lastName", []))
                # Count names by gender (supports arbitrary genders)
                gender_counts = {}
                for n in first_names:
                    g = n.get("gender") or "untagged"
                    gender_counts[g] = gender_counts.get(g, 0) + 1
                print(f"\n  {label} ({pct:.1f}%) -> {source_resolved}")
                if gender_counts:
                    counts_str = " / ".join(f"{c}{g[0].upper()}" for g, c in sorted(gender_counts.items()))
                    print(f"    Names: {counts_str} / {last_count}L")
                else:
                    print(f"    Names: {len(first_names)} first / {last_count} last")
            else:
                print(f"\n  {label} ({pct:.1f}%) -> {source_ref} [NOT LOADED]")

        return

    # Handle grouped namesets
    groups = nameset.get("nameGroups", {})

    if not groups:
        print(f"Nameset '{resolved}' does not use groups")
        return

    print(f"Groups in '{resolved}':")
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
        print("  full --nameset NAME [--count N] [--group G] [--gender G] [--filter TAG ...] [--format NAME]")
        print("       Generate name(s) from nameset")
        print("       --filter TAG    Restrict generation to entries with TAG.")
        print("                       Repeat for AND semantics (entries must have ALL tags).")
        print("       --format NAME   Use a named format variant from the nameset's 'formats' map.")
        print("                       Defaults to 'default'. Falls back to legacy 'format' field.")
        print("  groups --nameset NAME")
        print("       List groups in a nameset")
        print("  list [--namespace NS] [--all]")
        print("       List available namesets (optionally filtered by namespace)")
        print("       --all           Include hidden namesets (excluded by default)")
        sys.exit(0 if len(sys.argv) > 1 and sys.argv[1] in ('--help', '-h') else 1)

    command = sys.argv[1]

    # Parse options
    count = 1
    nameset = None
    group = None
    gender = None
    show_group = False
    namespace_filter = None
    tag_filter: List[str] = []
    format_name = "default"
    show_hidden = False

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
        elif sys.argv[i] == "--namespace" and i + 1 < len(sys.argv):
            namespace_filter = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--filter" and i + 1 < len(sys.argv):
            tag_filter.append(sys.argv[i + 1])
            i += 2
        elif sys.argv[i] == "--format" and i + 1 < len(sys.argv):
            format_name = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--show-group":
            show_group = True
            i += 1
        elif sys.argv[i] == "--all":
            show_hidden = True
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

        # Resolve bare or qualified nameset reference
        resolved_nameset = resolve_nameset_ref(nameset)
        if resolved_nameset is None:
            print(f"Error: Nameset '{nameset}' not found", file=sys.stderr)
            print(f"Available namesets: {', '.join(sorted(custom_namesets.keys()))}", file=sys.stderr)
            sys.exit(1)
        nameset = resolved_nameset

        # Normalize empty tag_filter list to None for downstream calls
        effective_tag_filter = tag_filter if tag_filter else None

        # Check nameset type and generate accordingly
        ns = custom_namesets.get(nameset, {})
        if ns.get("type") == "aggregate":
            # Aggregate nameset - select from sources
            results = generate_from_aggregate(nameset, count, group, gender, return_source=show_group, tag_filter=effective_tag_filter, format_name=format_name)
            if show_group:
                for name, src in results:
                    print(f"{name}|{src}")
            else:
                for name in results:
                    print(name)
        elif "nameGroups" in ns:
            # Grouped nameset - select from groups
            results = generate_from_nameset_with_groups(nameset, count, group, gender, return_group=show_group, tag_filter=effective_tag_filter, format_name=format_name)
            if show_group:
                for name, grp in results:
                    print(f"{name}|{grp}")
            else:
                for name in results:
                    print(name)
        else:
            # Simple nameset
            names = generate_from_nameset(nameset, count, gender, tag_filter=effective_tag_filter, format_name=format_name)
            for name in names:
                print(name)

    elif command == "groups":
        if not nameset:
            print("Error: --nameset is required", file=sys.stderr)
            sys.exit(1)
        list_groups(nameset)

    elif command == "list":
        list_namesets(namespace_filter=namespace_filter, show_hidden=show_hidden)

    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
