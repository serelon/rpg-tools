# Creating Namesets

Namesets provide culturally-appropriate names for NPCs, places, ships, constructs, or any entity needing generated names. The namegen tool supports three nameset types (simple, aggregate, grouped) with namespacing, inheritance, named format variants, per-entry tags, slot-mixed aggregate composition, and structured cultural metadata.

All v1 namesets keep working unchanged. Every v2 capability is opt-in.

## Contents

- [Quick Reference](#quick-reference)
- [Nameset Types](#nameset-types)
- [File Layout & Namespaces](#file-layout--namespaces)
- [Schema Reference](#schema-reference)
- [Format Strings](#format-strings)
- [Aggregate Composition](#aggregate-composition)
- [Inheritance (extends)](#inheritance-extends)
- [Per-Entry Tags & Filtering](#per-entry-tags--filtering)
- [Design Block](#design-block)
- [Hidden Flag](#hidden-flag)
- [Validate Command](#validate-command)
- [The --explain Flag](#the---explain-flag)
- [Migration from v1](#migration-from-v1)
- [Templates](#templates)
- [Backwards Compatibility](#backwards-compatibility)

---

## Quick Reference

### Listing namesets

```bash
python scripts/namegen.py list                            # Group by namespace, hide hidden
python scripts/namegen.py list --all                      # Include hidden namesets
python scripts/namegen.py list --verbose                  # Show name/setting/desc/sources/tags
python scripts/namegen.py list --namespace longwatch      # Restrict to one namespace
python scripts/namegen.py list --tag historical           # Filter by nameset-level tag (repeatable, OR)
python scripts/namegen.py list --setting "The Long Watch" # Filter by setting field
python scripts/namegen.py list --type aggregate           # Filter by nameset type
```

### Generating names

```bash
python scripts/namegen.py full --nameset NAME                       # One name with default format
python scripts/namegen.py full --nameset namespace:NAME              # Qualified ID lookup
python scripts/namegen.py full --nameset NAME --count 5             # Multiple names
python scripts/namegen.py full --nameset NAME --gender female       # Force a gender
python scripts/namegen.py full --nameset NAME --group eastern       # Force a source/group
python scripts/namegen.py full --nameset NAME --show-group          # Show which source/group fired
python scripts/namegen.py full --nameset NAME --filter patrician    # Restrict to entries with tag
python scripts/namegen.py full --nameset NAME --filter patrician --filter imperial  # AND semantics
python scripts/namegen.py full --nameset NAME --format formal       # Use a named format variant
python scripts/namegen.py full --nameset NAME --format ?            # List available formats
python scripts/namegen.py full --nameset NAME --explain             # Print assembly trace to stderr
```

### Listing groups/sources within a nameset

```bash
python scripts/namegen.py groups --nameset NAME
```

### Validating

```bash
python scripts/namegen.py validate
```

---

## Nameset Types

Three types are supported. The same v2 schema features (namespace, formats map, design block, per-entry tags, hidden flag) apply to all of them.

### Simple

Categories of entries combined via a format string. Most common type.

```json
{
  "namespace": "valdran",
  "id": "harbor-folk",
  "name": "Harbor Folk of Valdran",
  "genderWeights": {"male": 50, "female": 50},
  "formats": {"default": "{firstName} {lastName}"},
  "nameCategories": {
    "firstName": [
      {"name": "Tessa", "gender": "female"},
      {"name": "Bram",  "gender": "male"}
    ],
    "lastName": [
      {"name": "Netmender"},
      {"name": "Saltcrest"}
    ]
  }
}
```

### Aggregate

Composes names from multiple source namesets with weighted selection. Sources may themselves be aggregates (nested). Per-source overrides and per-slot policies enable diaspora-style mixing.

```json
{
  "namespace": "longwatch",
  "id": "core-worlds",
  "type": "aggregate",
  "formats": {"default": "{firstName} {lastName}"},
  "sources": [
    {"nameset": "east-asian-evolved", "weight": 30, "label": "east-asian"},
    {"nameset": "core:russian",       "weight": 15, "label": "russian"}
  ],
  "slots": {
    "lastName": {"policy": "mix", "rate": 0.3}
  }
}
```

See [Aggregate Composition](#aggregate-composition) for full detail.

### Grouped

Several sub-populations sharing structure but differing in roster, all in one file. Lighter than aggregates — no separate source files.

```json
{
  "namespace": "emberfall",
  "id": "kaldori-tribes",
  "formats": {"default": "{firstName} of the {lastName}"},
  "nameGroups": {
    "stag-tribe":  {"weight": 50, "firstNames": [...], "lastNames": [...]},
    "raven-tribe": {"weight": 30, "firstNames": [...], "lastNames": [...]}
  }
}
```

Grouped namesets currently expose only the `firstName` and `lastName` slots, drawn from each group's `firstNames`/`lastNames` arrays. For richer slot vocabulary, use a simple nameset with `nameCategories`, or model each group as a separate nameset and combine via an aggregate.

---

## File Layout & Namespaces

### Single-nameset files (v1 layout)

A `.json` file may contain a single nameset:

```json
{
  "namespace": "valdran",
  "id": "harbor-folk",
  ...
}
```

This is the v1 layout and continues to work unchanged.

### Multi-nameset files (v2)

A file may contain N namesets under a top-level `namesets` array:

```json
{
  "namespace": "metropolitan",
  "namesets": [
    {"id": "russian", "nameCategories": {...}},
    {"id": "polish",  "nameCategories": {...}},
    {"id": "german",  "nameCategories": {...}}
  ]
}
```

Discovery flattens both forms into the same internal dict, keyed by full `namespace:id`. Loose-file pattern (`*-names.json`) still works.

### Setting the namespace

Three options:

1. **File-level** — `"namespace": "metropolitan"` at the top of a multi-nameset file applies to every contained nameset.
2. **Per-nameset** — `"namespace": "medieval"` on an individual nameset overrides the file-level value.
3. **Default** — no declaration, namespace becomes `""` (root). All v1 namesets land here.

Full ID is always exactly `namespace:id` — single colon, two segments. Never deeper.

### Reference resolution

When one nameset references another (in aggregate `sources`, `extends`, slot `forced.nameset`, etc.):

- **Bare ID** (`"english"`) — resolved within the *current* namespace first, then falls back to root (`""`).
- **Qualified ID** (`"metropolitan:english"`) — exact lookup, no fallback.
- **Cross-namespace works fine** — a `medieval` aggregate can reference `metropolitan:russian`.

If two files declare the same `namespace:id`, last-loaded wins (matches the discovery merge behavior). `validate` flags duplicates.

### Recommended namespace taxonomy

One namespace per nameset. Cross-cutting axes go on `tags`. Pick the most specific namespace that still allows reuse.

| Kind | Example namespaces | Use for |
|------|-------------------|---------|
| **Reserved: built-in** | `core` | Bundled defaults shipped in `tools/data/namesets/` |
| **Reserved: campaign** | `aegis`, `emberfall`, `threadlight` | Campaign-specific (matches campaign folder name) |
| Era | `medieval`, `1940s`, `victorian`, `bronze-age`, `ancient` | Real-world historical |
| Cultural stratum | `metropolitan`, `frontier`, `imperial`, `nomadic` | Class/society axis |
| Genre | `fantasy`, `scifi`, `cyberpunk`, `weird`, `post-apoc` | Setting type |
| Species | `elven`, `dwarven`, `goblinoid`, `lizardfolk` | Non-human, cross-setting |
| Setting | `valdran`, `caldworth`, `solramis` | Specific worlds shared across campaigns |

### Discovery paths

Namesets are discovered (in order; later overrides earlier) from:

1. `{cwd}/namesets/`
2. `{parent}/namesets/`
3. `campaigns/*/namesets/`
4. `tools/data/namesets/` (bundled defaults — populates the `core` namespace)
5. `/mnt/user-data/uploads/namesets/`
6. `/mnt/user-data/uploads/*-names.json`
7. `/home/claude/*/namesets/`

File naming: directory-style (`namesets/my-culture.json`) or loose (`my-culture-names.json` — must end in `-names.json`).

---

## Schema Reference

### Top-level fields (leaf nameset)

| Field | Required | Description |
|-------|----------|-------------|
| `id` | Yes | Unique within namespace. Lowercase, hyphens preferred. |
| `namespace` | No | Single token. Defaults to `""` (root). May be set at file level instead. |
| `name` | No | Display name (shown by `list --verbose`). |
| `description` | No | Short description for human/LLM consumption. |
| `setting` | No | Campaign or world this nameset belongs to. Filterable via `--setting`. |
| `tags` | No | Array of strings for cross-namespace CLI filtering (`--tag`). |
| `hidden` | No | If `true`, omitted from default `list` output. See [Hidden Flag](#hidden-flag). |
| `extends` | No | Bare or qualified ID of a parent nameset to inherit from. See [Inheritance](#inheritance-extends). |
| `design` | No | Structured documentation block. See [Design Block](#design-block). |
| `genderWeights` | No | Map of gender keys to relative weights. Defaults to `{"male": 50, "female": 50}`. |
| `formats` | No | Map of named format variants. See [Format Strings](#format-strings). |
| `format` | No | Legacy single format string. Internally promoted to `formats.default`. |
| `nameCategories` | Sometimes | Required for simple namesets. Map of category name to list of entries. |
| `nameGroups` | Sometimes | Required for grouped namesets. Map of group name to `{weight, firstNames, lastNames}`. |
| `type` | Sometimes | `"aggregate"` for aggregates. Omitted for simple/grouped (detected by structure). |
| `sources` | Sometimes | Required for aggregates. See [Aggregate Composition](#aggregate-composition). |
| `slots` | No | Per-slot policies on aggregates. See [Aggregate Composition](#aggregate-composition). |

### `genderWeights`

Controls the gender distribution. Any keys are allowed — not just `male`/`female`:

```json
"genderWeights": {"male": 40, "female": 40, "neuter": 20}
```

```json
"genderWeights": {"military": 60, "civilian": 30, "prototype": 10}
```

When a gender is selected (rolled or via `--gender`), it cascades across **all** categories. An entry tagged `"unisex"` or with no `gender` field matches any gender. Per-placeholder overrides (`{firstName:male}`) bypass the cascade for one slot.

### `formats` map

Replaces the single `format` string. `default` is required (or supplied by promoting a legacy `format` field). Each value is one of:

```json
"formats": {
  "default": "{firstName} {lastName}",
  "naval": {
    "template": "{rank} {lastName}",
    "when": "Aboard ship or in formal naval correspondence."
  }
}
```

- Shorthand: a string is treated as `{template: "<string>"}`.
- Object form: `{template, when}` — the `when` field documents context for human/LLM use and is surfaced by `--format ?` and `--explain`.

Pick a variant with `--format <name>`. Run `--format ?` to see all variants and their `when` hints.

> **Do not** put a `_comment` key inside the `formats` map itself — the loader iterates it and would parse the comment as a malformed format. Comment about a specific format on a sibling `_comment_<formatname>` key at the nameset level.

### `nameCategories`

Map of category name (any string) to a list of entries:

```json
"nameCategories": {
  "firstName": [
    {"name": "Tessa", "gender": "female", "frequency": 8, "tags": ["common", "valdric"]},
    {"name": "Bram",  "gender": "male",   "frequency": 8, "tags": ["common", "valdric"]}
  ],
  "lastName": [
    {"name": "Netmender", "tags": ["trade"]}
  ]
}
```

Per-entry fields:

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | The name string. |
| `gender` | No | Any string. Cascade-aware. Omit (or use `unisex`) for gender-neutral. |
| `frequency` | No | Relative weight (default `1`). Higher = more likely. |
| `tags` | No | Flat array of strings. Filterable via `--filter`. |

Categories may also have child variants in extends children — see [Inheritance](#inheritance-extends).

> **Do not** put `_comment` keys inside `nameCategories` itself. The loader would treat them as malformed categories. Put per-category documentation on a sibling `_comment_<categoryname>` key at the nameset level.

### `nameGroups` (grouped namesets)

Map of group name to `{weight, firstNames, lastNames}`:

```json
"nameGroups": {
  "stag-tribe": {
    "weight": 50,
    "firstNames": [{"name": "Aelin", "gender": "female"}],
    "lastNames":  [{"name": "Stag"}]
  }
}
```

`_comment` keys *inside* a group dict (not the `nameGroups` map itself) are unknown keys and ignored — useful for per-group documentation.

### Aggregate `sources`

Each source describes one feeder nameset:

```json
"sources": [
  {
    "nameset": "east-asian-evolved",
    "weight": 30,
    "label": "east-asian"
  },
  {
    "nameset": "core:russian",
    "weight": 15,
    "label": "russian-military",
    "override": {
      "genderWeights": {"male": 70, "female": 30},
      "filter": ["military"]
    }
  }
]
```

| Field | Required | Description |
|-------|----------|-------------|
| `nameset` | Yes | Bare or qualified ID. Cross-namespace permitted. |
| `weight` | No | Relative selection weight (default `1`). |
| `label` | No | Display label for `--show-group` and `--explain`. |
| `override.genderWeights` | No | Per-source gender bias. |
| `override.filter` | No | Per-entry tag filter. AND semantics (entries must match ALL tags). |
| `override.format` | No | Force a named format on the source (rarely needed; aggregate format usually wins). |

### Aggregate `slots`

Per-slot policies governing which source supplies each format placeholder:

```json
"slots": {
  "firstName": {"policy": "inherit"},
  "lastName":  {"policy": "mix", "rate": 0.3},
  "middleName": {"policy": "independent"},
  "rank": {"policy": "forced", "nameset": "core:naval-ranks"}
}
```

| Policy | Behavior |
|--------|----------|
| `inherit` | Use the same source as the anchor slot. Default for non-anchor slots. Coherent names. |
| `independent` | Roll fresh from sources for this slot, ignoring the anchor. Cross-mix every time. |
| `mix` (with `rate: N`) | N (0.0–1.0) probability of `independent`, otherwise `inherit`. Diaspora rate. |
| `forced` (with `nameset: "..."`) | Always pull this slot from the named nameset. Useful for cross-cutting axes (titles, ranks). |
| `pool` (with `sources: [...]`, optional `rate: N`) | N (default 1.0) probability of drawing from the slot's **own** weighted source list, otherwise `inherit`. Pool sources are never anchor-eligible, so a surname-only leaf can feed one slot safely. |

The first slot in the format string is the **anchor** — it always rolls fresh from `sources`.

### `extends`

```json
{
  "id": "gladiators-noble",
  "extends": "gladiators",
  ...
}
```

Bare or qualified ID. See [Inheritance](#inheritance-extends).

### `design`

```json
"design": {
  "phonology": "...",
  "etymology": "...",
  "structure": "...",
  "convention": "..."
}
```

Optional structured documentation. Not consumed by generation. See [Design Block](#design-block).

---

## Format Strings

Format strings define how categories combine into a final name. They appear as values in the `formats` map (or as the legacy `format` string).

### Basic placeholders

```json
"formats": {"default": "{firstName} {lastName}"}
// "Marcus Chen"
```

A `{categoryName}` placeholder draws one entry from `nameCategories.categoryName`. Custom categories are encouraged — `{epithet}`, `{clan}`, `{patronymic}`, `{rank}`, `{origin}`, etc.

### Per-placeholder gender override

Force a specific gender for an individual placeholder using `{category:gender}`:

```json
"formats": {"default": "{firstName} {firstName:male}sson"}
// Female roll: "Freya Bjornsson" — child female, patronym base male
```

Essential for patronymic/matronymic systems where the parent name must be a different gender than the child:

```json
"formats": {
  "default": "{firstName} {firstName:male}sson {firstName:female}sdottir"
}
// "Thorin Grimsson Hildisdottir" — child, father, mother
```

The override is per-placeholder; the cascade still applies to other slots.

### Random patterns

Generate procedural numbers and character patterns for designations, serial numbers, ship registries.

**Numeric ranges** — random integer (inclusive):

```json
"formats": {"default": "{prefix}-{random:1-999}"}
// "XR-742"
```

**Character patterns** — each pattern character emits a random value:

| Pattern | Generates | Example |
|---------|-----------|---------|
| `A` | Uppercase letter (A–Z) | `AAA` → `KMZ` |
| `a` | Lowercase letter (a–z) | `aaa` → `qxm` |
| `0` | Digit (0–9) | `000` → `847` |
| `X` | Hex digit (0–9, A–F) | `XXXX` → `3A7F` |
| Any other | Literal (preserved) | `A-0` → `K-7` |

Examples:

```json
"formats": {"default": "{prefix}-{random:0000}"}
// "MK-4728"

"formats": {"default": "{random:AAA}-{random:000}"}
// "KMZ-847"

"formats": {"default": "0x{random:XXXXXXXX}"}
// "0x3A7F9C2E"

"formats": {"default": "{random:AA-000-aa}"}
// "KM-742-qx"
```

### Optional sections

Wrap content in square brackets to make it conditional on its placeholders resolving:

```json
"formats": {"default": "{firstName}[ {epithet}] {lastName}"}
// With epithet:    "Marcus the Brave Chen"
// Without epithet: "Marcus Chen"
```

Add a percentage weight to control inclusion probability when the content is available:

```json
"formats": {"default": "{firstName}[ {epithet}:30%] {lastName}"}
// 30% of the time: "Marcus the Brave Chen"
// 70% of the time: "Marcus Chen"
```

Without a weight, optional sections are included whenever their content resolves (effectively 100%).

A section is dropped **whole** if any placeholder inside it fails to resolve — literals included. So `{firstName}[ af {station}]` renders as just the given name when there is no station, never as `"Regina af"`. This is the right way to attach particles, honorifics and connectives to a category that some sources lack. Optional sections work identically in aggregates: a slot that resolves to a source without the category drops the section.

Nested optionals work:

```json
"formats": {"default": "{firstName}[{title}[ {epithet}]] {lastName}"}
// All three resolve: "Marcus Lord the Wise Chen"
// Only title:        "Marcus Lord Chen"
// Neither:           "Marcus Chen"
```

### Variable-depth chains

Syntax `{...}*N-M` repeats the bracketed group a random number of times between N and M (inclusive).

```
"{firstName}{ ek-{firstName}}*0-3"
```

Each repetition rolls fresh placeholders. Useful for lineage chains, ancestor-recital formats, and multi-generation patronymics.

> **Important gotcha.** Inside the chain group, **a single brace pair is a literal, not a placeholder**. To repeat a placeholder, double the braces.
>
> `{foo}*1-3` repeats the literal text `foo`.
> `{{foo}}*1-3` repeats the placeholder `{foo}`.

Examples:

```json
// Arakessi maternal lineage (0–3 ancestors), each rolling a fresh firstName
"formats": {"lineage": "{firstName}{, {firstName} tessek}*0-3"}
// "Sora, Tessa tessek, Mira tessek"

// Dwarven multi-generation patronymic, rolling male names for ancestors
"formats": {"lineage": "{firstName}{ {firstName:male}sson}*1-2"}
// "Thorin Grimsson Borinsson"
```

---

## Aggregate Composition

Aggregates compose names from multiple source namesets with weighted selection. The aggregate supplies the **format**; each source supplies the **slot values**.

### Simple aggregate

```json
{
  "namespace": "longwatch",
  "id": "core-worlds",
  "type": "aggregate",
  "genderWeights": {"male": 50, "female": 50},
  "formats": {"default": "{firstName} {lastName}"},
  "sources": [
    {"nameset": "east-asian-evolved", "weight": 30, "label": "east-asian"},
    {"nameset": "slavic-evolved",     "weight": 25, "label": "slavic"},
    {"nameset": "core:russian",       "weight": 15, "label": "russian"}
  ]
}
```

There are **two aggregate modes**, selected by whether the aggregate declares a `slots` map:

**Source-picking mode (no `slots`)** — the default. Used for composing *different naming styles*:

1. Tool picks one source by weight.
2. Generates the **entire name from that source**, using **the source's own format and categories**.
3. The aggregate's `format`/`formats` is *not* applied — each source renders in its own structural style.

This is the mode to use when your sources are structurally different (single-word vs `{title} {name} of {x} and {y}` vs CamelCase handle): each leaf keeps its own format, and the aggregate just weights between them. (When the aggregate is asked for a non-`default` format name via `--format X`, that name is passed down and the source renders with *its* `formats.X`, falling back to its `formats.default`.)

**Slot-aware mode (has `slots`)** — used for *diaspora mixing* within one shared structure:

1. Tool picks a source by weight (the **anchor** source).
2. For each format slot, applies the slot policy (default `inherit` for non-anchor slots) to pick a source.
3. Generates the slot value from that source's categories.
4. Combines using **the aggregate's** format. (Here, and only here, the sources' own formats are bypassed — sources supply slot *values*, not structure.)

`--group <label>` forces a specific source (source-picking) or anchor source (slot-aware).
`--show-group` prints the source/anchor label alongside the result.

### Per-source overrides

Each source may carry an `override` block:

```json
{
  "nameset": "core:russian",
  "weight": 15,
  "label": "russian-military",
  "override": {
    "genderWeights": {"male": 70, "female": 30},
    "filter": ["military"]
  }
}
```

- `genderWeights` — biases the gender roll when this source is selected.
- `filter` — list of per-entry tags; only entries matching ALL listed tags participate. Lets a single base nameset feed multiple aggregates with different sociological tiers (`patrician` vs `street`).
- `format` — forces a specific named format on the source itself (rarely needed since the aggregate's format normally wins).

### Slot policies

The `slots` map controls per-slot source selection:

```json
"slots": {
  "firstName": {"policy": "inherit"},
  "lastName":  {"policy": "mix", "rate": 0.3},
  "middleName": {"policy": "independent"},
  "rank":      {"policy": "forced", "nameset": "core:naval-ranks"}
}
```

| Policy | Behavior | Use case |
|--------|----------|----------|
| `inherit` | Match the anchor's source. | Coherent names ("Yuki Tanaka") — default for non-anchor slots. |
| `independent` | Roll fresh from `sources` for this slot. | Always cross-mix this slot. |
| `mix` (`rate: N`) | N probability of independent, else inherit. | Diaspora-rate naming (e.g. "Sanskrit first + Scarrow last 30% of the time"). |
| `forced` (`nameset: "..."`) | Always pull from the named nameset. | Cross-cutting axes — titles, ranks, honorifics shared across all sources. |
| `pool` (`sources: [...]`, `rate: N`) | With probability N (default 1.0) draw from the slot's own weighted source list; else inherit the anchor. | One slot mixing at a different rate than another (surnames 30% foreign, given names 0%); feeding a slot from a leaf that has *only* that category. |

The first slot mentioned in the active format string is the **anchor**. It always rolls fresh from `sources`; setting an explicit policy on it is a no-op.

### Pool slots

`mix` re-rolls among the aggregate's top-level `sources`, so every source has to be able to supply *every* slot — a source that lacks `firstName` would, when it lands as anchor, yield a name with no given name. `pool` gives one slot a private source list instead:

```json
"sources": [
  {"nameset": "swedish-parish", "weight": 60, "label": "swedish"},
  {"nameset": "finnish-parish", "weight": 40, "label": "finnish"}
],
"slots": {
  "lastName": {
    "policy": "pool",
    "rate": 0.3,
    "sources": [
      {"nameset": "line-surnames",  "weight": 2, "label": "line"},
      {"nameset": "names-arabic",   "weight": 5, "label": "diaspora", "override": {"filter": ["common"]}}
    ]
  }
}
```

- The anchor still comes from `sources` and supplies the given name (and, via `inherit`, any other slot not listed).
- With probability `rate` the slot draws from its pool by weight; otherwise it inherits the anchor, so `rate` reads as "fraction of this slot that is *not* the anchor's own." Default `rate` is `1.0` (always pool).
- Pool entries take the same fields as top-level sources (`nameset`, `weight`, `label`, `override.filter`); the filter applies to this slot only, which is the clean way to say "soldier-tagged surnames but any given name."
- Pool sources are never anchor-eligible, so a hidden leaf holding only `lastName` is a valid pool source.
- `validate` errors on unresolvable pool refs and warns when a pool source has no entries for the slot's category (a silent fall-back-to-anchor otherwise).
- `--explain` shows the pool pick as `pool:<label>`.

### Nested aggregates

A source may itself be an aggregate. Generation recurses: pick top-level source → if aggregate, pick sub-source → eventually hit a leaf → generate.

```json
"sources": [
  {"nameset": "east-asian-evolved", "weight": 30},
  {"nameset": "frontier-aggregate", "weight": 25}
]
```

Here `frontier-aggregate` could itself contain three or four sources, enabling hierarchical demographic models (a "Core Worlds" aggregate sourcing from a "Frontier" aggregate sourcing from individual planet namesets).

### Cross-namespace source references

Source `nameset` accepts both:

- **Bare** (`east-asian-evolved`) — resolves within current namespace, then root.
- **Qualified** (`core:russian`) — exact lookup.

A campaign aggregate can freely pull from `core:` defaults, other campaigns' shared namespaces, or any reachable namespace.

### Graceful degradation

If a source nameset is missing at generation time, the tool warns and skips it (the effective weight pool shrinks). Generation continues. `validate` flags missing sources as errors so you catch them up front.

### Format variants on aggregates

`--format naval` selects the aggregate's `formats.naval` template. **This applies only in slot-aware mode** (an aggregate with a `slots` map): slots in the variant pull values from sources per the slot policies, and the sources' own formats are bypassed. In source-picking mode (no `slots`), the aggregate has no governing format of its own — the `--format` name is passed *down* to the chosen source, which renders with its own `formats.<name>` (falling back to its `formats.default`). See [the two aggregate modes](#simple-aggregate).

---

## Inheritance (extends)

A nameset may extend another, inheriting everything (categories, formats, design, tags, gender weights, hidden flag) and then applying overrides.

```json
{
  "namespace": "kemic",
  "id": "gladiators-noble",
  "extends": "gladiators",
  "name": "Kemic Gladiators (noble-blood)",
  "tags": ["arena", "patrician", "human"],
  "hidden": false,

  "formats": {
    "default": "{title} {firstName} of {lastName}"
  },

  "nameCategories": {
    "firstName": {
      "add": [
        {"name": "Aurelian", "gender": "male", "tags": ["patrician"]}
      ],
      "remove": ["Drax", "Tarn"]
    },
    "title": [
      {"name": "Lord", "gender": "male"},
      {"name": "Lady", "gender": "female"}
    ]
  }
}
```

### Resolution rules

- **Top-level fields** (`formats`, `design`, `tags`, `genderWeights`, `setting`, etc.) **replace** the parent's value entirely when present in the child. To preserve parent tags, list them all again.
- **Per-category** under `nameCategories`:
  - A list value **replaces** that category outright.
  - An `{add: [...], remove: [...]}` object surgically modifies the parent category. `add` appends entries; `remove` strips by name string.
- **Hidden flag** inherits but the child can flip it.
- `extends` accepts bare or qualified IDs (`extends: "core:russian"`).

### Multi-level chains

A → B → C is supported. Resolution merges right-to-left (deepest parent first), then each descendant in turn.

### Cycles and constraints

- No circular extends. `validate` flags cycles.
- Aggregates and leaf namesets cannot extend each other (different schemas). Aggregates extending aggregates and leaves extending leaves both work.

### Why not just copy-paste?

Copy-paste invites drift — fix a typo in the parent and the child doesn't get it. Inheritance keeps the parent canonical.

### Why not aggregate-with-overrides?

Per-source overrides only affect *how an aggregate uses* a source. Inheritance creates a *new nameset* that other constructs (aggregates, further extends children) can reference. Different concept, often complementary.

---

## Per-Entry Tags & Filtering

Per-entry `tags` are flat string arrays for filterable axes within a nameset — class, role, phonetic profile, social stratum, etc.

```json
"firstName": [
  {"name": "Marcus",  "gender": "male",   "tags": ["patrician", "imperial"]},
  {"name": "Iulius",  "gender": "male",   "tags": ["patrician"]},
  {"name": "Lucius",  "gender": "male",   "tags": ["plebeian"]},
  {"name": "Sulpicia","gender": "female", "tags": ["patrician"]}
]
```

### `--filter` on the CLI

```bash
python scripts/namegen.py full --nameset romans --filter patrician
```

Repeat for AND semantics (entries must have ALL listed tags):

```bash
python scripts/namegen.py full --nameset romans --filter patrician --filter imperial
# Only "Marcus" qualifies in the example above
```

### Filtering inside aggregates

Apply at the source level via `override.filter`:

```json
{
  "nameset": "core:russian",
  "weight": 15,
  "override": {"filter": ["military"]}
}
```

The aggregate then pulls only `military`-tagged entries from `core:russian` for that source slot. Lets a single base nameset (`core:russian`) feed multiple aggregates with different sociological tiers.

### Tags vs gender

Gender remains a typed first-class field with cascade semantics, default rolling, and per-placeholder override syntax (`{firstName:female}`). Tags are *additional* axes — use them for everything that isn't gender.

---

## Design Block

The `design` block is structured optional documentation. The tool does **not** use it for generation. It's surfaced by `validate`, `list --verbose`, and `--explain` for human and LLM consumers — replacing the old habit of stuffing rules into long `description` fields.

```json
"design": {
  "phonology": "Hard consonants (k, t, r), short vowels. Avoids dipthongs.",
  "etymology": "First names contracted from old Valdric trade-cant; surnames from trades, ports of origin, or distinguishing marks.",
  "structure": "Given + occupational/locational byname. No middle names.",
  "convention": "Spoken given-first in casual settings, surname-first when reporting to harbor authorities."
}
```

All subfields optional. Conventional subfields:

| Subfield | Use |
|----------|-----|
| `phonology` | Sound profile — consonants, vowels, syllable shape. |
| `etymology` | Where names come from — roots, languages, traditions. |
| `structure` | Slot shape — given+family, given+patronymic+family, single-name, etc. |
| `convention` | Social rules — how names are spoken, when shortened, taboo names. |

You may add your own subfields; the tool surfaces all of them verbatim.

---

## Hidden Flag

```json
"hidden": true
```

Boolean. Marks a nameset as "exists as an aggregate base only — don't show me in `list` by default." Override with `list --all`.

Typical use: an `evolved-substrates` namespace where every member is hidden, plus a few visible aggregates that compose them. `list` stays clean; the aggregates are what users typically reach for.

---

## Validate Command

```bash
python scripts/namegen.py validate
```

Lints all loaded namesets and reports errors and warnings:

```
✗ longwatch:core-worlds — source 'frontier-aggregate' has circular reference to self
✗ emberfall:arakessi — format 'formal' references undefined category {tessek}
⚠ longwatch:void-born — namespace 'longwatch' not previously seen (typo? new?)
⚠ rust-and-ruin:askvargr — uses legacy format string, suggest migration
✓ 47 namesets validated, 2 errors, 2 warnings
```

Checks performed:

- Broken aggregate refs — referenced source nameset doesn't exist.
- Circular `extends` chains.
- Undefined format placeholders — `{foo}` references an undefined category.
- Namespace typos (fuzzy match against known namespaces).
- Legacy single-`format` usage — flagged as a migration nudge.

Errors block silent runtime failures; warnings are advisory. Run before bundling, after large nameset edits, and in CI for shared catalogs.

---

## The --explain Flag

Append `--explain` to a `full` command to dump an assembly trace to stderr alongside the generated name:

```
$ python scripts/namegen.py full --nameset longwatch:core-worlds --explain
Nameset: longwatch:core-worlds (aggregate)
Format: default → "{firstName} {lastName}"
Anchor source pick: east-asian-evolved (weight 30/100)
Slot firstName: inherit → east-asian-evolved → "Mei-Lin"
Slot lastName: mix(0.3) → rolled inherit → east-asian-evolved → "Tanaka"
Result: Mei-Lin Tanaka
```

Invaluable for debugging weird aggregate compositions — surfaces which source the anchor picked, which slot policy fired, which source supplied each slot value, and which format variant was used.

---

## Migration from v1

All v1 namesets keep working without modification. Migrate piecemeal, when you actually want the v2 features:

### 1. Add `namespace`

Move from filename convention to a first-class field. Pick from the [recommended taxonomy](#recommended-namespace-taxonomy):

```json
// Before
{"id": "harbor-folk", ...}

// After
{"namespace": "valdran", "id": "harbor-folk", ...}
```

Aggregates and `extends` references update from bare `harbor-folk` to qualified `valdran:harbor-folk` *only if you need to reach across namespaces*. Bare references still resolve within the current namespace.

### 2. Convert `format` to `formats.default`

Only if you want named variants. The legacy `format` string still works.

```json
// Before
"format": "{firstName} {lastName}"

// After
"formats": {
  "default": "{firstName} {lastName}",
  "formal": {
    "template": "{title} {firstName} {lastName} of {origin}",
    "when": "Court business, harbor council."
  }
}
```

### 3. Promote stuffed-into-description metadata into `design`

Long descriptions like "names use hard consonants, two syllables, surname is occupational" become structured:

```json
"design": {
  "phonology": "Hard consonants (k, t, r), short vowels.",
  "structure": "Given + occupational byname.",
  "convention": "Surname-first when reporting to harbor authorities."
}
```

### 4. Add per-entry `tags`

Wherever you've wanted to filter — class, region, sub-population, phonetic profile:

```json
"firstName": [
  {"name": "Marcus", "gender": "male", "tags": ["patrician"]},
  {"name": "Lucius", "gender": "male", "tags": ["plebeian"]}
]
```

Then `--filter patrician` on the CLI, or `override.filter: ["patrician"]` from an aggregate source.

### 5. Mark base namesets `hidden: true`

If a nameset exists only to feed aggregates and shouldn't clutter `list`:

```json
"hidden": true
```

### 6. Replace parallel aggregates with extends

If you maintain four parallel aggregates (`patrician`, `street`, `arena`, `ludus`) drawing from the same eight sources just to express social class, collapse them: keep one base aggregate, then extend it for each variant — or use `override.filter` on a single aggregate that takes a `--filter` axis at runtime.

### 7. Run `validate` for nudges

After migration, run `python scripts/namegen.py validate` to catch broken refs, undefined placeholders, and remaining legacy `format` usages.

---

## Templates

Working templates with heavy inline documentation live under `references/templates/`:

| Template | What it demonstrates |
|----------|----------------------|
| `simple.json` | Minimal leaf nameset — namespace, design block, multiple format variants (including a variable-depth chain), arbitrary genders, per-entry tags. |
| `aggregate.json` | Aggregate with cross-namespace source, nested aggregate source, per-source override (gender + filter), all four slot policies. |
| `grouped.json` | Multi-group nameset — three tribes sharing structure, different rosters. |
| `multi-nameset.json` | Multiple namesets in one file — file-level namespace, per-item namespace override, sibling extending sibling. |
| `extends.json` | Inheritance — parent + child + grandchild, `add`/`remove` on categories, full `formats` replacement. |

Copy a template into your campaign's `namesets/` directory and adapt. The `_comment` and `_comment_<field>` keys in the templates are unknown-key documentation and ignored by the loader; strip or keep them as you prefer.

---

## Backwards Compatibility

All v1 namesets work unchanged. Every v2 capability is opt-in, signaled by the presence of new fields:

- No `namespace` → namespace is `""` (root). Bare-ID resolution still works.
- No `formats` → existing `format` becomes `formats.default` internally.
- No `tags` on entries → entries match all tag filters trivially.
- No `extends` / `slots` / `override` → behaves exactly as v1.
- Legacy `firstNames`/`lastNames` arrays still convert to `nameCategories` automatically.

You can mix v1 and v2 namesets freely in the same campaign. Migrate at your own pace, only when a v2 feature is worth it.
