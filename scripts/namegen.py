#!/usr/bin/env python3
"""Name generation tool for solo RPG games. Uses namesets only."""

import difflib
import random
import re
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

from lib import discover_data


# Custom namesets storage
custom_namesets = {}


def _explain(msg: str, enabled: bool) -> None:
    """Print an [explain] trace line to stderr when enabled. No-op otherwise."""
    if enabled:
        print(f"[explain] {msg}", file=sys.stderr)


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

    # Resolve extends inheritance after all namesets are loaded
    resolve_all_extends()


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


def resolve_extends_chain(qualified_id: str, seen: Optional[set] = None) -> Dict:
    """Walk the extends chain and produce a fully-merged nameset.

    Modifies custom_namesets[qualified_id] in place. Idempotent.
    Raises ValueError on circular extends or missing parent.
    """
    if seen is None:
        seen = set()
    if qualified_id in seen:
        raise ValueError(f"Circular extends detected: {qualified_id} in chain {seen}")
    if qualified_id not in custom_namesets:
        raise ValueError(f"Cannot resolve extends: {qualified_id} not found")

    nameset = custom_namesets[qualified_id]
    if "_extends_resolved" in nameset:
        return nameset
    if "extends" not in nameset:
        nameset["_extends_resolved"] = True
        return nameset

    parent_ref = nameset["extends"]
    namespace = qualified_id.split(":", 1)[0]
    parent_qualified = resolve_nameset_ref(parent_ref, current_namespace=namespace)
    if parent_qualified is None:
        raise ValueError(f"Parent nameset '{parent_ref}' not found for {qualified_id}")

    seen.add(qualified_id)
    parent = resolve_extends_chain(parent_qualified, seen)
    seen.remove(qualified_id)

    # Build merged: start from parent, override with child's fields, merge categories specially
    merged = dict(parent)
    merged.pop("_extends_resolved", None)

    for key, value in nameset.items():
        if key == "extends":
            continue
        if key == "nameCategories":
            merged_cats = dict(parent.get("nameCategories", {}))
            for cat, child_def in value.items():
                if isinstance(child_def, dict) and ("add" in child_def or "remove" in child_def):
                    base_entries = list(merged_cats.get(cat, []))
                    remove_set = set(child_def.get("remove", []))
                    base_entries = [e for e in base_entries if e["name"] not in remove_set]
                    base_entries.extend(child_def.get("add", []))
                    merged_cats[cat] = base_entries
                else:
                    # Full replacement when child specifies a list directly
                    merged_cats[cat] = child_def
            merged["nameCategories"] = merged_cats
        else:
            merged[key] = value

    merged["_extends_resolved"] = True
    custom_namesets[qualified_id] = merged
    return merged


def resolve_all_extends():
    """Resolve all extends chains. Call after discovery."""
    for qid in list(custom_namesets.keys()):
        try:
            resolve_extends_chain(qid)
        except ValueError as e:
            print(f"Error resolving extends for {qid}: {e}", file=sys.stderr)


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
            # Find matching closing brace, accounting for nesting
            depth = 1
            start = i + 1
            j = start
            while j < len(format_str) and depth > 0:
                if format_str[j] == '{':
                    depth += 1
                elif format_str[j] == '}':
                    depth -= 1
                j += 1

            if depth != 0:
                # Unmatched, treat as literal
                tokens.append({"type": "literal", "value": char})
                i += 1
                continue

            # j is one past the matching closing brace
            content = format_str[start:j-1]

            # Check for chain quantifier *N-M after the }
            chain_match = re.match(r'\*(\d+)-(\d+)', format_str[j:])
            if chain_match:
                # Chain group - parse inner content recursively (may contain placeholders)
                inner_tokens = parse_format(content)
                tokens.append({
                    "type": "repeat",
                    "min": int(chain_match.group(1)),
                    "max": int(chain_match.group(2)),
                    "content": inner_tokens
                })
                i = j + chain_match.end()
                continue

            # Not a chain - treat content as a single placeholder (or random)
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

            i = j

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


def _render_tokens(
    tokens: List[Dict[str, Any]],
    resolve_placeholder,
    in_optional: bool = False,
) -> Tuple[str, bool]:
    """Render parsed format tokens using a caller-supplied placeholder resolver.

    ``resolve_placeholder(token, in_optional)`` returns the text for a
    placeholder token, or ``None`` when the category can't be satisfied.

    Returns ``(text, ok)``. ``ok`` is False when any placeholder *at this
    level* failed to resolve. An optional section is included only when its
    own placeholders all resolved — so ``[ af {station}]`` drops the whole
    section (particle included) when there is no station, instead of leaking
    a dangling literal. A failed nested optional never fails its parent.
    """
    result = []
    ok = True

    for token in tokens:
        ttype = token["type"]
        if ttype == "literal":
            result.append(token["value"])
        elif ttype == "placeholder":
            text = resolve_placeholder(token, in_optional)
            if text is None:
                ok = False
            else:
                result.append(text)
        elif ttype == "random":
            if "range" in token:
                result.append(generate_range(token["range"][0], token["range"][1]))
            elif "pattern" in token:
                result.append(generate_pattern(token["pattern"]))
        elif ttype == "optional":
            weight = token.get("weight", 100)
            if random.random() * 100 < weight:
                inner_text, inner_ok = _render_tokens(token["content"], resolve_placeholder, in_optional=True)
                if inner_ok and inner_text.strip():
                    result.append(inner_text)
        elif ttype == "repeat":
            repeats = random.randint(token["min"], token["max"])
            for _ in range(repeats):
                inner_text, _inner_ok = _render_tokens(token["content"], resolve_placeholder, in_optional=True)
                result.append(inner_text)

    return "".join(result), ok


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


def get_name_categories(nameset: dict) -> dict:
    """Return a nameset's nameCategories, normalizing legacy v1 namesets.

    v1 namesets carry top-level firstNames/lastNames arrays instead of a
    nameCategories map. The leaf and grouped generators convert these inline;
    this helper exposes the same conversion to the slot-aware aggregate path,
    so a `forced` slot can pull e.g. {lastName} from a v1 people nameset.
    """
    categories = nameset.get("nameCategories")
    if categories:
        return categories
    if "firstNames" in nameset or "lastNames" in nameset:
        return {
            "firstName": nameset.get("firstNames", []),
            "lastName": nameset.get("lastNames", []),
        }
    return {}


def build_aggregate_name_with_slots(
    aggregate_id: str,
    gender: Optional[str],
    format_name: str = "default",
    tag_filter: Optional[List[str]] = None,
    source_label: Optional[str] = None,
    gender_weights: Optional[Dict[str, int]] = None,
    explain: bool = False
) -> str:
    """Generate a name from an aggregate using per-slot source policies.

    Slot policies:
    - inherit (default): use the anchor source for this slot
    - independent: roll a fresh source for this slot
    - mix with rate N (0..1): N probability of independent, else inherit
    - forced with nameset "...": always pull from the named source
    - pool with sources [...] and rate N (default 1.0): N probability of
      drawing from the slot's own weighted source list, else inherit.
      Pool sources are never anchor-eligible.

    If `gender` is None and `gender_weights` is provided, the gender is
    selected here (after anchor resolution) so the anchor's
    `override.genderWeights` can bias the choice.

    Optional sections work as in simple namesets: ``[ af {station}]`` is
    dropped whole when the resolved source has no ``station`` category.
    """
    aggregate = custom_namesets[aggregate_id]
    aggregate_namespace = aggregate_id.split(":", 1)[0]
    sources = aggregate.get("sources", [])
    slots = aggregate.get("slots", {})

    # Pick anchor source (used for inherit-policy slots)
    if source_label:
        anchor_source_def = next((s for s in sources if s.get("label") == source_label), None)
        if not anchor_source_def:
            print(f"Error: Source label '{source_label}' not found in aggregate '{aggregate_id}'", file=sys.stderr)
            sys.exit(1)
    else:
        anchor_source_def = select_weighted_source(sources)

    if explain:
        anchor_label = anchor_source_def.get("label", anchor_source_def.get("nameset", "?"))
        anchor_weight = anchor_source_def.get("weight", 1)
        total_weight = sum(s.get("weight", 1) for s in sources)
        _explain(f"Anchor source pick: {anchor_label} (weight {anchor_weight}/{total_weight})", explain)

    template = get_format_template(aggregate, format_name)
    tokens = parse_format(template)

    def resolve_source(source_def):
        """Resolve a source definition to (nameset_dict, override_dict).

        Returns (None, {}) if source_def is missing or unresolvable.
        """
        if not source_def:
            return None, {}
        ref = source_def.get("nameset")
        if not ref:
            return None, {}
        qualified = resolve_nameset_ref(ref, current_namespace=aggregate_namespace)
        nameset = custom_namesets.get(qualified) if qualified else None
        return nameset, source_def.get("override", {})

    anchor_nameset, anchor_override = resolve_source(anchor_source_def)

    # Anchor's genderWeights override biases the (single) gender choice for this name.
    if gender is None and gender_weights is not None:
        effective_gw = anchor_override.get("genderWeights", gender_weights)
        gender = select_gender(effective_gw)

    def resolve_slot(token, _in_optional):
        """Resolve one placeholder via its slot policy; None if unsatisfiable."""
        category = token["value"]
        slot_config = slots.get(category, {"policy": "inherit"})
        policy = slot_config.get("policy", "inherit")

        # Determine source nameset for this slot, plus its override
        chosen_nameset = None
        chosen_override = {}
        chosen_source_label = None
        if policy == "forced":
            forced_ref = slot_config.get("nameset")
            # Look up the matching source_def in the aggregate's sources (for override)
            forced_def = next(
                (s for s in sources if s.get("nameset") == forced_ref),
                None,
            )
            if forced_def is not None:
                chosen_nameset, chosen_override = resolve_source(forced_def)
                chosen_source_label = forced_def.get("label", forced_ref)
            else:
                # Forced ref not in sources list - resolve directly without override
                if forced_ref:
                    qualified = resolve_nameset_ref(forced_ref, current_namespace=aggregate_namespace)
                    chosen_nameset = custom_namesets.get(qualified) if qualified else None
                    chosen_source_label = forced_ref
            if chosen_nameset is None:
                print(
                    f"Warning: forced slot source '{forced_ref}' not found for slot '{category}', falling back to anchor",
                    file=sys.stderr,
                )
                chosen_nameset = anchor_nameset
                chosen_override = anchor_override
                chosen_source_label = anchor_source_def.get("label", "?") + " (fallback)"
        elif policy == "independent":
            rolled_def = select_weighted_source(sources)
            chosen_nameset, chosen_override = resolve_source(rolled_def)
            chosen_source_label = rolled_def.get("label", rolled_def.get("nameset", "?"))
            if chosen_nameset is None:
                chosen_nameset = anchor_nameset
                chosen_override = anchor_override
                chosen_source_label = anchor_source_def.get("label", "?") + " (fallback)"
        elif policy == "mix":
            rate = slot_config.get("rate", 0.5)
            if random.random() < rate:
                rolled_def = select_weighted_source(sources)
                chosen_nameset, chosen_override = resolve_source(rolled_def)
                chosen_source_label = rolled_def.get("label", rolled_def.get("nameset", "?"))
                if chosen_nameset is None:
                    chosen_nameset = anchor_nameset
                    chosen_override = anchor_override
                    chosen_source_label = anchor_source_def.get("label", "?") + " (fallback)"
            else:
                chosen_nameset = anchor_nameset
                chosen_override = anchor_override
                chosen_source_label = anchor_source_def.get("label", "?") + " (inherit)"
        elif policy == "pool":
            # Slot-private source list: with probability `rate` draw from the
            # pool (weighted, never anchor-eligible), else inherit the anchor.
            # Lets a lastName-only leaf feed a slot without ever being picked
            # as anchor, and lets one slot mix at a different rate than another.
            rate = slot_config.get("rate", 1.0)
            pool = slot_config.get("sources", [])
            if pool and random.random() < rate:
                rolled_def = select_weighted_source(pool)
                chosen_nameset, chosen_override = resolve_source(rolled_def)
                chosen_source_label = "pool:" + rolled_def.get("label", rolled_def.get("nameset", "?"))
                if chosen_nameset is None:
                    chosen_nameset = anchor_nameset
                    chosen_override = anchor_override
                    chosen_source_label = anchor_source_def.get("label", "?") + " (fallback)"
            else:
                chosen_nameset = anchor_nameset
                chosen_override = anchor_override
                chosen_source_label = anchor_source_def.get("label", "?") + " (inherit)"
        else:  # inherit (default)
            chosen_nameset = anchor_nameset
            chosen_override = anchor_override
            chosen_source_label = anchor_source_def.get("label", "?")

        _explain(f"Slot {category}: {policy} -> {chosen_source_label}", explain)

        # Pick from this source's category
        if chosen_nameset is None:
            return None
        source_categories = get_name_categories(chosen_nameset)
        entries = source_categories.get(category, [])
        if not entries and anchor_nameset is not None and anchor_nameset is not chosen_nameset:
            # Fall back to anchor for this category
            source_categories = get_name_categories(anchor_nameset)
            entries = source_categories.get(category, [])
        if not entries:
            return None

        effective_gender = token.get("gender") or gender
        if effective_gender and any(e.get("gender") for e in entries):
            entries = filter_by_gender(entries, effective_gender, category)
        # Per-source filter override ANDs with user-provided tag_filter.
        override_filter = chosen_override.get("filter", [])
        effective_tag_filter = list(tag_filter or []) + list(override_filter)
        if effective_tag_filter:
            entries = filter_by_tags(entries, effective_tag_filter, category)
        if not entries:
            return None
        return select_weighted(entries)["name"]

    text, _ok = _render_tokens(tokens, resolve_slot)
    return " ".join(text.split())


def generate_from_aggregate(
    nameset_id: str,
    count: int = 1,
    source_label: Optional[str] = None,
    gender: Optional[str] = None,
    return_source: bool = False,
    tag_filter: Optional[List[str]] = None,
    format_name: str = "default",
    explain: bool = False
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

    _explain(f"Nameset: {resolved_id} (aggregate, {len(sources)} sources)", explain)
    _explain(f"Format: {format_name}", explain)

    results = []
    used = set()

    for _ in range(count):
        attempts = 0
        name = ""
        label = "(unresolved)"
        while attempts < 100:
            # Slot-aware path: aggregates declaring a 'slots' map use per-slot
            # source resolution rather than picking one source for the whole name.
            if "slots" in nameset:
                # Pass gender_weights through so the helper can apply the
                # anchor's genderWeights override after picking the anchor.
                name = build_aggregate_name_with_slots(
                    resolved_id,
                    gender,
                    format_name=format_name,
                    tag_filter=tag_filter,
                    source_label=source_label,
                    gender_weights=gender_weights,
                    explain=explain,
                )
                label = source_label or "(slot-aware)"
                if name and name.lower() not in used:
                    if return_source:
                        results.append((name, label))
                    else:
                        results.append(name)
                    used.add(name.lower())
                    break
                attempts += 1
                continue

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
                print(
                    f"Warning: Source nameset '{source_nameset_ref}' not found in aggregate '{resolved_id}', skipping",
                    file=sys.stderr,
                )
                attempts += 1
                continue

            source_nameset = custom_namesets[resolved_source]
            label = selected.get("label", source_nameset_ref)

            if explain:
                total_w = sum(s.get("weight", 1) for s in sources)
                this_w = selected.get("weight", 1)
                _explain(f"Source pick: {label} (weight {this_w}/{total_w}) -> {resolved_source}", explain)

            # Per-source overrides: genderWeights biases gender selection
            # for this source; filter ANDs with any user-provided tag_filter.
            override = selected.get("override", {})
            if "genderWeights" in override:
                effective_gender_weights = override["genderWeights"]
            else:
                effective_gender_weights = gender_weights

            if "filter" in override:
                effective_tag_filter = list(tag_filter or []) + list(override["filter"])
            else:
                effective_tag_filter = tag_filter

            # Per-source format override forces a specific named format on this
            # source (e.g. assigning different name-shapes to repeated sources of
            # the same leaf). Falls back to the format requested of the aggregate.
            effective_format = override.get("format", format_name)

            # Select gender (using effective weights)
            selected_gender = gender if gender else select_gender(effective_gender_weights)

            # Dispatch by source type: recurse for nested aggregates,
            # use grouped path for grouped sources, else leaf generator.
            if source_nameset.get("type") == "aggregate":
                sub = generate_from_aggregate(
                    resolved_source,
                    count=1,
                    gender=selected_gender,
                    format_name=effective_format,
                    tag_filter=effective_tag_filter,
                    explain=explain,
                )
                name = sub[0] if sub else ""
            elif "nameGroups" in source_nameset:
                sub = generate_from_nameset_with_groups(
                    resolved_source,
                    count=1,
                    gender=selected_gender,
                    format_name=effective_format,
                    tag_filter=effective_tag_filter,
                    explain=explain,
                )
                name = sub[0] if sub else ""
            else:
                name = generate_single_name(
                    source_nameset, selected_gender, tag_filter=effective_tag_filter, format_name=effective_format
                )

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
    format_name: str = "default",
    explain: bool = False
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

    _explain(f"Nameset: {resolved} (grouped)", explain)
    _explain(f"Format: {format_name} -> \"{format_str}\"", explain)

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

            if explain:
                total_w = sum(g.get("weight", 1) for g in groups.values())
                this_w = groups[selected_group].get("weight", 1)
                _explain(f"Group pick: {selected_group} (weight {this_w}/{total_w})", explain)

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


def generate_from_nameset(nameset_id: str, count: int = 1, gender: Optional[str] = None, tag_filter: Optional[List[str]] = None, format_name: str = "default", explain: bool = False) -> List[str]:
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

    _explain(f"Nameset: {resolved} (simple)", explain)
    _explain(f"Format: {format_name} -> \"{format_str}\"", explain)

    # Legacy support for old format
    if not categories and "firstNames" in nameset:
        categories = {
            "firstName": nameset["firstNames"],
            "lastName": nameset.get("lastNames", [])
        }

    gender_weights = nameset.get("genderWeights", {"male": 50, "female": 50})

    # A tag filter can leave only one gender's entries in the anchor category
    # (e.g. --filter patrician --filter imperial matching a single male name).
    # Restrict the gender roll to the genders actually present in the filtered
    # pool so the cascade never forces a fallback to unfiltered entries.
    if gender is None and tag_filter:
        anchor_entries = categories.get("firstName") or next(iter(categories.values()), [])
        required = set(tag_filter)
        matching = [e for e in anchor_entries if required.issubset(set(e.get("tags", [])))]
        present = {e.get("gender") for e in matching}
        if matching and not (None in present or "unisex" in present):
            restricted = {g: w for g, w in gender_weights.items() if g in present}
            if restricted:
                gender_weights = restricted

    names = []
    used = set()

    for _ in range(count):
        # Roll one gender per name (unless forced) so it cascades across every
        # gendered category — otherwise a female firstName could pair with a
        # male patronym. Matches the grouped and aggregate paths.
        selected_gender = gender if gender else select_gender(gender_weights)
        attempts = 0
        while attempts < 100:
            # Pass gender to build_name_from_format for filtering at selection time
            name = build_name_from_format(format_str, categories, selected_gender, tag_filter=tag_filter)
            if name.lower() not in used or count > len(categories.get("firstName", [])):
                names.append(name)
                used.add(name.lower())
                break
            attempts += 1
        else:
            # Ran out of attempts
            names.append(build_name_from_format(format_str, categories, selected_gender, tag_filter=tag_filter))

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

    When in_optional is True, missing categories are silently skipped, and the
    enclosing optional section is dropped whole (see ``_render_tokens``).
    """

    def resolve(token, inner_optional):
        category = token["value"]
        if category in categories and categories[category]:
            entries = categories[category]
            # Determine effective gender: per-placeholder override takes precedence
            effective_gender = token.get("gender") or gender
            # Apply gender filtering if gender specified and category has gendered entries
            if effective_gender and any(e.get("gender") for e in entries):
                entries = filter_by_gender(entries, effective_gender, category)
            entries = filter_by_tags(entries, tag_filter, category)
            return select_weighted(entries)["name"]
        if not inner_optional:
            # Warn only for top-level missing categories, not optional content
            print(f"Warning: Format references undefined or empty category '{category}'", file=sys.stderr)
        return None

    text, _ok = _render_tokens(tokens, resolve, in_optional=in_optional)
    return text


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


def list_namesets(
    namespace_filter: Optional[str] = None,
    show_hidden: bool = False,
    verbose: bool = False,
    tag_filter: Optional[List[str]] = None,
    setting_filter: Optional[str] = None,
    type_filter: Optional[str] = None
):
    """List available namesets, grouped by namespace, brief by default.

    Hidden namesets (with ``"hidden": true``) are excluded by default.
    Pass ``show_hidden=True`` to include them.

    Filters:
        namespace_filter -- only show namesets in this namespace.
        tag_filter       -- list of tags; nameset must have at least one matching tag.
        setting_filter   -- only show namesets whose ``setting`` field matches exactly.
        type_filter      -- "aggregate", "grouped", "simple", or any literal ``type`` value.

    Output:
        Brief (default): one line per namespace with comma-separated bare IDs.
        Verbose: per-nameset detail block with name/setting/description/type/sources/tags.
    """
    if not custom_namesets:
        print("No namesets found")
        return

    # Group by namespace
    by_ns: Dict[str, List[Tuple[str, Dict, str]]] = {}
    for full_id, ns_data in custom_namesets.items():
        ns, bare = full_id.split(":", 1)
        by_ns.setdefault(ns, []).append((bare, ns_data, full_id))

    for ns in sorted(by_ns.keys()):
        items = by_ns[ns]

        # Apply filters
        if namespace_filter is not None and ns != namespace_filter:
            continue
        if tag_filter:
            items = [t for t in items if any(tag in t[1].get("tags", []) for tag in tag_filter)]
        if setting_filter:
            items = [t for t in items if t[1].get("setting") == setting_filter]
        if type_filter:
            def matches_type(t):
                ns_data = t[1]
                if type_filter == "aggregate":
                    return ns_data.get("type") == "aggregate"
                if type_filter == "grouped":
                    return "nameGroups" in ns_data
                if type_filter == "simple":
                    return ns_data.get("type") != "aggregate" and "nameGroups" not in ns_data
                return ns_data.get("type") == type_filter
            items = [t for t in items if matches_type(t)]

        visible = [t for t in items if not t[1].get("hidden", False)]
        hidden = [t for t in items if t[1].get("hidden", False)]
        shown = visible if not show_hidden else (visible + hidden)
        if not shown:
            continue

        ns_label = ns if ns else "(root)"
        if hidden and not show_hidden:
            print(f"\n{ns_label} ({len(visible)} visible, {len(hidden)} hidden)")
        else:
            print(f"\n{ns_label} ({len(shown)})")

        if verbose:
            for bare, data, full_id in sorted(shown):
                print(f"\n  {full_id}")
                if data.get("name"):
                    safe_print(f"    Name: {data['name']}")
                if data.get("setting"):
                    safe_print(f"    Setting: {data['setting']}")
                if data.get("description"):
                    safe_print(f"    Description: {data['description']}")
                if data.get("type") == "aggregate":
                    sources = data.get("sources", [])
                    labels = [s.get("label", s.get("nameset", "?")) for s in sources]
                    print(f"    Type: aggregate ({len(sources)} sources)")
                    print(f"    Sources: {', '.join(labels)}")
                elif "nameGroups" in data:
                    print(f"    Groups: {', '.join(data['nameGroups'].keys())}")
                if data.get("tags"):
                    print(f"    Tags: {', '.join(data['tags'])}")
        else:
            ids = ", ".join(bare for bare, _, _ in sorted(shown))
            print(f"  {ids}")


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


def _flatten_tokens(tokens):
    """Recursively yield all tokens including those nested in optional and repeat groups."""
    for t in tokens:
        yield t
        if t.get("type") == "optional":
            yield from _flatten_tokens(t["content"])
        elif t.get("type") == "repeat":
            yield from _flatten_tokens(t["content"])


def validate_all() -> Tuple[List[str], List[str]]:
    """Validate all loaded namesets. Returns (errors, warnings) lists.
    Also prints a summary to stdout.
    """
    errors: List[str] = []
    warnings: List[str] = []

    # Build namespace -> nameset count for typo detection
    ns_counts: Dict[str, int] = {}
    for full_id in custom_namesets:
        ns = full_id.split(":", 1)[0]
        ns_counts[ns] = ns_counts.get(ns, 0) + 1

    for full_id, nameset in custom_namesets.items():
        ns = full_id.split(":", 1)[0]

        # 1. Check aggregate sources resolve, and that the aggregate has any
        if nameset.get("type") == "aggregate":
            sources = nameset.get("sources", [])
            if not sources:
                errors.append(f"{full_id} - aggregate has no sources")
            for source in sources:
                ref = source.get("nameset")
                if not ref:
                    errors.append(f"{full_id} - aggregate source has no 'nameset' field")
                    continue
                resolved = resolve_nameset_ref(ref, current_namespace=ns)
                if not resolved:
                    errors.append(f"{full_id} - source '{ref}' not found")

            # 1b. Pool-policy slots carry their own source lists: refs must
            # resolve (error) and should actually hold the slot's category
            # (warning) — otherwise every roll silently falls back to anchor.
            for slot_name, slot_cfg in nameset.get("slots", {}).items():
                if not isinstance(slot_cfg, dict) or slot_cfg.get("policy") != "pool":
                    continue
                pool = slot_cfg.get("sources", [])
                if not pool:
                    errors.append(f"{full_id} - slot '{slot_name}' has policy 'pool' but no sources")
                for psrc in pool:
                    pref = psrc.get("nameset") if isinstance(psrc, dict) else None
                    if not pref:
                        errors.append(f"{full_id} - slot '{slot_name}' pool source has no 'nameset' field")
                        continue
                    presolved = resolve_nameset_ref(pref, current_namespace=ns)
                    if not presolved:
                        errors.append(f"{full_id} - slot '{slot_name}' pool source '{pref}' not found")
                        continue
                    pcats = get_name_categories(custom_namesets.get(presolved, {}))
                    if slot_name not in pcats or not pcats.get(slot_name):
                        warnings.append(
                            f"{full_id} - slot '{slot_name}' pool source '{pref}' has no '{slot_name}' entries"
                        )

        # 2. Check that grouped namesets actually have groups, and simple namesets have categories
        if nameset.get("type") != "aggregate":
            if "nameGroups" in nameset:
                if not nameset["nameGroups"]:
                    errors.append(f"{full_id} - grouped nameset has empty nameGroups")
            elif not nameset.get("nameCategories"):
                errors.append(f"{full_id} - nameset has no nameCategories or nameGroups")

        # 3. Check formats reference defined categories (skip for aggregates - they pull cats from sources).
        # Categories vary by nameset shape:
        #   - nameCategories: keys of that dict
        #   - nameGroups: implicit {firstName, lastName} (categories built per-group at generation time)
        if nameset.get("type") != "aggregate":
            if "nameGroups" in nameset:
                categories = {"firstName", "lastName"}
            else:
                categories = set(nameset.get("nameCategories", {}).keys())

            # Check both legacy `format` string and new `formats` map
            templates_to_check = []
            if "formats" in nameset:
                for fname, fdef in nameset["formats"].items():
                    template = fdef if isinstance(fdef, str) else fdef.get("template", "")
                    templates_to_check.append((fname, template))
            elif "format" in nameset:
                templates_to_check.append(("format", nameset["format"]))

            for fname, template in templates_to_check:
                try:
                    tokens = parse_format(template)
                except Exception as e:
                    errors.append(f"{full_id} - format '{fname}' parse error: {e}")
                    continue
                for tok in _flatten_tokens(tokens):
                    if tok.get("type") == "placeholder":
                        cat = tok["value"]
                        if cat not in categories:
                            warnings.append(
                                f"{full_id} - format '{fname}' references undefined category '{{{cat}}}'"
                            )

        # 4. Legacy format field warning
        if "format" in nameset and "formats" not in nameset:
            warnings.append(f"{full_id} - uses legacy 'format' field, suggest migration to 'formats' map")

    # 5. Namespace typo detection: warn when two namespaces are fuzzy-similar.
    # Common pattern: a typo creates a near-duplicate namespace with 1 entry,
    # while the canonical namespace has many.
    real_namespaces = [n for n in ns_counts if n]
    seen_pairs: set = set()
    for ns_name in real_namespaces:
        others = [n for n in real_namespaces if n != ns_name]
        for match in difflib.get_close_matches(ns_name, others, n=3, cutoff=0.8):
            pair = tuple(sorted([ns_name, match]))
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            a, b = pair
            warnings.append(
                f"namespaces '{a}' ({ns_counts[a]}) and '{b}' ({ns_counts[b]}) "
                f"look similar - possible typo?"
            )

    print(f"\n{len(custom_namesets)} namesets validated, {len(errors)} errors, {len(warnings)} warnings")
    for e in errors:
        print(f"E {e}")
    for w in warnings:
        print(f"W {w}")
    return errors, warnings


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
        print("  full --nameset NAME [--count N] [--group G] [--gender G] [--filter TAG ...] [--format NAME] [--explain]")
        print("       Generate name(s) from nameset")
        print("       --filter TAG    Restrict generation to entries with TAG.")
        print("                       Repeat for AND semantics (entries must have ALL tags).")
        print("       --format NAME   Use a named format variant from the nameset's 'formats' map.")
        print("                       Defaults to 'default'. Falls back to legacy 'format' field.")
        print("       --explain       Print an assembly trace to stderr showing nameset, format,")
        print("                       source/group picks, and per-slot policy decisions.")
        print("  groups --nameset NAME")
        print("       List groups in a nameset")
        print("  list [--namespace NS] [--all] [--verbose] [--tag TAG ...] [--setting NAME] [--type T]")
        print("       List available namesets, grouped by namespace.")
        print("       --namespace NS  Only show namesets in this namespace.")
        print("       --all           Include hidden namesets (excluded by default).")
        print("       --verbose       Show per-nameset detail (name/setting/desc/type/sources/tags).")
        print("       --tag TAG       Only show namesets having this tag. Repeat for OR semantics.")
        print("       --setting NAME  Only show namesets whose 'setting' field matches.")
        print("       --type T        Filter by type: aggregate, grouped, simple, or any literal type value.")
        print("  validate")
        print("       Lint all loaded namesets. Reports errors (broken aggregate refs, undefined")
        print("       format placeholders) and warnings (legacy 'format' field).")
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
    list_tag_filter: List[str] = []
    setting_filter: Optional[str] = None
    type_filter: Optional[str] = None
    format_name = "default"
    show_hidden = False
    verbose = False
    explain = False

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
        elif sys.argv[i] == "--tag" and i + 1 < len(sys.argv):
            list_tag_filter.append(sys.argv[i + 1])
            i += 2
        elif sys.argv[i] == "--setting" and i + 1 < len(sys.argv):
            setting_filter = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--type" and i + 1 < len(sys.argv):
            type_filter = sys.argv[i + 1]
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
        elif sys.argv[i] == "--verbose":
            verbose = True
            i += 1
        elif sys.argv[i] == "--explain":
            explain = True
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
            results = generate_from_aggregate(
                nameset, count, group, gender,
                return_source=show_group,
                tag_filter=effective_tag_filter,
                format_name=format_name,
                explain=explain,
            )
            if show_group:
                for name, src in results:
                    print(f"{name}|{src}")
            else:
                for name in results:
                    print(name)
        elif "nameGroups" in ns:
            # Grouped nameset - select from groups
            results = generate_from_nameset_with_groups(
                nameset, count, group, gender,
                return_group=show_group,
                tag_filter=effective_tag_filter,
                format_name=format_name,
                explain=explain,
            )
            if show_group:
                for name, grp in results:
                    print(f"{name}|{grp}")
            else:
                for name in results:
                    print(name)
        else:
            # Simple nameset
            names = generate_from_nameset(
                nameset, count, gender,
                tag_filter=effective_tag_filter,
                format_name=format_name,
                explain=explain,
            )
            for name in names:
                print(name)

    elif command == "groups":
        if not nameset:
            print("Error: --nameset is required", file=sys.stderr)
            sys.exit(1)
        list_groups(nameset)

    elif command == "list":
        list_namesets(
            namespace_filter=namespace_filter,
            show_hidden=show_hidden,
            verbose=verbose,
            tag_filter=list_tag_filter if list_tag_filter else None,
            setting_filter=setting_filter,
            type_filter=type_filter,
        )

    elif command == "validate":
        validate_all()

    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
