# Creating Namesets

Namesets provide culturally-appropriate names for NPCs, places, or any entity needing generated names. The namegen tool supports three nameset types with flexible composition.

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

Control the male/female distribution for the entire nameset:

```json
"genderWeights": {"male": 75, "female": 25}
```

Default is `{"male": 50, "female": 50}`. Can be overridden with `--gender male` or `--gender female`.

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
python scripts/namegen.py full --nameset station-crew --group japanese --count 5

# See which source was selected
python scripts/namegen.py full --nameset station-crew --show-group
# Output: Takeshi Yamamoto|japanese
```

### Listing Sources

```bash
python scripts/namegen.py groups --nameset station-crew
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

- **simple-western.json** - Basic first/last name structure
- **aggregate-metropolitan.json** - Multi-source composition
- **custom-categories.json** - Non-Western naming patterns (epithets, clans)

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
