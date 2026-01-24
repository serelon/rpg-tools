# Namegen Tool Enhancements Plan

**Date:** 2026-01-24
**Feature:** Enhanced name generation with flexible gender system and format string improvements
**Branch:** `feature/namegen-enhancements`

## Overview

Overhaul the namegen tool to support complex fantasy naming conventions. Fixes aggregate namesets with custom categories (#62), implements proper gender cascading across all categories (#63), adds optional sections with weights, and introduces random pattern generation for constructs/designations.

## Design Summary

**Key Changes:**
1. Gender cascades to ALL categories, not just firstName
2. Per-placeholder gender override: `{category:male}`
3. Optional sections: `[ {epithet}]` and `[ {epithet}:30%]`
4. Random generation: `{random:1-99}` (range) and `{random:AAA}` (pattern)
5. Arbitrary gender support via genderWeights

---

## Batch 1: Bugfix - Aggregate Custom Categories (#62)

### Task 1.1: Create feature branch
```bash
git checkout -b feature/namegen-enhancements develop
```

### Task 1.2: Fix `generate_single_name()` to use source categories
Current code hardcodes `firstName`/`lastName` lookup. Fix to:
- Use source nameset's actual `nameCategories`
- Use source nameset's `format` string (not aggregate's)
- Pass through all categories, not just firstName/lastName

### Task 1.3: Fix `generate_from_aggregate()` delegation
- After selecting a source, delegate fully to source's format and categories
- Remove hardcoded category assumptions
- Let source nameset handle its own structure

### Task 1.4: Test aggregate with custom categories
- Create test case with lizardfolk nameset (clutchSyllable, selfSyllable)
- Verify aggregate produces actual names, not empty strings
- Verify no "undefined category" warnings

---

## Batch 2: Gender Cascade System (#63)

### Task 2.1: Modify `build_name_from_format()` to accept gender
Add `gender: Optional[str] = None` parameter.
- Thread gender through from generation entry points
- Apply to each category during name building

### Task 2.2: Apply gender filter to ALL categories
In `build_name_from_format()`:
- Before selecting from any category, apply `filter_by_gender(entries, gender)`
- Not just firstName - all categories with gender-tagged entries

### Task 2.3: Add warning for empty filtered categories
When `filter_by_gender()` returns empty and falls back:
```python
if not filtered:
    print(f"Warning: {category} has no entries for gender '{gender}', using unfiltered", file=sys.stderr)
    return entries
```

### Task 2.4: Thread gender through all generation paths
Update these functions to pass gender to `build_name_from_format()`:
- `generate_from_nameset()`
- `generate_from_nameset_with_groups()`
- `generate_from_aggregate()` / `generate_single_name()`

---

## Batch 3: Per-Placeholder Gender Override

### Task 3.1: Extend format parser for gender syntax
Update `parse_format()` to recognize `{category:gender}`:
```python
# Pattern: {category} or {category:gender}
pattern = r'\{(\w+)(?::(\w+))?\}'
```
Token becomes: `{"type": "placeholder", "category": "firstName", "gender": "male"}`

### Task 3.2: Apply per-placeholder gender in `build_name_from_format()`
When building name:
- If placeholder has explicit gender → use that
- Else → use character's gender (passed in)
- Filter category accordingly

### Task 3.3: Update nameset-guide.md with gender override syntax
Document:
```json
"format": "{firstName} {firstName:male}{suffix} {firstName:female}{suffix}"
```
Explain: `:gender` overrides character gender for that placeholder only.

---

## Batch 4: Arbitrary Genders

### Task 4.1: Remove hardcoded male/female assumptions
In `select_gender()` and `filter_by_gender()`:
- Work with whatever genders are defined in `genderWeights`
- No hardcoded defaults beyond `{"male": 50, "female": 50}`

### Task 4.2: Update `filter_by_gender()` for arbitrary genders
Rules:
- `unisex` entries match ANY gender
- Untagged entries (gender: null) match ANY gender
- Explicit gender tags require exact match
- Works for `neuter`, `construct`, or any custom gender

### Task 4.3: Document arbitrary genders in nameset-guide.md
```json
"genderWeights": {"male": 40, "female": 40, "neuter": 20}
```
Entries can use any gender tag that appears in genderWeights.

---

## Batch 5: Optional Sections

### Task 5.1: Implement optional section parsing
Update `parse_format()` to properly handle `[content]`:
- Already parses but treated as literal
- Mark as `{"type": "optional", "content": parsed_inner_tokens, "weight": 100}`

### Task 5.2: Implement weighted optional syntax
Parse `[ {category}:30%]`:
- Extract weight percentage
- Store as `{"type": "optional", "content": [...], "weight": 30}`

### Task 5.3: Implement optional section logic in `build_name_from_format()`
For optional tokens:
- Roll against weight percentage (default 100%)
- If roll succeeds AND inner categories have entries → include
- If category empty → skip section (no warning, graceful degradation)
- Clean up whitespace (avoid double spaces)

### Task 5.4: Document optional sections
```json
"format": "{firstName}[ {epithet}] {lastName}"        // include if exists
"format": "{firstName}[ {epithet}:30%] {lastName}"   // 30% chance
```

---

## Batch 6: Random Pattern Generation

### Task 6.1: Add `{random:...}` placeholder parsing
In `parse_format()`, detect `{random:pattern}`:
- Token: `{"type": "random", "pattern": "AAA"}` or `{"type": "random", "range": [1, 99]}`

### Task 6.2: Implement range detection
Detect `N-M` where both are integers with single dash:
- `1-99` → range
- `0-255` → range
- `000` → pattern (no dash)
- `A-Z` → pattern (non-integer)

### Task 6.3: Implement pattern generation
Pattern characters:
- `A` → random uppercase letter (A-Z)
- `a` → random lowercase letter (a-z)
- `0` → random digit (0-9)
- `X` → random hex digit (0-9, A-F)
- Anything else → literal

```python
def generate_pattern(pattern: str) -> str:
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
```

### Task 6.4: Implement range generation
```python
def generate_range(min_val: int, max_val: int) -> str:
    return str(random.randint(min_val, max_val))
```

### Task 6.5: Document random generation
Ranges:
```json
"{random:1-99}"      // 1 to 99
"{random:0-255}"     // 0 to 255
```

Patterns:
```json
"{random:AAA}"       // 3 uppercase letters → "KXR"
"{random:000}"       // 3 zero-padded digits → "042"
"{random:XXX}"       // 3 hex digits → "A7F"
```

Composed patterns (for mixed):
```json
"{random:AA}-{random:0000}"   // "KX-0742"
```

---

## Batch 7: Documentation & Testing

### Task 7.1: Update nameset-guide.md comprehensively
- Gender cascade explanation
- Per-placeholder override syntax
- Arbitrary genders
- Optional sections with weights
- Random generation (ranges and patterns)
- Examples for each feature

### Task 7.2: Add example namesets demonstrating new features
Create `references/examples/namesets/`:
- `dwarven-patronymic.json` - gender-filtered patronyms/matronyms
- `construct-designations.json` - random patterns for robots/constructs
- `fantasy-epithets.json` - optional epithets with weights

### Task 7.3: Manual testing
- Dwarf names with patronymic/matronymic suffixes
- Aggregate with custom categories (lizardfolk/korvathi)
- Construct designations (CT-0000 style)
- Optional epithets at 30% rate
- Non-binary gender filtering

### Task 7.4: Create PR
- Reference issues #62 and #63
- Summary of all new features
- Test plan with example outputs
- "Closes #62, Closes #63" in body

---

## Format String Grammar (Final)

```
format      = token*
token       = placeholder | optional | random | literal
placeholder = "{" category (":" gender)? "}"
optional    = "[" token* (":" weight "%")? "]"
random      = "{random:" (range | pattern) "}"
range       = integer "-" integer
pattern     = (A | a | 0 | X | literal_char)+
literal     = any_char_except_brackets
```

**Examples:**
```
{firstName}                    // character's gender
{firstName:male}               // force male
[ {epithet}]                   // optional, include if exists
[ {epithet}:30%]               // optional, 30% chance
{random:1-99}                  // range 1-99
{random:AAA}                   // 3 uppercase letters
{random:AA}-{random:0000}      // composed: "KX-0742"
```

---

## Notes

- All changes are backwards-compatible (existing namesets work unchanged)
- Gender cascade is automatic - no schema changes required
- Optional sections gracefully degrade when categories are empty
- Random generation is self-contained (no external dependencies)
- Pattern vs range detection uses simple heuristic (single dash with integers on both sides = range)
