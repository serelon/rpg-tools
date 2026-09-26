# Sheet Guide — event-sourced character sheets

`scripts/sheet.py` keeps character sheets as a **ledger of dated events** folded against a
**rules pack**. A character is *resolved, not stored*: ask for the sheet at a date and the
tool replays every event up to it. Nothing in the ledger is ever refused — problems become
warnings you can proofread.

The engine is generic (any system); everything system-specific lives in JSON data. A worked
example ships in `examples/sheet/d20-lite/` (an invented d20-flavoured toy pack and its
character, Wren).

```bash
python scripts/sheet.py resolve examples/sheet/d20-lite/wren            # resolved JSON
python scripts/sheet.py validate examples/sheet/d20-lite/wren           # warnings, anchors, notices
python scripts/sheet.py quote examples/sheet/d20-lite/wren bond.strength --by 2
```

Contents: [Layout](#layout) · [Keys](#keys-and-reserved-names) · [Merging](#loading-and-merging) ·
[Rules](#rules) · [Shape](#shape) · [Catalog](#catalog) · [Manifest](#manifest) ·
[History](#history-events-and-effects) · [Dates](#dates) · [Expressions](#expressions) ·
[The fold](#the-fold) · [Warnings](#warnings-and-notices) · [Output](#output) · [CLI](#cli) ·
[Authoring tips](#authoring-tips)

---

## Layout

```
my-pack/rules.json            # traits, caps, costs, derived values, tables, budgets
my-pack/shape.json            # how the sheet is laid out (groups → sections → fields)
my-pack/catalog/*.json        # static data by key (names, text, per-level text)
my-pack/<char>/sheet.json     # manifest: which rules/shape/catalog, which history files
my-pack/<char>/history/creation.json
my-pack/<char>/history/s01.json   # one file per session
```

A campaign can add a houserule file that `extends` the pack and patches a number or two.

## Keys and reserved names

- Keys are dotted segments, each `[a-z_][a-z0-9_]*` and not a Python keyword.
- A **class trait** has exactly two segments, `class.id` (`skill.sneak`). A third segment is
  only valid as a **compound part** (`bond.strength`, `skill.sword.exp`).
- **Bare keys** are one segment (`xp`, `heritage`).
- List entry ids, span ids, anchor ids and catalog ids that are only used as *values* may
  contain `-` (`north-road`).
- **Reserved** (never a trait's first segment, derived key, class, list or span name):
  `current target key id entry value index list span_years span_open span_note span_id` and
  the builtin names `sum count min max table catalog clamp if _if round floor ceil abs rank
  get`. `base`/`effective` (output fields) and `modifiers`/`tallies` (rules keys) are held
  for a later modifier layer; a non-empty `modifiers`/`tallies` just produces a
  `reserved-unimplemented` notice.

## Loading and merging

Rules, shape and catalog files may declare `extends` — a path or list of paths **relative
to the declaring file**, globs allowed (`catalog/*.json`, sorted naturally: `s2` before
`s10`; a file matching its own glob is skipped).

- Parents merge depth-first in list order, then the declaring file on top.
- **Deep merge by key:** objects merge recursively, anything else — including arrays — is
  replaced by the later file, and `null` **removes** a key.
- **Diamonds** merge each file once, at its first position: `x` extends `[a, b]`, both
  extending `c`, merges `c, a, b, x` — so `a`'s overrides of `c` survive `b`.
- A cycle is fatal: `Circular extends detected: a.json -> b.json -> a.json`.
- Because arrays replace wholesale, anything a child may want to patch is a **keyed
  object** (budgets, groups, sections). A campaign houserule can patch one number:

```json
{"extends": "../../packs/my-pack/rules.json",
 "creation": {"budgets": {"skills": {"total": 4}}}}
```

Malformed pack/manifest/catalog JSON, missing files, bad expressions and key collisions are
**fatal** (exit 2). Anything in the ledger is a **warning**.

## Rules

| field | meaning |
|---|---|
| `id`, `name` | pack id (echoed as `system.rules`) |
| `currency` | default currency trait for costs (default `"xp"`) |
| `classes` | `{class: ClassDef}` — families of traits (`skill`, `ability`) |
| `traits` | `{key: TraitDef}` — declared traits (`ability.might`, bare `xp`) |
| `lists` | `{name: {name, cap?, cost?, currency?, gm_only?, catalog?, fields?}}` |
| `spans` | `{kind: {name, gm_only?}}` — periods with a start and end |
| `tables` | `{name: {"rows": {KEY: row}}}` or `{name: {"steps": [[threshold, row], ...]}}` |
| `derived` | `{key: expr}` or `{key: {expr, name, gm_only?}}` |
| `creation` | `{budgets, freebies?, checks?}` — see [Creation budgets](#creation-budgets) |
| `notices` | `{code: {scope: "sheet" \| "span:KIND", when, message}}` |

**ClassDef / TraitDef fields** (a declared trait inherits its class's fields, then overrides):

| field | meaning |
|---|---|
| `name`, `note`, `gm_only` | display; `gm_only` hides from the player view |
| `type` | `rating` (default) · `enum` · `number` · `text` · `compound` · `relation` |
| `min`, `max` | expressions; rating `min` defaults to 0 |
| `default` | value while absent (rating/number → `min`, enum → first value, text/relation → null, compound → part defaults) |
| `base` | creation baseline (defaults to `default`) |
| `values` | enum values, ordered low → high |
| `parts` | compound: `{part: TraitDef}` of rating/enum/number/text parts |
| `group` | group id (traits); class: `groups` (ordered list) and `default_group` |
| `open` | class only: undeclared keys in the class are fine (custom abilities) |
| `catalog` | rating class: the catalog namespace for its ids; text trait: namespace its *value* is looked up in |
| `cost` | `{new?, raise, currency?}` — expressions priced per step (below) |
| `active` | expression; false → the trait is on the sheet but inactive |
| `per_trait` | class only: `{name: expr}` computed for every trait a class section shows |

- **Undeclared keys:** `class.id` in a declared class inherits the ClassDef — known if the
  class is `open` or (for a catalog class) the id is in its catalog, otherwise
  `unknown-trait`. Any other undeclared key is a rating, min 0, and `unknown-trait`.
- **Compound** traits (a shade + exponent, a value + passion) hold `{part: value}`;
  effects target `KEY.part`; bounds and costs are per part.
- **Relation** traits hold `{ref, name}` — `ref` is a path to another `sheet.json` or a free
  id. It is stored and displayed; v1 does not resolve across ledgers.

**Costs.** For each step of an increase, `current` is the rating before the step and
`target` = `current + 1`. `cost.new` prices the first dot (used iff `current == 0` and `new`
is defined); `cost.raise` every other step. Enums price by index. Costs are evaluated against
the *running* state, so an earlier effect in the same event (a changed clan, say) affects
later prices.

**Lists** are ordered collections of entries with stable ids (gear, feats, marks). `cap`
is an expression; `cost` prices a `gain` (local `entry`); `catalog` joins an entry's `ref`
to a catalog entry (name/text/levels); `fields` are computed per entry (local `entry`) and
visible everywhere, including projections:

```json
"lists": {"gear": {"name": "Gear", "fields": {"load": "entry.weight * entry.qty"}}},
"derived": {"load": "sum(list.gear[*].load)", "capacity": "ability.might * 5"},
"notices": {"overloaded": {"scope": "sheet", "when": "load > capacity",
                           "message": "Carrying more than capacity"}}
```

### Creation budgets

Creation events (`"kind": "creation"`) are checked against budgets instead of priced.

```json
"creation": {
  "budgets": {
    "abilities": {"class": "ability", "total": 27, "step_cost": "if(target > 13, 2, 1)"},
    "attrs":     {"class": "attr", "by": "group", "priority": [7, 5, 3]},
    "grit":      {"keys": ["grit"], "total": 0, "base": "virtue.alpha"},
    "gifts":     {"list": "gifts", "total": 2, "spend": "sum(list.gifts[*].points)"},
    "powers":    {"class": "power", "total": 3, "where": "id in catalog('kind', kind).powers"}},
  "freebies": {"total": "15 + min(7, sum(list.flaws[*].points))",
               "cost": {"attrs": 5, "grit": 1}},
  "checks": {"level": {"when": "level != 1", "message": "Start at level 1"}}}
```

- A budget covers a `class`, a list of `keys`, or a `list`.
- **Spend** per trait = Σ `step_cost` (default 1) over the steps from `base` to the value
  (below base counts −1 per step: an underspend). `base` defaults to the TraitDef `base`;
  a budget `base` expression overrides it (locals `key id entry`).
- `total: n` is one slot; `by: "group"` + `priority` is one slot per class group, per-group
  spends sorted high → low matched against the priorities sorted high → low. The class's
  `groups` (or the groups observed on its declared traits) must match the priority length.
- **Underspend warns. Overspend costs** `over × freebies.cost[budget id, else class]`
  freebies (no cost defined → warns). Freebies spent ≠ `freebies.total` warns.
- `where` false on a spent trait warns; each `checks.<id>.when` that is true warns.
- Everything is evaluated on the **creation state** (the fold of creation events only), so
  later play never trips a creation check.
- Give every freebie-purchasable trait a budget; freebies on an unbudgeted trait are
  neither priced nor warned.

## Shape

```json
{"id": "my-pack", "groups": {
  "identity": {"name": "Identity", "order": 10, "sections": {
    "core": {"order": 10, "fields": [
      {"key": "heritage", "kind": "choice", "options": {"catalog": "heritage"}},
      {"key": "level", "kind": "derived"},
      {"key": "patron", "kind": "relation", "show": "present"}]}}},
  "skills": {"name": "Skills", "order": 30, "sections": {
    "skills": {"class": "skill", "show": "all"}}},
  "gear": {"name": "Gear", "order": 50, "sections": {"gear": {"list": "gear"}}},
  "journeys": {"name": "Journeys", "order": 60, "sections": {"all": {"spans": "*"}}}}}
```

- **Group:** `name`, `order` (ties by key), `gm_only`, `sections`.
- **Section:** `name`, `order`, `gm_only`, `note`, and exactly one of `fields` (array),
  `class` (+ `where: {group: X}`, `show: present | active | all`, optional `kind`),
  `list: NAME`, `spans: KIND | "*"`.
- **Field:** `key` (required except `track`/`nested`), `kind`, `name`, `max` (display-only
  override; `over-cap` always uses the TraitDef), `levels` (track), `options` (choice:
  `{catalog: ns}` · `{table: name}` · `{values: [...]}`), `fields` (nested), `show: present`
  (omit while absent), `gm_only`, `note`.
- **Field kinds:** `fixed catalog named nested choice scalar derived pool track relation`.
  Class sections generate fields: `catalog` if the class has a catalog, `named` if open,
  else `fixed`. Order: declared traits, then undeclared present traits by display name.
  `show: active` = present plus declared-and-active (present-but-inactive traits are kept
  and flagged `inactive`); `all` = declared plus present.

**Display names:** event/edit meta `name` → shape field `name` → TraitDef `name` → catalog
entry `name` → the id title-cased (`self_control` → "Self Control").

## Catalog

`{ns: {id: entry}}`, merged like rules. Entry fields: `name`, `text` (write paraphrase,
never quote a book), `levels` (`{"1": {name, text}, ...}`), plus anything else expressions
may need (`catalog('skill', id).ability`, a kind's list of powers).

## Manifest

```json
{"id": "wren", "name": "Wren Tallow",
 "rules": "../rules.json", "shape": "../shape.json", "catalog": "../catalog.json",
 "history": ["history/creation.json", "history/s*.json", "history/branch-*.json"],
 "meta": {"concept": "a reedfolk courier"}}
```

`rules`/`shape`/`catalog` take a path or list (merged left to right, as if extended).
`history` is a list of paths/globs expanded in order, each glob sorted naturally, duplicates
kept at first position; a listed file that does not exist yet is simply skipped. The
**file index** (position in that list) is a sort tiebreak. `meta` is passed through.

## History: events and effects

One file per source, an object (not a bare array):

```json
{"source": "s01",
 "events": [
  {"date": "412-06", "when": "practising on the rooftops", "seq": 2,
   "effects": [{"add": "skill.sneak", "by": 1}, {"add": "training", "by": -2}],
   "note": "…"}]}
```

Event fields: `date` (required), `when` (freeform label), `seq` (tiebreak), `effects`
(required), `note`, `gm_only`, `free` (a reason; silences `no-cost`), `kind: "creation"`,
`satisfies` (an anchor id — provenance only), `source` (informational).

| effect | meaning |
|---|---|
| `{"set": KEY, "to": V}` | rating int, enum value, number, text, relation `{ref, name}`, compound `{part: v}`; KEY may be `KEY.part` |
| `{"add": KEY, "by": N}` | `by` defaults to 1, may be negative; enums move N steps |
| `{"gain": "list.NAME", "id": ID, "entry": {...}}` | add a list entry (`name`, `text`, `gm_only`, `ref`, any fields) |
| `{"edit": KEY, "fields": {...}}` | trait meta only: `name group note gm_only`; `null` removes |
| `{"edit": "list.NAME", "id": ID, "fields": {...}}` | merge into an entry; `null` removes |
| `{"retire": KEY}` / `{"retire": "list.NAME", "id": ID}` | off the sheet; history keeps it |
| `{"start": KIND, "id": ID, "name"?, "note"?}` / `{"end": KIND, "id": ID, "note"?}` | spans |
| `{"anchor": KEY, "id": ID, "at_least": N}` / `"at_most": N` | numeric assertion (enum by index) |
| `{"anchor": KEY, "id": ID, "is": V}` | text/enum assertion |
| `{"anchor": "list.NAME", "id": ID, "has": ENTRY_ID}` | entry must be live |

`set`/`add` may also carry trait meta (`name`, `group`, `note`, `gm_only`).

**Costs are stored as paid.** A raise records its payment as a negative `add` on the
currency (`{"add": "xp", "by": -5}`), never recomputed: inserting an older event later must
not rewrite spent XP. The fold compares what was paid with what it would quote and warns.

**Lifecycle:** a retired trait touched again comes back fresh (from its default), keeping
its old provenance; `gain` of a retired entry id revives it with only the new entry; `gain`
of a live id, `edit`/`retire` of something missing, reusing a span id or ending a closed
span are `invalid-event` (effect skipped). `add` on text/relation and setting an enum to an
unknown value are `invalid-event`; `add` past either end of an enum clamps and warns
`over-cap`.

**Anchors** are assertions, not effects — "by 1200 this is at least 4" (a branch file
written ahead of the trunk). They lift the value in the trait's better direction from their
date: `at_least` is a floor, `at_most` a ceiling for lower-is-better traits, `is`/`has` for
text/enum/lists. An anchor is *satisfied* if the plain fold already meets it at its
position; `validate` lists the ones the trunk has not reached.

## Dates

Partial ISO: `1130`, `1130-10`, `1130-10-31`, signed years allowed (`-500`; year 0 exists).
Prose is never a date. Dates say *when the sheet changes*; `when` carries the story label.

- **Order:** date, vaguer before contained (`1130` < `1130-01` < `1130-01-01`), then `seq`,
  then file index, then position in the file. Events fold by in-world date, not by the
  order they were written.
- **`--at D`** includes everything within the named period: `--at 1130` includes
  `1130-12-31`.
- **Years** (span durations): `Y + (M−1)/12 + (D−1)/372`. An open span runs to `--at`, else
  to the latest included event.

## Expressions

Expression slots take a number/bool literal or a string expression. The language is a tiny
safe subset of Python syntax, parsed with `ast` and checked against a whitelist at load
(nothing is `eval`ed):

- literals, names, `.attr`, `[index]`, lists, `and or not`, `+ - * / // %`, comparisons
  including `in`/`not in`, and calls to the builtins only;
- `list.gear[*].load` projects over a list; `if(c, a, b)` is the lazy conditional;
- arithmetic needs numbers (no string or list tricks), division by zero and non-finite
  results are errors; attributes on `None` give `None`; ordering against `None` is an error;
- max 1000 characters, AST depth 50; no `_private` attributes.

**Names** resolve longest dotted prefix first, then by tier: local variables → derived keys
→ traits (present value, or the default if declared / in an open class) → a bare class name
(`{id: value}` of its present traits, so `sum(virtue)`, `count(skill)`, `ability[x]`) →
`list` (`{name: [entries]}`) → error. A typo under a closed class (`ability.mihgt`) is an
error, not `None`. Enums are their string value (`skill.sneak == 'expert'`); `rank('skill.sneak')`
gives the position.

| builtin | returns |
|---|---|
| `sum(xs)` | sum of numbers in a list or object's values; `None` skipped; empty → 0 |
| `count(xs)` | number of items that aren't `None`, `False`, `0` or `""` |
| `min(a, b, …)` / `min(xs)`, `max` | min / max; empty is an error |
| `table(name, key)` | a row of `rules.tables[name]` (`rows`: exact key; `steps`: greatest threshold ≤ key) |
| `catalog(ns, key)` | the merged catalog entry, or `None` |
| `if(cond, a, b)` | lazy conditional |
| `clamp(x, lo, hi)`, `round(x, n)`, `floor(x)`, `ceil(x)`, `abs(x)` | numeric helpers |
| `rank(key)` | enum position of a trait |
| `get(container, k)` | same as `container[k]` |

**Locals** per slot: costs `key id current target entry` (+ `value` for compound parts);
`active`, budget `where`/`base`: `key id entry`; budget `step_cost`: `key id entry current
target`; class `per_trait`: `key id entry value index`; list `cost`/`fields`: `entry`;
span notices: `span_id span_years span_open span_note`. `entry` is the catalog entry for
the trait id (or the flat list entry for list slots).

Runtime failures never crash the tool: they produce an `expr-error` warning and the value
`None`. Derived cycles (`a -> b -> a`) are reported the same way.

## The fold

1. Load and merge everything; parse every expression.
2. Validate events; malformed ones are skipped with `invalid-event`.
3. Sort by date; drop events after `--at`.
4. The **creation state** folds creation events only (for budgets).
5. The main fold applies every event to the **unanchored state**, pricing raises and
   checking caps, payments and unknown keys as it goes.
6. The **anchored state** applies every anchor to that result (floors, ceilings, `is`).
   Costs use the unanchored state; derived values and the output use the anchored one.
7. A final sweep checks caps (including a derived cap that dropped), inactive traits,
   unsatisfied anchors, creation budgets and notices.

**Inactive traits** (Road-style virtue sets): when an event changes which traits of a class
are `active`, the fold warns once at that event and then per inactive trait on the sheet.
Nothing is converted automatically — switching is an explicit later event (`retire` the
old, `set` the new).

## Warnings and notices

Warnings (`{code, message, key?, ref?}`) — nothing is refused:

| code | when |
|---|---|
| `cost-mismatch` | the event paid a different amount than the quote |
| `no-cost` | a priced raise with no payment and no `free` reason |
| `over-cap` | a rating outside min/max, an enum pushed past its end, a list over its cap |
| `negative-pool` | a `number` trait below its `min` |
| `unknown-trait` | undeclared key in a closed class, id not in the class catalog, undeclared list/span kind/anchor key, an anchor on the wrong kind of trait |
| `before-creation` | a non-creation event dated before the first creation event |
| `unsatisfied-anchor` | an anchor the plain fold hasn't reached at its date |
| `creation-budget` | budget under/overspend, freebies mismatch, `where` or `checks` failures |
| `inactive-trait` | an active-set change (at the event) or an inactive trait on the sheet |
| `invalid-event` | malformed events/effects and lifecycle violations |
| `expr-error` | an expression failed at runtime |

**Notices** (`{code, message, ref?, span?}`) are due processes and thresholds, never run by
the engine: rule-defined `notices` and the engine's `reserved-unimplemented`. Filtered caps
("no more than three attuned items") are sheet notices:
`count(list.gear[*].attuned) > 3`.

## Output

`resolve` prints, in order: `format` (`"sheet/1"`), `view`, `at`, `character {id, name,
meta}`, `system {rules, shape}`, `groups`, `lists`, `spans`, `values`, `derived`, and in
the GM view `anchors`, `warnings`, `notices`.

- **Groups → sections → fields**, render-ready: every trait-backed field carries `type`
  (renderers draw by `type`, and use `kind` only for extras), `name`, `value`, and per type
  `min`/`max` (rating), `values`/`index` (enum), `parts` (compound). Catalog fields add
  `text` and `levels` up to the rating; choices add `display` and `text`; pools give
  `value` = `max`; tracks give `levels` or `max`. Class sections add `computed` from
  `per_trait`. GM view adds `warn: [codes]`.
- **Lists** entries `{id, name, text, ref?, fields, from}`; **spans** `{id, kind, name,
  start, end, open, years, note, from}`.
- `values` holds present, non-retired traits (anchored); `derived` every derived key.
- **Provenance:** `from` lists the refs (`"s01#3"` = third event of `history/s01.json`) of
  events that touched a trait/entry/span. `--provenance off` drops it.
- **Player view** (`--player`, and `export`): same values; drops warnings, anchors,
  notices, everything `gm_only` (including traits, entries and spans *created* by a
  `gm_only` event, and `gm_only` derived keys), and hides refs to `gm_only` events and to
  events containing anchors (branch files are spoilers).

## CLI

`SHEET` is a `sheet.json` or its directory. stdout carries only the artifact; warnings go to
stderr as `sheet: warning [code] message (ref)` (`--quiet` silences them). Exit 0 = ok
(warnings never fail), 1 = `validate --strict` found warnings, 2 = fatal input or usage
error. Dates on the command line must match the date format — prose exits 2.

```bash
sheet.py resolve SHEET [--at D] [--gm|--player] [--provenance on|off] [--compact]
sheet.py export SHEET [--at D] [--provenance on|off] [--key NAME]   # JS: DATA.sheet = {...};
sheet.py validate SHEET [--at D] [--strict] [--json]
sheet.py quote SHEET KEY [--by N] [--at D] [--json]    # bond.strength 2→4: 3 + 4 = 7 training
sheet.py history SHEET [KEY] [--at D] [--json]         # date  ref  when  effects
sheet.py diff SHEET --from D --to D [--player] [--json]
```

**Writers** append one event to `history/<source>.json` (created if missing). All take
`--date D --source S` plus `--when`, `--note`, `--seq N`, `--gm-only`, `--free REASON`,
`--dry-run`:

```bash
sheet.py add SHEET skill.climb --date 413-02 --source s03              # payment auto-filled
sheet.py add SHEET ability.wit --no-cost --free "a gift" --date 413 --source s03
sheet.py gain SHEET list.gear --id lamp --name Lamp --set weight=1 --set qty=2 --date 413 --source s03
sheet.py edit SHEET list.gear --id lamp --set qty=3 --unset tag --date 413 --source s03
sheet.py retire SHEET list.gear --id anvil --date 413 --source s03
sheet.py event SHEET --file events.json --source s03   # one event, an array, or {"events": [...]}
```

- **Cost auto-fill:** the writer folds with the new event tentatively inserted, reads its
  quote and appends `{"add": currency, "by": -cost}`; `--cost N` overrides, `--no-cost`
  skips.
- **Glob guard:** `history/<source>.json` must match the manifest's `history` patterns,
  else nothing is written (exit 2) — a write the loader would never read is refused.
- `event --file` checks every event first; any malformed one → exit 2, nothing written.
  `--date` there is optional and fills events that lack one.
- Writers never edit existing events. Fixing an old event is a deliberate hand-edit.
- Writes are atomic (temp file + rename) with 2-space indentation.

The export fragment assigns, never declares: the page's own data script must declare
`const DATA = {...}` before it. Every `<` in the JSON is escaped as `<`, so notes
containing `</script>` are safe to inline.

## Authoring tips

- **Pre-format hand-written history files** with 2-space indentation (as the writers do),
  so the first CLI append doesn't re-indent every line in the diff.
- Record payments in the same event as the raise; use `free` for story gifts.
- Keep branch assertions in their own files (`history/branch-*.json`) with anchors — they
  never pollute the trunk and are hidden from the player view.
- Put numbers a campaign might change in keyed objects (budgets by id) so a houserule file
  can patch one value.
- Derived values that would reveal a `gm_only` trait should themselves be `gm_only`.
- Growing the language happens in the engine (new builtins), never as code in packs.
