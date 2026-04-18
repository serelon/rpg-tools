# Namegen v2 - Design Document

> **Design brainstorm completed 2026-04-18**

## Problem Statement

The current namegen tool serves well for simple cases but the campaigns under `../solorpg/` reveal recurring workarounds, redundant data, and missing capabilities:

- **Slot-level mixing is impossible** — Solramis, gladiator-ludus, and Long Watch all want diaspora-style names (e.g. Sanskrit first + Scarrow last) but must generate from individual sources and splice manually.
- **Filtering by sub-population is missing** — Blood & Spectacle maintains four parallel aggregates (patrician, street, arena, ludus) drawing from the same eight sources just to express social class.
- **Multiple naming structures per nameset are unsupported** — Valentina has ~4 address modes (naval, formal, intimate, full); Iset has birth name + stage name. The guide hints at `formatFormal`/`formatShort` but the tool ignores them.
- **Cultural/phonological metadata is hidden in description fields** — Arakessi uses a `design` block (phonology, roots, length, naming_convention, cultural_notes); Deep Drift documents intent in build scripts. No formal schema for this knowledge.
- **No namespacing** — names will collide as the catalog grows (`metropolitan:english` vs `medieval:english`).
- **Aggregates can't nest** — silently broken; would enable hierarchical demographic models.
- **List dumps every nameset including aggregate-only base namesets** — the user usually wants the aggregates.
- **No filesystem flexibility** — one nameset per file, period. Splitting/monolithing not supported.
- **No validation tooling** — broken aggregate refs, undefined format placeholders, etc. are runtime surprises.

## Goals

1. Absorb all the workarounds the campaigns are doing manually
2. Enable hierarchical and slot-mixed aggregate composition
3. Formalize cultural/phonological metadata as first-class schema
4. Introduce namespaces to preempt name collisions as the catalog grows
5. Allow flexible file layout (one nameset per file, N per file, monolith — same internal model)
6. Improve list/discovery UX without making simple cases noisier
7. Add validation and explain tooling
8. Maintain full backward compatibility — all v1 namesets keep working unchanged

## Non-Goals

- **Conditional sources** with arbitrary "if X then Y" rules — slot policies + cross-mix probability cover the realistic use cases.
- **Reverse lookup** ("what nameset would this name come from?") — interesting but no demand.
- **Cross-campaign nameset sharing infrastructure** — campaigns stay orthogonal; campaign-id namespacing is enough.
- **Scaffold/generator command** — templates + good documentation cover the same ground for an LLM-assisted workflow.
- **Phonetic *generation*** — only phonetic *tagging* and filtering. Generating names that match a phonetic profile is research-grade.

## Architecture Overview

Two tiers of change, packaged together but ship-able in stages within a feature branch.

### Tier 1 — Data Model Overhaul (interlocking)

Foundational changes to the schema and core resolution logic. All v1 features remain functional; new features are opt-in.

1. **Namespaces** — full IDs become `namespace:id`. Reserved prefixes: `core:`, `<campaign-id>:`. Free-form rest with documented conventions (era, cultural stratum, genre, species, setting).
2. **Multi-nameset files** — a JSON file may contain one nameset (current) or many under a top-level `namesets` array.
3. **Formalized `design` block** — structured optional documentation (phonology, etymology, structure, convention).
4. **Hidden flag** — `"hidden": true` on aggregate-only base namesets so they don't clutter `list`.
5. **Per-entry `tags` array** — flat string array for filterable axes (class, role, phonetic, etc.). Gender stays as a typed first-class field with cascade semantics.
6. **Named format variants** — `formats` map replaces single `format`; each entry can be a template string or `{template, when}` object documenting context.
7. **Variable-depth chains** — `{...}*N-M` repeating-group syntax for lineage chains.
8. **Inheritance / extends** — namesets can extend other namesets, with category `add`/`remove` and full top-level field overrides.
9. **Aggregate v2** — nested aggregates, per-source overrides, slot policies (inherit/independent/mix/forced), source filtering, graceful degradation.

### Tier 2 — UX Surface (independent additions)

Improvements to the CLI; can land independently after Tier 1 stabilizes.

1. **`list` overhaul** — briefer by default, hides `hidden` namesets, groups by namespace; `--all`, `--verbose`, `--namespace`, `--tag`, `--setting`, `--type` filters.
2. **`full` filtering** — `--filter <tag>` (repeatable, AND semantics) for per-entry filtering within a chosen nameset.
3. **`--format <variant>`** — picks a named format. `--format ?` lists available with `when` hints.
4. **`validate` command** — lints aggregate refs, circular extends, undefined format placeholders, namespace typos (fuzzy), legacy format usage.
5. **`--explain` flag** — dumps assembly trace (which source picked, which slot policy fired, which format variant).

### What stays unchanged

- Three nameset types: simple, aggregate, grouped.
- Frequency weighting, gender cascade, optional sections, random patterns.
- Discovery model (search 7 paths, merge).
- Standard library only — no new dependencies.

---

## Section 1 — File & Namespace Model

### Multi-nameset files

A `.json` file may contain a single nameset (current behavior, unchanged) or many. Detection by structure:

```json
// Single nameset (v1, still works)
{"id": "names-russian", "nameCategories": {...}}

// Multiple namesets (new)
{
  "namespace": "metropolitan",
  "namesets": [
    {"id": "russian", "nameCategories": {...}},
    {"id": "polish", "nameCategories": {...}},
    {"id": "german", "nameCategories": {...}}
  ]
}
```

The discovery layer flattens both forms into the same internal `custom_namesets` dict, keyed by full `namespace:id`. Loose-file pattern (`*-names.json`) still works.

### Namespaces

Full ID is `namespace:id` (single colon, two segments — never deeper).

Three ways to set the namespace:

1. **File-level** — `"namespace": "metropolitan"` at the top of a multi-nameset file applies to all contained namesets.
2. **Per-nameset** — `"namespace": "medieval"` on an individual nameset (overrides file-level).
3. **Default** — no declaration → namespace is `""` (root). All current v1 namesets land here. Backward compatible.

### Reference resolution

When a nameset references another (in aggregate sources, `extends`, etc.):

- **Bare ID** `"english"` — resolve within the *current* namespace first, then root (`""`).
- **Qualified ID** `"metropolitan:english"` — exact lookup.
- **Cross-namespace works fine** — `medieval` aggregate can reference `metropolitan:russian`.

### Hidden flag

`"hidden": true` on a nameset means "exists as an aggregate base only — don't show me in `list` by default." Override with `--all`. Combined with namespaces, this enables clean organization (e.g. an `evolved-substrates` namespace where every member is hidden, plus a few visible aggregates that compose them).

### Conflict handling

If two files declare the same `namespace:id`, last-loaded wins (matches current discovery merge behavior). `validate` flags duplicates.

### Recommended namespace taxonomy

| Kind | Example namespaces | Use for |
|------|-------------------|---------|
| **Reserved: built-in** | `core` | Bundled defaults shipped in `tools/data/namesets/` |
| **Reserved: campaign** | `aegis`, `emberfall`, `threadlight` | Campaign-specific (matches campaign folder name) |
| Era | `medieval`, `1940s`, `victorian`, `bronze-age`, `ancient` | Real-world historical |
| Cultural stratum | `metropolitan`, `frontier`, `imperial`, `nomadic` | Class/society axis |
| Genre | `fantasy`, `scifi`, `cyberpunk`, `weird`, `post-apoc` | Setting type |
| Species | `elven`, `dwarven`, `goblinoid`, `lizardfolk` | Non-human, cross-setting |
| Setting | `valdran`, `caldworth`, `solramis` | Specific worlds (when shared across campaigns) |

**Rule of thumb**: a nameset goes in the *most specific namespace that still allows reuse*.

**One namespace per nameset.** Tags handle cross-cutting axes (a nameset has `tags: ["historical", "1940s", "human"]` regardless of its namespace).

---

## Section 2 — Nameset Schema

The full v2 leaf-nameset schema, with all new fields:

```json
{
  "namespace": "longwatch",
  "id": "void-born",
  "name": "Void-Born",
  "description": "...",
  "setting": "The Long Watch",
  "tags": ["spacefaring", "novel", "human"],
  "hidden": true,

  "design": {
    "phonology": "Resonant vowel-rich forms...",
    "etymology": "Crèche-line and ship-bloodline derivations...",
    "structure": "2-3 syllables, open endings dominant",
    "convention": "Single given + family. No patronymics."
  },

  "genderWeights": {"male": 50, "female": 50},

  "formats": {
    "default": "{firstName} {lastName}",
    "formal": {
      "template": "{title} {firstName} {middle} {lastName}",
      "when": "Court, official documents, formal introductions"
    },
    "naval": {
      "template": "{rank} {lastName}",
      "when": "Aboard ship or in naval service"
    },
    "intimate": {
      "template": "{nickname}",
      "when": "Close friends, family"
    }
  },

  "nameCategories": {
    "firstName": [
      {"name": "Sorin", "gender": "male", "tags": ["flowing"]},
      {"name": "Tessik", "gender": "female", "tags": ["hard-crisp"]}
    ],
    "lastName": [...]
  }
}
```

### `design` block

All subfields optional. The tool doesn't *use* this block for generation — it's structured documentation surfaced by `validate`, `list --verbose`, and `--explain`. Replaces the current pattern of stuffing rules into long `description` fields or comment-fields like `_doc`.

### `tags` (nameset-level)

Flat array of strings for cross-namespace filtering on the CLI (`--tag historical`, `--tag human`). Independent of namespace and per-entry tags.

### `hidden`

Boolean. See Section 1.

### `formats` map

Replaces the single `format` string. Always has `default`. Each value is one of:

- A template string (shorthand): `"naval": "{rank} {lastName}"`
- An object: `{"template": "...", "when": "..."}` — the `when` field documents context for human/LLM use.

Generated with `--format <name>`. Old single `format` field still parses as `formats.default` internally.

### Per-entry `tags`

Flat array of strings. Filterable via `--filter <tag>` (repeatable, AND semantics). Used for class/role/phonetic/social-stratum/etc. distinctions within a single nameset.

```json
{"name": "Marcus", "gender": "male", "tags": ["patrician", "imperial"]}
```

Gender stays as the typed first-class field with cascade semantics, default rolling, and per-placeholder override syntax (`{firstName:female}`).

### Variable-depth chains

Syntax: `{...}*N-M` — the bracketed group repeats randomly N to M times.

Example for Arakessi maternal lineage (0-3 ancestors):

```
"{firstName}{, {firstName} tessek}*0-3"
```

Example for dwarven multi-generation patronymic (1-2 generations):

```
"{firstName}{ {firstName:male}sson}*1-2"
```

Inner content uses placeholders normally and may include literals.

---

## Section 3 — Aggregate Model

The full v2 aggregate schema:

```json
{
  "namespace": "longwatch",
  "id": "core-worlds",
  "type": "aggregate",
  "genderWeights": {"male": 50, "female": 50},
  "formats": {
    "default": "{firstName} {lastName}"
  },
  "sources": [
    {"nameset": "east-asian-evolved", "weight": 30, "label": "east-asian"},
    {"nameset": "slavic-evolved", "weight": 25, "label": "slavic"},
    {
      "nameset": "core:russian",
      "weight": 15,
      "label": "russian",
      "override": {
        "genderWeights": {"male": 70, "female": 30},
        "filter": ["military"]
      }
    },
    {"nameset": "frontier-aggregate", "weight": 10, "label": "frontier"}
  ],
  "slots": {
    "firstName": {"policy": "inherit"},
    "lastName": {"policy": "mix", "rate": 0.3}
  }
}
```

### Five new aggregate capabilities

#### 1. Nested aggregates

A source may itself be an aggregate (note `frontier-aggregate` in the example). Generation recurses: pick top-level source → if aggregate, pick sub-source → eventually hit a leaf → generate from it.

Currently broken in v1 (the dispatcher reads `nameCategories` directly without checking source type, producing empty names). v2 adds type dispatch and recursion.

#### 2. Per-source overrides

Optional `override` block per source. Supported overrides:

- `genderWeights` — biases gender selection for this aggregate's use of this source.
- `filter` — list of per-entry tags; only entries matching ALL listed tags participate.
- `format` — forces a specific format variant from the source (rarely needed since aggregate format usually wins).

#### 3. Slot policies

The `slots` map controls per-format-slot source selection:

| Policy | Behavior |
|--------|----------|
| `inherit` (default for non-anchor slots) | Match the anchor slot's source → coherent names |
| `independent` | Roll fresh from sources → cross-mix |
| `mix` with `rate: N` | N% chance independent, (1-N)% inherit → diaspora rate |
| `forced` with `nameset: "..."` | Always use the named source for this slot |

The first slot in the format string is the anchor (rolls fresh by default).

#### 4. Source filtering

Implemented via `override.filter`. Pulls only entries whose per-entry `tags` include ALL the listed filter tags. Enables a single base nameset to serve multiple aggregates with different sociological tiers.

#### 5. Graceful degradation

Missing source nameset → warn and skip (with reduced effective weight pool), don't crash. `validate` flags it as an error so it's caught before runtime.

### Format variants on aggregates

If you `--format naval`, the aggregate's `formats.naval` template is used. The slot picks a source; that source generates the *slot value* (e.g. picks a `firstName` from its categories). The format itself is the aggregate's — the source's own format is ignored when it's being used as an aggregate source.

### Cross-namespace references

Source `nameset` field accepts both bare IDs (`east-asian-evolved` — resolves within current namespace, then root) and qualified (`core:russian` — exact lookup).

---

## Section 4 — Inheritance / Extends

For variants like `east-asian-evolved-core` vs `east-asian-evolved-frontier` (Long Watch gap), or for a "Kemic noble" subset of the Kemic gladiator nameset.

```json
{
  "namespace": "longwatch",
  "id": "east-asian-evolved-core",
  "extends": "east-asian-evolved",
  "description": "Core-world refined variant",

  "design": {
    "convention": "More polished, court-influenced..."
  },

  "nameCategories": {
    "firstName": {
      "add": [
        {"name": "Senna-Vis", "gender": "female", "tags": ["refined"]},
        {"name": "Tessario", "gender": "male", "tags": ["refined"]}
      ],
      "remove": ["Bjarn", "Krash"]
    }
  },

  "formats": {
    "default": "{firstName} {middleName} {lastName}"
  }
}
```

### Resolution rules

- Child inherits everything from parent (categories, formats, design, tags, gender weights, hidden flag).
- Per-category `add` appends entries; `remove` strips by name string.
- Top-level fields (formats, design, tags, etc.) override fully when present in the child.
- `extends` accepts namespace-qualified IDs (`extends: "core:russian"`).

### Multi-level chains

A → B → C. C's effective state is parent-merge applied right-to-left (deepest parent first).

### Constraints

- No circular extends. `validate` flags cycles.
- Aggregates can't extend leaf namesets, and vice versa (different schemas). They *can* extend each other within type.

### Why not just copy-paste?

Copy-paste invites drift — fix a typo in the parent, child doesn't get it. Inheritance keeps the parent canonical.

### Why not aggregate-with-overrides?

Aggregate per-source overrides (Section 3) only affect *how an aggregate uses* a source. Inheritance creates a *new nameset* that other constructs can reference. Different concept.

---

## Section 5 — UX Surface (Tier 2)

Independent additions; ship after Tier 1 stabilizes.

### `list` overhaul

Briefer by default, hides `hidden: true` namesets, groups by namespace.

```
$ namegen list
core (28)
  american, russian, chinese, japanese, ...
longwatch (3 visible, 9 hidden)
  core-worlds, frontier-aggregate, imperial-nobility
emberfall (5)
  caldworth-city, arakessi, elves, dwarves, lizardfolk
```

Flags:

- `--all` — show hidden too
- `--verbose` — old-style detail (sources, groups, name counts)
- `--namespace longwatch` — filter to one namespace
- `--tag spacefaring` — filter by nameset-level tag
- `--setting "The Long Watch"` — filter by setting field
- `--type aggregate` — filter by nameset type

### `full` filtering

`--filter <tag>` (repeatable, AND semantics) filters per-entry tags within the chosen nameset.

### `--format <variant>`

Picks a named format. `--format naval` uses `formats.naval`. `--format ?` lists available formats with their `when` hints.

### `validate` command

```
$ namegen validate
✗ longwatch:core-worlds — source 'frontier-aggregate' has circular reference to self
✗ emberfall:arakessi — format 'formal' references undefined category {tessek}
⚠ longwatch:void-born — namespace 'longwatch' not previously seen (typo? new?)
⚠ rust-and-ruin:askvargr — uses legacy format string, suggest migration
✓ 47 namesets validated, 2 errors, 2 warnings
```

Checks:

- Broken aggregate refs (source nameset doesn't exist)
- Circular extends
- Undefined format placeholders (`{foo}` references undefined category)
- Undefined per-entry tag axes (when filter syntax is used)
- Namespace typos (fuzzy match against known namespaces)
- Legacy single-`format` usage (suggest migration to `formats` map)

### `--explain` flag

On `full`, dumps the assembly trace:

```
$ namegen full --nameset longwatch:core-worlds --explain
Nameset: longwatch:core-worlds (aggregate)
Format: default → "{firstName} {lastName}"
Anchor source pick: east-asian-evolved (weight 30/100)
Slot firstName: inherit → east-asian-evolved → "Mei-Lin"
Slot lastName: mix(0.3) → rolled inherit → east-asian-evolved → "Tanaka"
Result: Mei-Lin Tanaka
```

Invaluable for debugging weird aggregate compositions.

---

## Section 6 — Migration & Rollout

### Backward compatibility

All v1 namesets keep working without modification. New features are opt-in, signaled by presence of new fields:

- No `namespace` → namespace `""` (root). Bare-ID resolution still works.
- No `formats` → existing `format` becomes `formats.default` internally.
- No `tags` on entries → entry matches all tag filters trivially.
- No `extends` / `slots` / `override` → behaves as v1.
- Legacy `firstNames`/`lastNames` arrays still convert (already supported).

### Internal flattening

Discovery merges multi-nameset files into the same `custom_namesets` dict, keyed by full `namespace:id`. Single-nameset files load as before. Loose `*-names.json` files still work.

### Migration path (per nameset, when ready)

1. Add `namespace` (move from filename convention to first-class field).
2. Convert `format` string → `formats.default` (only if you want named variants).
3. Promote stuffed-into-description metadata into `design` block.
4. Add per-entry `tags` where you've wanted to filter.
5. Mark base namesets `hidden: true` if they're aggregate-only.

No forced rewrites. `namegen validate --suggest-migration` (Tier 2) gives nudges.

### Templates (replaces "scaffold")

Under `references/templates/`:

- `simple.json` — minimal leaf nameset
- `aggregate.json` — aggregate with slot policies
- `grouped.json` — multi-group nameset
- `multi-nameset.json` — file with N namesets in one
- `extends.json` — inheritance variant

Each heavily commented with the new fields, suitable to copy and adapt.

### Documentation rewrite

`references/nameset-guide.md` overhaul:

- Quick reference at top, scaling complexity downward
- New sections: namespaces, multi-nameset files, design block, format variants, chains, per-entry tags, inheritance, slot policies
- Migration appendix with before/after examples
- Cross-references to templates

### Implementation order (within feature branch)

1. **Phase 1: Test infrastructure** — set up `tests/` with stdlib `unittest`. Lock current behavior in regression tests before any changes.
2. **Phase 2: Multi-nameset files + namespaces + reference resolution** — foundational, unlocks everything else.
3. **Phase 3: Schema additions** — per-entry tags, format variants, design block, hidden flag. Pure schema, no logic complexity.
4. **Phase 4: Aggregate v2** — nested, per-source overrides, slot policies, source filtering, graceful degradation.
5. **Phase 5: Inheritance / extends** — resolution + add/remove + cycle detection.
6. **Phase 6: Variable-depth chains** — most exotic, lowest demand. Defer if scope creeps.
7. **Phase 7: Tier 2 UX** — `list` overhaul, `validate`, `--explain`, `--format`, `--filter`. Independent of phases 2–6 once their schema lands.

### Branching

All work happens on `feature/namegen-v2`, branched from `develop`. Phases land as commits on the branch. Once Tier 1 + Tier 2 both stabilize and pass tests in real campaigns, PR to `develop`. Then `develop` → `stable` per existing flow; bundle bump on `stable`.
