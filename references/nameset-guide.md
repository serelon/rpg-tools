# Creating Namesets

Namesets provide culturally-appropriate names for NPCs, places, or any entity needing generated names. The namegen tool supports three nameset types with flexible composition.

## Contents

- [Quick Reference](#quick-reference)
- [Nameset Types](#nameset-types) — Simple, Aggregate, Grouped
- [Schema Reference](#schema-reference) — Core fields, name categories, gender weights, frequency
- [Format Strings](#format-strings)
- [Aggregate Namesets](#aggregate-namesets)
- [File Discovery](#file-discovery)
- [Design Guidelines](#design-guidelines)
- [Examples](#examples)
- [Legacy Format](#legacy-format)

---

## Quick Reference

```bash
python scripts/namegen.py list                                    # List all namesets
python scripts/namegen.py full --nameset NAME                     # Generate one name
python scripts/namegen.py full --nameset NAME --count 5           # Generate multiple
python scripts/namegen.py full --nameset NAME --gender female     # Filter by gender
python scripts/namegen.py full --nameset NAME --group eastern     # Force specific group/source
python scripts/namegen.py full --nameset NAME --show-group        # Show which group was selected
python scripts/namegen.py groups --nameset NAME                   # List groups/sources in nameset
```

---

## Nameset Types

### 1. Simple Nameset

The most common type. Categories of names combined via format string.

```json
{
  "id": "frontier-colonists",
  "name": "Frontier Colonists",
  "description": "Working-class names for frontier settlements",
  "setting": "Space Western Campaign",
  "tags": ["frontier", "working-class", "colonial"],
  "nameCategories": {
    "firstName": [
      {"name": "Jake", "gender": "male"},
      {"name": "Rosa", "gender": "female"},
      {"name": "River", "gender": "unisex"}
    ],
    "lastName": [
      {"name": "Reyes"},
      {"name": "Chen"},
      {"name": "Okonkwo"}
    ]
  },
  "format": "{firstName} {lastName}"
}
```

### 2. Aggregate Nameset

Composes names from multiple source namesets with weighted selection. Perfect for multicultural settings.

```json
{
  "id": "station-personnel",
  "name": "Station Personnel",
  "description": "Multinational names for space station crew",
  "type": "aggregate",
  "genderWeights": {"male": 50, "female": 50},
  "format": "{firstName} {lastName}",
  "sources": [
    {"nameset": "names-american", "weight": 30, "label": "american"},
    {"nameset": "names-chinese", "weight": 25, "label": "chinese"},
    {"nameset": "names-russian", "weight": 20, "label": "russian"},
    {"nameset": "names-indian", "weight": 15, "label": "indian"},
    {"nameset": "names-brazilian", "weight": 10, "label": "brazilian"}
  ]
}
```

Use `--group american` to force a specific source, or `--show-group` to see which was selected.

### 3. Grouped Nameset

Names organized into weighted groups within a single file. Useful when sources share structure but differ in style.

```json
{
  "id": "fantasy-cultures",
  "name": "Fantasy Cultures",
  "description": "Names grouped by fictional culture",
  "genderWeights": {"male": 50, "female": 50},
  "format": "{firstName} {lastName}",
  "nameGroups": {
    "northern": {
      "weight": 40,
      "firstNames": [
        {"name": "Bjorn", "gender": "male"},
        {"name": "Freya", "gender": "female"}
      ],
      "lastNames": [
        {"name": "Ironforge"},
        {"name": "Stormborn"}
      ]
    },
    "southern": {
      "weight": 60,
      "firstNames": [
        {"name": "Marcus", "gender": "male"},
        {"name": "Lucia", "gender": "female"}
      ],
      "lastNames": [
        {"name": "Aurelius"},
        {"name": "Varro"}
      ]
    }
  }
}
```

---

## Schema Reference

### Core Fields

| Field | Required | Description |
|-------|----------|-------------|
| `id` | Yes | Unique identifier (lowercase, hyphens) |
| `name` | Yes | Display name |
| `description` | No | Explains the nameset's purpose and style |
| `setting` | No | Campaign or world this nameset belongs to |
| `tags` | No | Array of searchable tags |
| `format` | No | Format string (default: `"{firstName} {lastName}"`) |

### Name Categories

The `nameCategories` object holds arrays of name entries:

```json
"nameCategories": {
  "firstName": [...],
  "lastName": [...],
  "epithet": [...],      // Custom category
  "clanName": [...]      // Custom category
}
```

Each entry in a category:

```json
{"name": "Marcus", "gender": "male", "frequency": 5}
```

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | The actual name string |
| `gender` | No | `"male"`, `"female"`, or `"unisex"`. Omit for gender-neutral. |
| `frequency` | No | Relative weight (default: 1). Higher = more likely. |

### Gender Weights

Control the gender distribution for the entire nameset:

```json
"genderWeights": {"male": 75, "female": 25}
```

Default is `{"male": 50, "female": 50}`. Can be overridden with `--gender male` or `--gender female`.

#### Arbitrary Genders

Gender weights can use **any gender identifiers**, not just male/female:

```json
// Fantasy creatures with three genders
"genderWeights": {"male": 40, "female": 40, "neuter": 20}

// Constructs/machines
"genderWeights": {"military": 60, "civilian": 30, "prototype": 10}
```

Name entries can use matching gender tags:

```json
"firstName": [
  {"name": "Krix", "gender": "neuter"},
  {"name": "Unit-7", "gender": "military"},
  {"name": "ARIA", "gender": "civilian"}
]
```

When generating with `--gender neuter`, entries tagged as `"neuter"`, `"unisex"`, or untagged will be selected. This allows creative use of the gender system for any categorical filtering.

#### Gender Cascade

When a gender is selected (either via `--gender` flag or rolled from `genderWeights`), it applies to **ALL categories**, not just `firstName`.

This enables gendered entries in any category:

```json
"nameCategories": {
  "firstName": [
    {"name": "Erik", "gender": "male"},
    {"name": "Astrid", "gender": "female"}
  ],
  "title": [
    {"name": "Lord", "gender": "male"},
    {"name": "Lady", "gender": "female"},
    {"name": "Ser", "gender": "unisex"}
  ],
  "suffix": [
    {"name": "-son", "gender": "male"},
    {"name": "-dottir", "gender": "female"}
  ]
},
"format": "{title} {firstName} Storm{suffix}"
// Male: "Lord Erik Stormson"
// Female: "Lady Astrid Stormdottir"
```

Without gender tags, entries are selected regardless of the current gender.

### Frequency Weighting

Make common names appear more often:

```json
"lastName": [
  {"name": "Wang", "frequency": 10},
  {"name": "Li", "frequency": 10},
  {"name": "Zhang", "frequency": 9},
  {"name": "Ouyang", "frequency": 1}
]
```

Frequencies are relative weights, not percentages. A name with `frequency: 10` is 10x more likely than one with `frequency: 1`.

---

## Format Strings

Format strings define how categories combine into full names.

### Basic Placeholders

```json
"format": "{firstName} {lastName}"
// Output: "Marcus Chen"
```

### Custom Categories

Define any category name you need:

```json
"nameCategories": {
  "firstName": [...],
  "epithet": [
    {"name": "the Swift"},
    {"name": "Bear-Slayer"},
    {"name": "One-Eye"}
  ],
  "clan": [
    {"name": "of the River-Folk"},
    {"name": "of the High-Passes"}
  ]
},
"format": "{firstName} {epithet}"
// Output: "Keth the Swift"
```

### Per-Placeholder Gender Override

Force a specific gender for individual placeholders using `{category:gender}` syntax:

```json
"format": "{firstName} {firstName:male}son"
// If global gender is female: "Freya Bjornson" (female first, male patronym base)
```

This is essential for patronymic/matronymic naming systems where you need the parent's name to be a different gender than the child:

```json
// Dwarven patronymic: child's name + parent's name + suffix
"format": "{firstName} {firstName:male}sson {firstName:female}sdottir"
// Example: "Thorin Grimsson Hildisdottir" (child, father's name, mother's name)
```

The per-placeholder gender overrides the global `--gender` flag or rolled gender for that specific placeholder only.

### Optional Sections

Wrap content in square brackets to make it optional:

```json
"format": "{firstName}[ {epithet}] {lastName}"
// If epithet exists: "Marcus the Brave Chen"
// If epithet is missing/empty: "Marcus Chen"
```

Add a percentage weight to control inclusion probability:

```json
"format": "{firstName}[ {epithet}:30%] {lastName}"
// 30% chance to include epithet even when available
// Output: "Marcus Chen" (70% of the time)
// Output: "Marcus the Brave Chen" (30% of the time)
```

Without a weight suffix, optional sections are included whenever their content resolves (100% when content exists).

**Nested optionals** are supported for complex conditional naming:

```json
"format": "{firstName}[{title}[ {epithet}]] {lastName}"
// If both exist: "Marcus Lord the Wise Chen"
// If only title: "Marcus Lord Chen"
// If neither: "Marcus Chen"
```

### Random Generation

Generate random numbers and character patterns for designations, serial numbers, and procedural names.

**Numeric ranges** - Random integer between min and max (inclusive):

```json
"format": "{prefix}-{random:1-999}"
// Output: "XR-742"
```

**Character patterns** - Each pattern character generates a random value:

| Pattern | Generates | Example |
|---------|-----------|---------|
| `A` | Uppercase letter (A-Z) | `AAA` -> `"KMZ"` |
| `a` | Lowercase letter (a-z) | `aaa` -> `"qxm"` |
| `0` | Digit (0-9) | `000` -> `"847"` |
| `X` | Hex digit (0-9, A-F) | `XXXX` -> `"3A7F"` |
| Other | Literal (preserved) | `A-0` -> `"K-7"` |

Examples:

```json
// Robot designation
"format": "{prefix}-{random:0000}"
// Output: "MK-4728"

// Ship registry
"format": "{random:AAA}-{random:000}"
// Output: "KMZ-847"

// Hex identifier
"format": "0x{random:XXXXXXXX}"
// Output: "0x3A7F9C2E"

// Mixed pattern
"format": "{random:AA-000-aa}"
// Output: "KM-742-qx"
```

### Multiple Formats

You can define alternative formats (the tool uses `format` by default):

```json
"format": "{firstName} {epithet}",
"formatFormal": "{firstName} {epithet} {clan}",
"formatShort": "{firstName}"
```

Note: Currently only `format` is used by the tool. Alternative formats serve as documentation for manual use.

---

## Aggregate Namesets

Aggregates compose from multiple source namesets, each with its own weight.

### Source Structure

```json
"sources": [
  {
    "nameset": "names-japanese",   // ID of source nameset (must exist)
    "weight": 15,                  // Relative selection weight
    "label": "japanese"            // Display label for --show-group
  }
]
```

### How It Works

1. Tool selects a source based on weights
2. Generates name from that source's `nameCategories`
3. Uses aggregate's `format` and `genderWeights`

### Forcing a Source

```bash
# Force Japanese names only
python scripts/namegen.py full --nameset station-personnel --group japanese --count 5

# See which source was selected
python scripts/namegen.py full --nameset station-personnel --show-group
# Output: Takeshi Yamamoto|japanese
```

### Listing Sources

```bash
python scripts/namegen.py groups --nameset station-personnel
# Shows each source with weight percentage and name counts
```

---

## File Discovery

Namesets are discovered from multiple locations (in order, later overrides earlier):

1. `{cwd}/namesets/` - Current working directory
2. `{parent}/namesets/` - Parent directories
3. `campaigns/*/namesets/` - Campaign subdirectories
4. `tools/data/namesets/` - Bundled default namesets
5. `/mnt/user-data/uploads/namesets/` - Claude.ai uploads
6. `/mnt/user-data/uploads/*-names.json` - Loose uploaded files
7. `/home/claude/*/namesets/` - Extracted skill bundles

### File Naming

Two patterns work:

- **Directory**: `namesets/my-culture.json`
- **Loose files**: `my-culture-names.json` (must end in `-names.json`)

---

## Design Guidelines

### 1. Think About Structure First

Not all cultures use "first name + last name":

| Culture Type | Structure | Example Format |
|--------------|-----------|----------------|
| Modern Western | Given + Family | `{firstName} {lastName}` |
| East Asian | Family + Given | `{lastName} {firstName}` |
| Patronymic | Given + Parent's name | `{firstName} {patronymic}` |
| Epithet-based | Given + Descriptor | `{firstName} {epithet}` |
| Single name | Given only | `{firstName}` |
| Clan-based | Given + Clan marker | `{firstName} {clan}` |

### 2. Consider Frequency Distribution

Real name distributions follow power laws. Common names should have higher frequency:

```json
// Realistic Chinese surname distribution
{"name": "Wang", "frequency": 10},  // ~7% of population
{"name": "Li", "frequency": 10},    // ~7% of population
{"name": "Ouyang", "frequency": 1}  // Rare compound surname
```

### 3. Default Counts (When Applicable)

For simple Western-style namesets:
- 200 male first names
- 200 female first names
- 100 unisex first names (optional)
- 200 last names

Adjust based on actual cultural patterns.

### 4. Authenticity Over Fantasy

Names should feel plausible for their context. Research actual naming conventions rather than inventing "fantasy-sounding" names.

### 5. Usability

Names should be:
- Pronounceable by your players
- Memorable enough to track NPCs
- Distinct enough to avoid confusion

---

## Examples

See `references/examples/namesets/` for complete working examples:

### Basic Examples

- **simple-western.json** - Basic first/last name structure with gender tags and frequency weighting
- **aggregate-example.json** - Multi-source composition from multiple namesets
- **custom-categories.json** - Non-Western naming patterns (epithets, clans)

### Advanced Feature Examples

- **dwarven-patronymic.json** - Demonstrates per-placeholder gender override for patronymic/matronymic naming. Uses `{firstName:male}` and `{firstName:female}` to select parent names independent of child's gender.

- **construct-designations.json** - Demonstrates random generation patterns for robots, constructs, and procedural designations. Shows `{random:0000}` numeric patterns and `{random:AAA}` letter patterns.

- **fantasy-epithets.json** - Demonstrates optional sections with probability weights. Uses `[ {epithet}:30%]` syntax to occasionally include earned titles.

---

## Legacy Format

Older namesets may use `firstNames` and `lastNames` arrays directly:

```json
{
  "id": "old-format",
  "firstNames": [
    {"name": "Jake", "gender": "male"}
  ],
  "lastNames": [
    {"name": "Smith"}
  ]
}
```

This is automatically converted to `nameCategories` internally. New namesets should use `nameCategories`.
