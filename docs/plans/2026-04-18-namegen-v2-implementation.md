# Namegen v2 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Overhaul the namegen tool's data model to support namespaces, multi-nameset files, formalized design metadata, named format variants, variable-depth chains, per-entry tagging, inheritance, and substantially richer aggregate composition (nested aggregates, slot policies, per-source overrides, filtering, graceful degradation). Then layer in CLI UX improvements (briefer `list`, `validate`, `--explain`, `--format`, `--filter`).

**Architecture:** All v1 namesets continue to work unchanged (full backward compatibility). New features are opt-in via presence of new fields. Internal flattening means the in-memory `custom_namesets` dict (keyed by full `namespace:id`) is the single source of truth regardless of file layout. Aggregate dispatch becomes type-aware (recurses for nested) and slot-aware (per-slot source policies).

**Tech Stack:** Python 3 stdlib only (no new deps). Tests use `unittest` from stdlib. Plain Python scripts in `scripts/`.

**Reference design doc:** `docs/plans/2026-04-18-namegen-v2-design.md`

---

## Pre-flight

### Branch setup

**Step 1: Create feature branch from develop**

```bash
git checkout develop
git pull
git checkout -b feature/namegen-v2
```

**Step 2: Verify clean state**

```bash
git status
```

Expected: "On branch feature/namegen-v2", working tree clean (the two design/plan docs may show as untracked).

**Step 3: Stage and commit the design + plan docs first**

```bash
git add docs/plans/2026-04-18-namegen-v2-design.md docs/plans/2026-04-18-namegen-v2-implementation.md
git commit -m "docs(namegen): add v2 design and implementation plan"
```

---

## Phase 1: Test Infrastructure

The existing namegen tool has zero tests. Before changing anything, lock current behavior in a regression baseline. This makes the rest of the plan safe.

### Task 1.1: Test directory and runner

**Files:**
- Create: `tests/__init__.py` (empty)
- Create: `tests/README.md`
- Create: `tests/run_tests.py`

**Step 1: Create the tests directory structure**

Create `tests/__init__.py` as empty file.

Create `tests/README.md`:

```markdown
# Tests

Run all tests:

    python tests/run_tests.py

Run a specific module:

    python -m unittest tests.test_namegen_discovery -v

Run a specific test:

    python -m unittest tests.test_namegen_discovery.TestDiscovery.test_loads_single_file -v

No external dependencies. Uses stdlib `unittest`.
```

Create `tests/run_tests.py`:

```python
#!/usr/bin/env python3
"""Run all tests under tests/."""
import sys
import unittest
from pathlib import Path

if __name__ == "__main__":
    repo_root = Path(__file__).parent.parent
    sys.path.insert(0, str(repo_root))
    sys.path.insert(0, str(repo_root / "scripts"))

    loader = unittest.TestLoader()
    suite = loader.discover(start_dir=str(Path(__file__).parent), pattern="test_*.py")
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
```

**Step 2: Run the runner to verify infrastructure works**

```bash
python tests/run_tests.py
```

Expected: "Ran 0 tests" (no tests yet, but no errors).

**Step 3: Commit**

```bash
git add tests/
git commit -m "test: add test infrastructure for namegen"
```

### Task 1.2: Regression test — current namegen baseline

**Files:**
- Create: `tests/fixtures/namesets/simple-test.json`
- Create: `tests/fixtures/namesets/aggregate-test.json`
- Create: `tests/fixtures/namesets/grouped-test.json`
- Create: `tests/test_namegen_baseline.py`

**Step 1: Create test fixtures (small, deterministic-friendly namesets)**

`tests/fixtures/namesets/simple-test.json`:

```json
{
  "id": "simple-test",
  "name": "Simple Test",
  "nameCategories": {
    "firstName": [
      {"name": "Alice", "gender": "female"},
      {"name": "Bob", "gender": "male"},
      {"name": "Sam", "gender": "unisex"}
    ],
    "lastName": [
      {"name": "Smith"},
      {"name": "Jones"}
    ]
  },
  "format": "{firstName} {lastName}"
}
```

`tests/fixtures/namesets/aggregate-test.json`:

```json
{
  "id": "aggregate-test",
  "name": "Aggregate Test",
  "type": "aggregate",
  "genderWeights": {"male": 50, "female": 50},
  "format": "{firstName} {lastName}",
  "sources": [
    {"nameset": "simple-test", "weight": 100, "label": "simple"}
  ]
}
```

`tests/fixtures/namesets/grouped-test.json`:

```json
{
  "id": "grouped-test",
  "name": "Grouped Test",
  "genderWeights": {"male": 50, "female": 50},
  "format": "{firstName} {lastName}",
  "nameGroups": {
    "alpha": {
      "weight": 50,
      "firstNames": [{"name": "Anna", "gender": "female"}],
      "lastNames": [{"name": "Aldridge"}]
    },
    "beta": {
      "weight": 50,
      "firstNames": [{"name": "Bram", "gender": "male"}],
      "lastNames": [{"name": "Beaumont"}]
    }
  }
}
```

**Step 2: Write regression tests for current behavior**

`tests/test_namegen_baseline.py`:

```python
"""Regression baseline: lock current namegen behavior before refactoring."""
import random
import unittest
from pathlib import Path

import namegen


class NamegenBaseline(unittest.TestCase):
    """Verify current behavior continues to work after every change."""

    @classmethod
    def setUpClass(cls):
        # Load fixtures
        fixtures_root = Path(__file__).parent
        namegen.discover_namesets(fixtures_root)

    def setUp(self):
        random.seed(42)  # Deterministic generation

    def test_simple_nameset_loads(self):
        self.assertIn("simple-test", namegen.custom_namesets)

    def test_aggregate_nameset_loads(self):
        self.assertIn("aggregate-test", namegen.custom_namesets)
        self.assertEqual(
            namegen.custom_namesets["aggregate-test"].get("type"), "aggregate"
        )

    def test_grouped_nameset_loads(self):
        self.assertIn("grouped-test", namegen.custom_namesets)
        self.assertIn("nameGroups", namegen.custom_namesets["grouped-test"])

    def test_simple_generation_produces_two_words(self):
        names = namegen.generate_from_nameset("simple-test", count=1)
        self.assertEqual(len(names), 1)
        self.assertEqual(len(names[0].split()), 2)

    def test_simple_generation_count(self):
        names = namegen.generate_from_nameset("simple-test", count=5)
        self.assertEqual(len(names), 5)

    def test_simple_gender_filter_female(self):
        for _ in range(20):
            names = namegen.generate_from_nameset("simple-test", count=1, gender="female")
            first = names[0].split()[0]
            self.assertIn(first, ("Alice", "Sam"))

    def test_simple_gender_filter_male(self):
        for _ in range(20):
            names = namegen.generate_from_nameset("simple-test", count=1, gender="male")
            first = names[0].split()[0]
            self.assertIn(first, ("Bob", "Sam"))

    def test_aggregate_generation(self):
        names = namegen.generate_from_aggregate("aggregate-test", count=3)
        self.assertEqual(len(names), 3)

    def test_grouped_generation(self):
        names = namegen.generate_from_nameset_with_groups("grouped-test", count=3)
        self.assertEqual(len(names), 3)

    def test_grouped_force_group(self):
        names = namegen.generate_from_nameset_with_groups("grouped-test", count=5, group="alpha")
        for n in names:
            self.assertEqual(n.split()[0], "Anna")

    def test_format_string_simple(self):
        cats = {
            "firstName": [{"name": "X"}],
            "lastName": [{"name": "Y"}],
        }
        result = namegen.build_name_from_format("{firstName} {lastName}", cats)
        self.assertEqual(result, "X Y")

    def test_format_string_optional_section(self):
        cats = {"firstName": [{"name": "X"}]}
        # Optional with no available content collapses
        result = namegen.build_name_from_format("{firstName}[ {missing}]", cats)
        self.assertEqual(result, "X")

    def test_random_pattern(self):
        result = namegen.generate_pattern("AAA")
        self.assertEqual(len(result), 3)
        self.assertTrue(result.isupper())
        self.assertTrue(result.isalpha())

    def test_random_range(self):
        result = namegen.generate_range(1, 10)
        self.assertTrue(1 <= int(result) <= 10)


if __name__ == "__main__":
    unittest.main()
```

**Step 3: Run the tests to verify they all pass**

```bash
python tests/run_tests.py
```

Expected: All tests pass. If any fail, the fix is in the test (the current code is the source of truth at this baseline).

**Step 4: Commit**

```bash
git add tests/
git commit -m "test(namegen): regression baseline for current behavior"
```

---

## Phase 2: Multi-nameset Files + Namespaces

The foundation. Internal IDs become `namespace:id`. Multi-nameset files supported. Reference resolution: bare → current namespace → root.

### Task 2.1: Internal IDs become qualified

**Files:**
- Modify: `scripts/lib/discovery.py` (current discovery logic — needs to track namespace per loaded nameset)
- Modify: `scripts/namegen.py` — `discover_namesets` to use qualified IDs internally
- Test: `tests/test_namegen_namespaces.py`

**Step 1: Read current discovery code**

```bash
cat scripts/lib/discovery.py
```

Note the current return type and structure. The change is: each loaded nameset gets its `id` rewritten internally to `<namespace>:<id>` (where namespace defaults to `""` if not declared). The user-facing `id` field in the JSON stays untouched; only the dict key changes.

**Step 2: Write failing tests for namespaced loading**

`tests/test_namegen_namespaces.py`:

```python
"""Tests for namespace-aware nameset loading and reference resolution."""
import unittest
from pathlib import Path

import namegen


class TestNamespaceLoading(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures_root = Path(__file__).parent / "fixtures-namespaces"
        namegen.discover_namesets(fixtures_root)

    def test_unqualified_nameset_lands_in_root_namespace(self):
        # simple-test was created without a namespace field → root
        self.assertIn(":simple-test", namegen.custom_namesets)

    def test_namespaced_nameset_loads_with_qualified_key(self):
        self.assertIn("metropolitan:english", namegen.custom_namesets)

    def test_multi_nameset_file_explodes(self):
        # multi-test.json declares namespace "test" with 3 namesets inside
        self.assertIn("test:alpha", namegen.custom_namesets)
        self.assertIn("test:beta", namegen.custom_namesets)
        self.assertIn("test:gamma", namegen.custom_namesets)

    def test_per_nameset_namespace_overrides_file_namespace(self):
        # Inside multi-test.json, gamma declares its own namespace "override"
        self.assertNotIn("test:gamma-override", namegen.custom_namesets)
        self.assertIn("override:gamma-override", namegen.custom_namesets)


class TestReferenceResolution(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures_root = Path(__file__).parent / "fixtures-namespaces"
        namegen.discover_namesets(fixtures_root)

    def test_qualified_reference_resolves(self):
        result = namegen.resolve_nameset_ref("metropolitan:english", current_namespace="other")
        self.assertEqual(result, "metropolitan:english")

    def test_bare_reference_resolves_in_current_namespace_first(self):
        # "english" exists in metropolitan; from current_namespace=metropolitan it should resolve there
        result = namegen.resolve_nameset_ref("english", current_namespace="metropolitan")
        self.assertEqual(result, "metropolitan:english")

    def test_bare_reference_falls_back_to_root(self):
        # "simple-test" only exists in root; resolution from any namespace should find it
        result = namegen.resolve_nameset_ref("simple-test", current_namespace="metropolitan")
        self.assertEqual(result, ":simple-test")

    def test_unresolvable_reference_returns_none(self):
        result = namegen.resolve_nameset_ref("nonexistent", current_namespace="metropolitan")
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
```

**Step 3: Create test fixtures**

Create directory `tests/fixtures-namespaces/namesets/`.

Copy `tests/fixtures/namesets/simple-test.json` to `tests/fixtures-namespaces/namesets/simple-test.json` (unchanged — represents an unqualified nameset).

Create `tests/fixtures-namespaces/namesets/metropolitan-english.json`:

```json
{
  "namespace": "metropolitan",
  "id": "english",
  "nameCategories": {
    "firstName": [{"name": "James", "gender": "male"}],
    "lastName": [{"name": "Smith"}]
  }
}
```

Create `tests/fixtures-namespaces/namesets/multi-test.json`:

```json
{
  "namespace": "test",
  "namesets": [
    {
      "id": "alpha",
      "nameCategories": {
        "firstName": [{"name": "A"}],
        "lastName": [{"name": "1"}]
      }
    },
    {
      "id": "beta",
      "nameCategories": {
        "firstName": [{"name": "B"}],
        "lastName": [{"name": "2"}]
      }
    },
    {
      "namespace": "override",
      "id": "gamma-override",
      "nameCategories": {
        "firstName": [{"name": "G"}],
        "lastName": [{"name": "3"}]
      }
    }
  ]
}
```

**Step 4: Run tests to verify they fail**

```bash
python -m unittest tests.test_namegen_namespaces -v
```

Expected: All fail (resolve_nameset_ref doesn't exist; namespacing not implemented).

**Step 5: Implement namespace-aware discovery**

In `scripts/lib/discovery.py`, modify `discover_data` (and helpers) to:

1. When loading a JSON file, detect if it's a multi-nameset file: `"namesets" in data and isinstance(data["namesets"], list)`.
2. For multi-nameset files: read top-level `namespace`; for each entry in `namesets`, use entry's `namespace` if present, else file-level. Store each as a separate item.
3. For single-nameset files: read top-level `namespace` (default `""`).
4. Return dict keyed by `<namespace>:<id>` (note: empty namespace produces `":id"` keys — intentional, marks unnamespaced).

The discovery module is shared with other tools (characters, locations, stories, etc.). Keep the multi-item file handling generic enough to apply to any data type, OR add a namegen-specific wrapper. Recommended: add a parameter `multi_collection_key` to `discover_data` that, when set, triggers multi-item-file handling. For namegen, pass `multi_collection_key="namesets"`. Other tools unchanged.

In `scripts/namegen.py`, update `discover_namesets` to pass `multi_collection_key="namesets"` and to read the new dict-shape.

Add `resolve_nameset_ref` to `scripts/namegen.py`:

```python
def resolve_nameset_ref(ref: str, current_namespace: str = "") -> Optional[str]:
    """Resolve a nameset reference to a fully-qualified key.

    Rules:
    - If ref contains ':', it's already qualified — return if exists, else None.
    - If ref is bare, try current_namespace first, then root ('').
    """
    if ':' in ref:
        return ref if ref in custom_namesets else None
    # Try current namespace
    candidate = f"{current_namespace}:{ref}"
    if candidate in custom_namesets:
        return candidate
    # Fall back to root
    candidate = f":{ref}"
    if candidate in custom_namesets:
        return candidate
    return None
```

**Step 6: Update existing functions to use qualified keys**

In `scripts/namegen.py`, every `if X in custom_namesets` lookup (in `generate_from_nameset`, `generate_from_aggregate`, `generate_from_nameset_with_groups`, `list_namesets`, `list_groups`, `main`) needs to either:

- Accept a qualified key from the caller, OR
- Resolve bare refs via `resolve_nameset_ref` (when callers might pass either).

For the CLI entry point in `main()`, when the user passes `--nameset NAME`, accept both bare and qualified; resolve via `resolve_nameset_ref(name, current_namespace="")`. Print a clear error if unresolvable.

For aggregate source resolution inside `generate_from_aggregate`, pass the parent aggregate's namespace as `current_namespace`. (Compute from the parent's qualified key by splitting on `:`.)

**Step 7: Update baseline tests for qualified keys**

The baseline tests in `tests/test_namegen_baseline.py` reference unqualified IDs (e.g. `"simple-test"`). Update each lookup to use the resolution path:

```python
# Old
self.assertIn("simple-test", namegen.custom_namesets)
# New
self.assertIn(":simple-test", namegen.custom_namesets)
```

Similarly for `generate_from_nameset` etc. — the public interface should still accept bare IDs and resolve them; only the internal dict keys change.

**Step 8: Run all tests to verify all pass**

```bash
python tests/run_tests.py
```

Expected: All baseline tests pass + all new namespace tests pass.

**Step 9: Smoke-test against real campaigns**

```bash
cd ../solorpg
python ../rpg-tools/scripts/namegen.py list 2>&1 | head -30
python ../rpg-tools/scripts/namegen.py full --nameset names-russian --count 3
cd ../rpg-tools
```

Expected: Existing namesets still load, generation still works, list output (still v1 format) shows all namesets in root namespace.

**Step 10: Commit**

```bash
git add scripts/ tests/
git commit -m "feat(namegen): namespace-aware loading and multi-nameset files"
```

### Task 2.2: --namespace CLI filter on list

**Files:**
- Modify: `scripts/namegen.py` (`list_namesets` and CLI option parsing)
- Test: `tests/test_namegen_list.py`

**Step 1: Write failing tests**

`tests/test_namegen_list.py`:

```python
"""Tests for list/filter CLI behavior."""
import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import namegen


class TestListNamespaceFilter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures_root = Path(__file__).parent / "fixtures-namespaces"
        namegen.discover_namesets(fixtures_root)

    def test_list_filters_by_namespace(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            namegen.list_namesets(namespace_filter="metropolitan")
        out = buf.getvalue()
        self.assertIn("english", out)
        self.assertNotIn("simple-test", out)
        self.assertNotIn("alpha", out)

    def test_list_no_filter_shows_all(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            namegen.list_namesets()
        out = buf.getvalue()
        self.assertIn("english", out)
        self.assertIn("simple-test", out)
        self.assertIn("alpha", out)
```

**Step 2: Run tests to verify they fail**

```bash
python -m unittest tests.test_namegen_list -v
```

Expected: FAIL — `list_namesets` doesn't accept a `namespace_filter` arg.

**Step 3: Implement the filter**

In `scripts/namegen.py`, update `list_namesets`:

```python
def list_namesets(namespace_filter: Optional[str] = None):
    if not custom_namesets:
        print("No namesets found")
        return

    items = sorted(custom_namesets.items())
    if namespace_filter is not None:
        items = [(k, v) for k, v in items if k.startswith(f"{namespace_filter}:")]

    print("Available namesets:")
    for full_id, nameset in items:
        # ... existing display logic, but show full_id instead of bare id ...
```

Wire up the CLI: parse `--namespace VALUE` in `main()` and pass to `list_namesets`.

**Step 4: Run tests, then full suite**

```bash
python -m unittest tests.test_namegen_list -v
python tests/run_tests.py
```

Expected: All pass.

**Step 5: Commit**

```bash
git add scripts/namegen.py tests/test_namegen_list.py
git commit -m "feat(namegen): --namespace filter on list"
```

---

## Phase 3: Schema Additions

Per-entry `tags`, `formats` map, `design` block, `hidden` flag. Each is a small focused change.

### Task 3.1: Per-entry tags + --filter

**Files:**
- Modify: `scripts/namegen.py` — update `build_name_from_tokens` to filter entries by tags before selection
- Test: `tests/test_namegen_tags.py`
- Fixture: `tests/fixtures-tags/namesets/tagged-test.json`

**Step 1: Create fixture**

`tests/fixtures-tags/namesets/tagged-test.json`:

```json
{
  "id": "tagged-test",
  "nameCategories": {
    "firstName": [
      {"name": "Marcus", "gender": "male", "tags": ["patrician", "imperial"]},
      {"name": "Brutus", "gender": "male", "tags": ["commoner"]},
      {"name": "Lucia", "gender": "female", "tags": ["patrician"]}
    ],
    "lastName": [
      {"name": "Aurelius", "tags": ["patrician"]},
      {"name": "Plebius", "tags": ["commoner"]}
    ]
  },
  "format": "{firstName} {lastName}"
}
```

**Step 2: Write failing tests**

`tests/test_namegen_tags.py`:

```python
"""Per-entry tag filtering."""
import random
import unittest
from pathlib import Path

import namegen


class TestPerEntryTags(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures_root = Path(__file__).parent / "fixtures-tags"
        namegen.discover_namesets(fixtures_root)

    def setUp(self):
        random.seed(42)

    def test_filter_single_tag(self):
        for _ in range(30):
            names = namegen.generate_from_nameset("tagged-test", count=1, tag_filter=["patrician"])
            first = names[0].split()[0]
            last = names[0].split()[1]
            self.assertIn(first, ("Marcus", "Lucia"))
            self.assertEqual(last, "Aurelius")

    def test_filter_no_match_falls_back(self):
        # No entries tagged 'nonexistent' → should not crash, should warn and use unfiltered
        names = namegen.generate_from_nameset("tagged-test", count=1, tag_filter=["nonexistent"])
        self.assertEqual(len(names), 1)

    def test_filter_multi_tag_AND(self):
        for _ in range(30):
            names = namegen.generate_from_nameset("tagged-test", count=1, tag_filter=["patrician", "imperial"])
            first = names[0].split()[0]
            self.assertEqual(first, "Marcus")

    def test_no_filter_uses_all(self):
        seen = set()
        for _ in range(50):
            names = namegen.generate_from_nameset("tagged-test", count=1)
            seen.add(names[0].split()[0])
        # Likely to have seen multiple entries
        self.assertGreater(len(seen), 1)
```

**Step 3: Run tests to verify failure**

```bash
python -m unittest tests.test_namegen_tags -v
```

Expected: FAIL — `generate_from_nameset` doesn't accept `tag_filter`.

**Step 4: Implement filtering**

Add a helper in `scripts/namegen.py`:

```python
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
```

Modify `build_name_from_tokens` to thread `tag_filter` down and apply it after the gender filter:

```python
def build_name_from_tokens(tokens, categories, gender=None, tag_filter=None, in_optional=False):
    # ...existing code...
    if effective_gender and any(e.get("gender") for e in entries):
        entries = filter_by_gender(entries, effective_gender, category)
    entries = filter_by_tags(entries, tag_filter, category)
    entry = select_weighted(entries)
    # ...
```

Thread `tag_filter` parameter through `build_name_from_format`, `generate_from_nameset`, `generate_single_name`, `generate_from_nameset_with_groups`. Default `None`.

Wire up CLI: parse `--filter TAG` (repeatable) in `main()`, collect into a list, pass through.

**Step 5: Run tests + smoke-test**

```bash
python tests/run_tests.py
```

Expected: All pass (baseline + namespaces + tags).

**Step 6: Commit**

```bash
git add scripts/ tests/
git commit -m "feat(namegen): per-entry tags with --filter (AND semantics)"
```

### Task 3.2: Formats map (named variants)

**Files:**
- Modify: `scripts/namegen.py` — add format normalization, `--format` flag
- Test: `tests/test_namegen_formats.py`
- Fixture: `tests/fixtures-formats/namesets/multi-format.json`

**Step 1: Create fixture**

`tests/fixtures-formats/namesets/multi-format.json`:

```json
{
  "id": "multi-format",
  "nameCategories": {
    "firstName": [{"name": "Valentina", "gender": "female"}],
    "lastName": [{"name": "Celestine"}],
    "title": [{"name": "Princess", "gender": "female"}],
    "rank": [{"name": "Cadet"}]
  },
  "formats": {
    "default": "{firstName} {lastName}",
    "formal": {
      "template": "{title} {firstName} {lastName}",
      "when": "Court appearances"
    },
    "naval": {
      "template": "{rank} {lastName}",
      "when": "Aboard ship"
    }
  }
}
```

**Step 2: Write failing tests**

`tests/test_namegen_formats.py`:

```python
"""Named format variants."""
import unittest
from pathlib import Path

import namegen


class TestFormatVariants(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures_root = Path(__file__).parent / "fixtures-formats"
        namegen.discover_namesets(fixtures_root)

    def test_default_format(self):
        names = namegen.generate_from_nameset("multi-format", count=1)
        self.assertEqual(names[0], "Valentina Celestine")

    def test_named_format_formal(self):
        names = namegen.generate_from_nameset("multi-format", count=1, format_name="formal")
        self.assertEqual(names[0], "Princess Valentina Celestine")

    def test_named_format_naval(self):
        names = namegen.generate_from_nameset("multi-format", count=1, format_name="naval")
        self.assertEqual(names[0], "Cadet Celestine")

    def test_unknown_format_warns_and_uses_default(self):
        # Should not crash
        names = namegen.generate_from_nameset("multi-format", count=1, format_name="nonexistent")
        self.assertEqual(names[0], "Valentina Celestine")

    def test_legacy_single_format_field_still_works(self):
        # The old "format": "..." string should still parse via shim
        # tested via the baseline simple-test fixture
        pass  # covered by baseline tests
```

**Step 3: Run tests, verify failure**

```bash
python -m unittest tests.test_namegen_formats -v
```

Expected: FAIL — `generate_from_nameset` doesn't accept `format_name`.

**Step 4: Implement format normalization**

Add to `scripts/namegen.py`:

```python
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
```

Update every call site that currently does `nameset.get("format", "...")` to use `get_format_template(nameset, format_name)`. Thread `format_name` parameter through `generate_from_nameset`, `generate_from_aggregate`, `generate_from_nameset_with_groups`, `generate_single_name`. Default `"default"`.

CLI: parse `--format NAME` in `main()`, pass through.

**Step 5: Run all tests**

```bash
python tests/run_tests.py
```

Expected: All pass (legacy tests still work via the get_format_template shim).

**Step 6: Commit**

```bash
git add scripts/ tests/
git commit -m "feat(namegen): named format variants with shorthand-or-object syntax"
```

### Task 3.3: Hidden flag + design block + nameset-level tags

**Files:**
- Modify: `scripts/namegen.py` — `list_namesets` respects `hidden`, `--all` flag
- Test: `tests/test_namegen_hidden.py`

**Step 1: Add fixtures with `hidden`, `design`, `tags`**

Append to `tests/fixtures-namespaces/namesets/multi-test.json` to add a hidden nameset:

```json
{
  "namespace": "test",
  "namesets": [
    ... (existing alpha, beta, gamma) ...,
    {
      "id": "delta-hidden",
      "hidden": true,
      "tags": ["internal"],
      "design": {
        "convention": "Used as aggregate base only"
      },
      "nameCategories": {
        "firstName": [{"name": "D"}],
        "lastName": [{"name": "4"}]
      }
    }
  ]
}
```

**Step 2: Write failing tests**

`tests/test_namegen_hidden.py`:

```python
"""Hidden flag behavior in list."""
import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import namegen


class TestHiddenFlag(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures_root = Path(__file__).parent / "fixtures-namespaces"
        namegen.discover_namesets(fixtures_root)

    def test_hidden_excluded_by_default(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            namegen.list_namesets()
        self.assertNotIn("delta-hidden", buf.getvalue())

    def test_hidden_shown_with_all_flag(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            namegen.list_namesets(show_hidden=True)
        self.assertIn("delta-hidden", buf.getvalue())

    def test_hidden_can_still_be_referenced_directly(self):
        # Even when not in list, generate should work
        names = namegen.generate_from_nameset("test:delta-hidden", count=1)
        self.assertEqual(len(names), 1)
```

**Step 3: Run tests, verify failure**

```bash
python -m unittest tests.test_namegen_hidden -v
```

Expected: FAIL — `list_namesets` doesn't accept `show_hidden`.

**Step 4: Implement**

Update `list_namesets` in `scripts/namegen.py`:

```python
def list_namesets(namespace_filter: Optional[str] = None, show_hidden: bool = False):
    if not custom_namesets:
        print("No namesets found")
        return

    items = sorted(custom_namesets.items())
    if namespace_filter is not None:
        items = [(k, v) for k, v in items if k.startswith(f"{namespace_filter}:")]
    if not show_hidden:
        items = [(k, v) for k, v in items if not v.get("hidden", False)]

    # ... existing display logic ...
```

CLI: add `--all` flag in `main()`, pass `show_hidden=args.all`.

**Step 5: Run all tests**

```bash
python tests/run_tests.py
```

Expected: All pass.

**Step 6: Commit**

```bash
git add scripts/ tests/
git commit -m "feat(namegen): hidden flag + --all to list aggregate bases"
```

---

## Phase 4: Aggregate v2

The biggest single change. Nested aggregates, slot policies, per-source overrides, source filtering, graceful degradation.

### Task 4.1: Type-aware source dispatch (enables nested aggregates)

**Files:**
- Modify: `scripts/namegen.py` — `generate_from_aggregate` to recurse on aggregate-type sources
- Test: `tests/test_namegen_nested.py`
- Fixture: `tests/fixtures-aggregates/namesets/nested.json`

**Step 1: Create fixture**

`tests/fixtures-aggregates/namesets/leaves.json`:

```json
{
  "namespace": "test",
  "namesets": [
    {
      "id": "alpha-leaf",
      "nameCategories": {
        "firstName": [{"name": "Aleph"}],
        "lastName": [{"name": "Anchor"}]
      }
    },
    {
      "id": "beta-leaf",
      "nameCategories": {
        "firstName": [{"name": "Bet"}],
        "lastName": [{"name": "Beam"}]
      }
    }
  ]
}
```

`tests/fixtures-aggregates/namesets/nested.json`:

```json
{
  "namespace": "test",
  "namesets": [
    {
      "id": "mid-aggregate",
      "type": "aggregate",
      "formats": {"default": "{firstName} {lastName}"},
      "sources": [
        {"nameset": "alpha-leaf", "weight": 100, "label": "alpha"}
      ]
    },
    {
      "id": "top-aggregate",
      "type": "aggregate",
      "formats": {"default": "{firstName} {lastName}"},
      "sources": [
        {"nameset": "mid-aggregate", "weight": 50, "label": "mid"},
        {"nameset": "beta-leaf", "weight": 50, "label": "beta"}
      ]
    }
  ]
}
```

**Step 2: Write failing tests**

`tests/test_namegen_nested.py`:

```python
"""Nested aggregates: aggregates that pull from other aggregates."""
import random
import unittest
from pathlib import Path

import namegen


class TestNestedAggregates(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures_root = Path(__file__).parent / "fixtures-aggregates"
        namegen.discover_namesets(fixtures_root)

    def setUp(self):
        random.seed(42)

    def test_top_aggregate_can_pick_nested_source(self):
        # Generate enough names; some should be from alpha-leaf (via mid-aggregate)
        seen_alpha = False
        seen_beta = False
        for _ in range(50):
            names = namegen.generate_from_aggregate("test:top-aggregate", count=1)
            if "Aleph" in names[0]:
                seen_alpha = True
            if "Bet" in names[0]:
                seen_beta = True
        self.assertTrue(seen_alpha)
        self.assertTrue(seen_beta)

    def test_nested_dispatch_no_empty_names(self):
        # Before this fix, picking a nested source would produce empty/garbage names
        for _ in range(30):
            names = namegen.generate_from_aggregate("test:top-aggregate", count=1)
            self.assertNotEqual(names[0].strip(), "")
            self.assertEqual(len(names[0].split()), 2)
```

**Step 3: Run tests, verify failure (or weird behavior)**

```bash
python -m unittest tests.test_namegen_nested -v
```

Expected: FAIL — `test_nested_dispatch_no_empty_names` likely fails with empty/garbage names when mid-aggregate is picked.

**Step 4: Implement type dispatch**

Refactor `generate_from_aggregate` in `scripts/namegen.py` so that when it picks a source, it dispatches by type:

```python
def generate_from_aggregate(nameset_id, count=1, source_label=None, gender=None, return_source=False, format_name="default", tag_filter=None):
    nameset = custom_namesets[nameset_id]
    sources = nameset.get("sources", [])
    gender_weights = nameset.get("genderWeights", {"male": 50, "female": 50})
    aggregate_namespace = nameset_id.split(":", 1)[0]

    results = []
    used = set()

    for _ in range(count):
        attempts = 0
        while attempts < 100:
            if source_label:
                selected = next((s for s in sources if s.get("label") == source_label), None)
                if not selected:
                    print(f"Error: Source '{source_label}' not found", file=sys.stderr)
                    sys.exit(1)
            else:
                selected = select_weighted_source(sources)

            source_ref = selected["nameset"]
            source_qualified = resolve_nameset_ref(source_ref, current_namespace=aggregate_namespace)

            if source_qualified is None:
                print(f"Warning: Source nameset '{source_ref}' not found, skipping", file=sys.stderr)
                attempts += 1
                continue

            source_nameset = custom_namesets[source_qualified]
            label = selected.get("label", source_ref)
            selected_gender = gender if gender else select_gender(gender_weights)

            # Dispatch by source type
            if source_nameset.get("type") == "aggregate":
                # Recurse: generate from the nested aggregate as if it were called directly
                sub = generate_from_aggregate(
                    source_qualified, count=1, gender=selected_gender,
                    format_name=format_name, tag_filter=tag_filter
                )
                name = sub[0] if sub else ""
            elif "nameGroups" in source_nameset:
                sub = generate_from_nameset_with_groups(
                    source_qualified, count=1, gender=selected_gender,
                    format_name=format_name, tag_filter=tag_filter
                )
                name = sub[0] if sub else ""
            else:
                name = generate_single_name(source_nameset, selected_gender, format_name=format_name, tag_filter=tag_filter)

            if name and name.lower() not in used:
                if return_source:
                    results.append((name, label))
                else:
                    results.append(name)
                used.add(name.lower())
                break
            attempts += 1
        else:
            if return_source:
                results.append((name, label))
            else:
                results.append(name)

    return results
```

`generate_single_name` and `generate_from_nameset_with_groups` need `format_name` and `tag_filter` parameters threaded through (already done in earlier tasks).

**Step 5: Run tests**

```bash
python tests/run_tests.py
```

Expected: All pass — including baseline (which uses non-nested aggregates).

**Step 6: Commit**

```bash
git add scripts/ tests/
git commit -m "feat(namegen): nested aggregates via type-aware source dispatch"
```

### Task 4.2: Graceful degradation on missing source

Already partially implemented in 4.1 (warn-and-skip instead of crash). Add explicit test.

**Files:**
- Test: append to `tests/test_namegen_nested.py` (or create `test_namegen_aggregate_robustness.py`)
- Fixture: `tests/fixtures-aggregates/namesets/missing-source.json`

**Step 1: Create fixture with missing source**

`tests/fixtures-aggregates/namesets/missing-source.json`:

```json
{
  "namespace": "test",
  "id": "broken-aggregate",
  "type": "aggregate",
  "formats": {"default": "{firstName} {lastName}"},
  "sources": [
    {"nameset": "alpha-leaf", "weight": 100, "label": "alpha"},
    {"nameset": "nonexistent-source", "weight": 100, "label": "ghost"}
  ]
}
```

**Step 2: Write test**

```python
class TestAggregateRobustness(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures_root = Path(__file__).parent / "fixtures-aggregates"
        namegen.discover_namesets(fixtures_root)

    def test_missing_source_does_not_crash(self):
        # Should warn but produce names from the working source
        names = namegen.generate_from_aggregate("test:broken-aggregate", count=10)
        # All names should be from alpha-leaf
        for n in names:
            self.assertIn("Aleph", n)
```

**Step 3: Run tests**

```bash
python -m unittest tests.test_namegen_nested -v
```

Expected: PASS (already implemented in 4.1).

**Step 4: Commit (if any test additions)**

```bash
git add tests/
git commit -m "test(namegen): aggregate robustness against missing sources"
```

### Task 4.3: Slot policies (inherit / independent / mix / forced)

The big new aggregate capability. Each format slot decides where to source its value from.

**Files:**
- Modify: `scripts/namegen.py` — new function `build_aggregate_name_with_slots`
- Test: `tests/test_namegen_slots.py`
- Fixture: `tests/fixtures-aggregates/namesets/slot-policies.json`

**Step 1: Create fixtures**

Add to `tests/fixtures-aggregates/namesets/slot-policies.json`:

```json
{
  "namespace": "test",
  "namesets": [
    {
      "id": "japanese-test",
      "nameCategories": {
        "firstName": [{"name": "Hiroshi", "gender": "male"}, {"name": "Yuki", "gender": "female"}],
        "lastName": [{"name": "Yamamoto"}, {"name": "Tanaka"}]
      }
    },
    {
      "id": "german-test",
      "nameCategories": {
        "firstName": [{"name": "Hans", "gender": "male"}, {"name": "Greta", "gender": "female"}],
        "lastName": [{"name": "Müller"}, {"name": "Schmidt"}]
      }
    },
    {
      "id": "diaspora-test",
      "type": "aggregate",
      "formats": {"default": "{firstName} {lastName}"},
      "sources": [
        {"nameset": "japanese-test", "weight": 50, "label": "ja"},
        {"nameset": "german-test", "weight": 50, "label": "de"}
      ],
      "slots": {
        "firstName": {"policy": "inherit"},
        "lastName": {"policy": "mix", "rate": 0.5}
      }
    },
    {
      "id": "fully-mixed",
      "type": "aggregate",
      "formats": {"default": "{firstName} {lastName}"},
      "sources": [
        {"nameset": "japanese-test", "weight": 50, "label": "ja"},
        {"nameset": "german-test", "weight": 50, "label": "de"}
      ],
      "slots": {
        "firstName": {"policy": "inherit"},
        "lastName": {"policy": "independent"}
      }
    },
    {
      "id": "forced-last",
      "type": "aggregate",
      "formats": {"default": "{firstName} {lastName}"},
      "sources": [
        {"nameset": "japanese-test", "weight": 50, "label": "ja"},
        {"nameset": "german-test", "weight": 50, "label": "de"}
      ],
      "slots": {
        "firstName": {"policy": "inherit"},
        "lastName": {"policy": "forced", "nameset": "japanese-test"}
      }
    }
  ]
}
```

**Step 2: Write failing tests**

`tests/test_namegen_slots.py`:

```python
"""Slot policies: inherit / independent / mix / forced."""
import random
import unittest
from pathlib import Path

import namegen


JA_FIRST = {"Hiroshi", "Yuki"}
JA_LAST = {"Yamamoto", "Tanaka"}
DE_FIRST = {"Hans", "Greta"}
DE_LAST = {"Müller", "Schmidt"}


class TestSlotPolicies(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures_root = Path(__file__).parent / "fixtures-aggregates"
        namegen.discover_namesets(fixtures_root)

    def setUp(self):
        random.seed(42)

    def test_default_inherit_produces_coherent(self):
        # No 'slots' map, no per-slot policy → should always be inherit (coherent)
        # Use diaspora-test but check that japanese-test's 'inherit' default behavior works
        # Actually use a coherent aggregate without slot map at all (existing nested test)
        for _ in range(50):
            names = namegen.generate_from_aggregate("test:diaspora-test", count=1)
            first, last = names[0].split()
            # Either both Japanese or first Japanese with German last (mix=0.5)
            # The point is: it shouldn't crash
            self.assertIn(first, JA_FIRST | DE_FIRST)
            self.assertIn(last, JA_LAST | DE_LAST)

    def test_independent_produces_cross_mix(self):
        # fully-mixed should produce names with first and last from different sources sometimes
        cross_mix_seen = False
        for _ in range(100):
            names = namegen.generate_from_aggregate("test:fully-mixed", count=1)
            first, last = names[0].split()
            if (first in JA_FIRST and last in DE_LAST) or (first in DE_FIRST and last in JA_LAST):
                cross_mix_seen = True
                break
        self.assertTrue(cross_mix_seen, "independent policy should produce cross-mix names")

    def test_mix_rate_produces_some_inherit_some_independent(self):
        # diaspora-test with mix rate 0.5 should produce a mix
        cross_mix_count = 0
        for _ in range(200):
            names = namegen.generate_from_aggregate("test:diaspora-test", count=1)
            first, last = names[0].split()
            first_ja = first in JA_FIRST
            last_de = last in DE_LAST
            first_de = first in DE_FIRST
            last_ja = last in JA_LAST
            if (first_ja and last_de) or (first_de and last_ja):
                cross_mix_count += 1
        # Expect roughly 50% (mix rate); allow wide margin: between 30 and 70
        self.assertGreater(cross_mix_count, 30)
        self.assertLess(cross_mix_count, 170)

    def test_forced_pins_slot_to_named_source(self):
        # forced-last should always have a Japanese last name regardless of first
        for _ in range(50):
            names = namegen.generate_from_aggregate("test:forced-last", count=1)
            first, last = names[0].split()
            self.assertIn(last, JA_LAST)
```

**Step 3: Run tests, verify failure**

```bash
python -m unittest tests.test_namegen_slots -v
```

Expected: FAIL — slot policies not implemented.

**Step 4: Implement slot-aware aggregate generation**

This is a substantial refactor. Add a new function `build_aggregate_name_with_slots` that:

1. Parses the aggregate's format template into tokens (using existing `parse_format`).
2. For each placeholder token, determines which source to draw from based on `slots[<category>].policy`.
3. Calls into the source nameset's per-category list to pick the right entry.

Pseudocode:

```python
def build_aggregate_name_with_slots(aggregate_id, gender, format_name="default", tag_filter=None, source_label=None):
    aggregate = custom_namesets[aggregate_id]
    aggregate_namespace = aggregate_id.split(":", 1)[0]
    sources = aggregate.get("sources", [])
    slots = aggregate.get("slots", {})

    # Pick anchor source (used for first slot and any slot with policy=inherit)
    if source_label:
        anchor_source = next((s for s in sources if s.get("label") == source_label), None)
        if not anchor_source:
            print(f"Error: Source label '{source_label}' not found", file=sys.stderr)
            sys.exit(1)
    else:
        anchor_source = select_weighted_source(sources)

    template = get_format_template(aggregate, format_name)
    tokens = parse_format(template)

    # Build name token by token
    result = []
    anchor_resolved = None  # Cached resolved anchor source nameset
    for token in tokens:
        if token["type"] == "literal":
            result.append(token["value"])
        elif token["type"] == "placeholder":
            category = token["value"]
            slot_policy = slots.get(category, {}).get("policy", "inherit")

            # Determine source for this slot
            if slot_policy == "forced":
                forced_ref = slots[category]["nameset"]
                source_qualified = resolve_nameset_ref(forced_ref, current_namespace=aggregate_namespace)
                source_choice = custom_namesets.get(source_qualified)
            elif slot_policy == "independent":
                rolled = select_weighted_source(sources)
                source_qualified = resolve_nameset_ref(rolled["nameset"], current_namespace=aggregate_namespace)
                source_choice = custom_namesets.get(source_qualified)
            elif slot_policy == "mix":
                rate = slots[category].get("rate", 0.5)
                if random.random() < rate:
                    rolled = select_weighted_source(sources)
                    source_qualified = resolve_nameset_ref(rolled["nameset"], current_namespace=aggregate_namespace)
                    source_choice = custom_namesets.get(source_qualified)
                else:
                    if anchor_resolved is None:
                        anchor_qualified = resolve_nameset_ref(anchor_source["nameset"], current_namespace=aggregate_namespace)
                        anchor_resolved = custom_namesets.get(anchor_qualified)
                    source_choice = anchor_resolved
            else:  # inherit (default)
                if anchor_resolved is None:
                    anchor_qualified = resolve_nameset_ref(anchor_source["nameset"], current_namespace=aggregate_namespace)
                    anchor_resolved = custom_namesets.get(anchor_qualified)
                source_choice = anchor_resolved

            # Pick from this source's category
            source_categories = source_choice.get("nameCategories", {})
            entries = source_categories.get(category, [])
            if not entries:
                # Slot category missing in source — fall back to anchor
                if anchor_resolved is None:
                    anchor_qualified = resolve_nameset_ref(anchor_source["nameset"], current_namespace=aggregate_namespace)
                    anchor_resolved = custom_namesets.get(anchor_qualified)
                source_categories = anchor_resolved.get("nameCategories", {})
                entries = source_categories.get(category, [])
            if not entries:
                continue

            effective_gender = token.get("gender") or gender
            if effective_gender and any(e.get("gender") for e in entries):
                entries = filter_by_gender(entries, effective_gender, category)
            entries = filter_by_tags(entries, tag_filter, category)
            entry = select_weighted(entries)
            result.append(entry["name"])
        elif token["type"] == "random":
            if "range" in token:
                result.append(generate_range(token["range"][0], token["range"][1]))
            elif "pattern" in token:
                result.append(generate_pattern(token["pattern"]))
        elif token["type"] == "optional":
            # For now, skip optional handling in slot-aware generation
            # (Optional sections can use the anchor source's categories)
            pass

    return " ".join("".join(result).split())
```

In `generate_from_aggregate`, branch on whether `slots` is present:

```python
if "slots" in nameset:
    name = build_aggregate_name_with_slots(
        nameset_id, selected_gender, format_name=format_name,
        tag_filter=tag_filter, source_label=source_label
    )
    label = source_label or "(slot-aware)"
else:
    # Existing path for v1 aggregates
    ...
```

**Step 5: Run tests**

```bash
python -m unittest tests.test_namegen_slots -v
python tests/run_tests.py
```

Expected: All pass (slot policies + baseline).

**Step 6: Commit**

```bash
git add scripts/ tests/
git commit -m "feat(namegen): slot policies for aggregates (inherit/independent/mix/forced)"
```

### Task 4.4: Per-source overrides (genderWeights, filter)

**Files:**
- Modify: `scripts/namegen.py` — apply per-source overrides during generation
- Test: `tests/test_namegen_overrides.py`
- Fixture: extend `tests/fixtures-aggregates/namesets/slot-policies.json`

**Step 1: Add fixture**

Add to `slot-policies.json`:

```json
{
  "id": "override-test",
  "type": "aggregate",
  "formats": {"default": "{firstName} {lastName}"},
  "sources": [
    {
      "nameset": "japanese-test",
      "weight": 100,
      "label": "ja-male-only",
      "override": {
        "genderWeights": {"male": 100, "female": 0}
      }
    }
  ]
}
```

(Add to existing `namesets` array in the file.)

**Step 2: Write failing test**

`tests/test_namegen_overrides.py`:

```python
"""Per-source overrides on aggregate sources."""
import random
import unittest
from pathlib import Path

import namegen


class TestPerSourceOverrides(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures_root = Path(__file__).parent / "fixtures-aggregates"
        namegen.discover_namesets(fixtures_root)

    def setUp(self):
        random.seed(42)

    def test_override_gender_weights(self):
        # override-test forces male-only via per-source override
        for _ in range(30):
            names = namegen.generate_from_aggregate("test:override-test", count=1)
            first = names[0].split()[0]
            self.assertEqual(first, "Hiroshi")  # only male in japanese-test
```

**Step 3: Run, verify failure**

```bash
python -m unittest tests.test_namegen_overrides -v
```

Expected: FAIL — override not applied; both Hiroshi and Yuki appear.

**Step 4: Implement**

In `generate_from_aggregate`, after picking a source, check `selected.get("override")`:

```python
override = selected.get("override", {})
if "genderWeights" in override:
    effective_gender_weights = override["genderWeights"]
    selected_gender = gender if gender else select_gender(effective_gender_weights)
else:
    selected_gender = gender if gender else select_gender(gender_weights)

if "filter" in override:
    effective_tag_filter = (tag_filter or []) + override["filter"]
else:
    effective_tag_filter = tag_filter
```

Pass `effective_tag_filter` instead of `tag_filter` to the source generation call.

For the slot-aware path, look up `selected["override"]` for the anchor and for each per-slot rolled source, applying overrides at the entry-filtering step.

**Step 5: Run tests**

```bash
python tests/run_tests.py
```

Expected: All pass.

**Step 6: Commit**

```bash
git add scripts/ tests/
git commit -m "feat(namegen): per-source overrides (genderWeights, filter)"
```

---

## Phase 5: Inheritance / Extends

### Task 5.1: Extends resolution + add/remove

**Files:**
- Modify: `scripts/namegen.py` — add `resolve_extends` function called during discovery
- Test: `tests/test_namegen_extends.py`
- Fixture: `tests/fixtures-extends/namesets/`

**Step 1: Create fixtures**

`tests/fixtures-extends/namesets/parent.json`:

```json
{
  "namespace": "test",
  "id": "parent",
  "design": {"convention": "Base convention"},
  "tags": ["base"],
  "nameCategories": {
    "firstName": [
      {"name": "Alpha", "gender": "male"},
      {"name": "Beta", "gender": "female"},
      {"name": "ToRemove", "gender": "unisex"}
    ],
    "lastName": [
      {"name": "Original"}
    ]
  },
  "formats": {"default": "{firstName} {lastName}"}
}
```

`tests/fixtures-extends/namesets/child.json`:

```json
{
  "namespace": "test",
  "id": "child",
  "extends": "parent",
  "design": {"convention": "Child convention"},
  "nameCategories": {
    "firstName": {
      "add": [{"name": "Gamma", "gender": "male"}],
      "remove": ["ToRemove"]
    }
  }
}
```

`tests/fixtures-extends/namesets/grandchild.json`:

```json
{
  "namespace": "test",
  "id": "grandchild",
  "extends": "child",
  "tags": ["specialized"]
}
```

**Step 2: Write failing tests**

`tests/test_namegen_extends.py`:

```python
"""Inheritance via extends."""
import random
import unittest
from pathlib import Path

import namegen


class TestExtends(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures_root = Path(__file__).parent / "fixtures-extends"
        namegen.discover_namesets(fixtures_root)

    def test_child_inherits_parent_categories(self):
        child = namegen.custom_namesets["test:child"]
        first_names = [e["name"] for e in child["nameCategories"]["firstName"]]
        self.assertIn("Alpha", first_names)  # inherited
        self.assertIn("Beta", first_names)   # inherited
        self.assertIn("Gamma", first_names)  # added
        self.assertNotIn("ToRemove", first_names)  # removed

    def test_child_inherits_parent_lastnames(self):
        child = namegen.custom_namesets["test:child"]
        last_names = [e["name"] for e in child["nameCategories"]["lastName"]]
        self.assertIn("Original", last_names)

    def test_child_overrides_design(self):
        child = namegen.custom_namesets["test:child"]
        self.assertEqual(child["design"]["convention"], "Child convention")

    def test_child_inherits_tags_when_not_overridden(self):
        child = namegen.custom_namesets["test:child"]
        # child doesn't declare tags; should inherit parent's
        self.assertIn("base", child.get("tags", []))

    def test_grandchild_inherits_through_chain(self):
        grand = namegen.custom_namesets["test:grandchild"]
        first_names = [e["name"] for e in grand["nameCategories"]["firstName"]]
        self.assertIn("Alpha", first_names)
        self.assertIn("Gamma", first_names)
        self.assertNotIn("ToRemove", first_names)
        # grandchild overrides tags
        self.assertEqual(grand["tags"], ["specialized"])

    def test_child_can_be_generated_from(self):
        random.seed(42)
        names = namegen.generate_from_nameset("test:child", count=5)
        self.assertEqual(len(names), 5)
```

**Step 3: Run, verify failure**

```bash
python -m unittest tests.test_namegen_extends -v
```

Expected: FAIL — extends resolution not implemented.

**Step 4: Implement extends resolution**

Add to `scripts/namegen.py`:

```python
def resolve_extends_chain(qualified_id: str, seen: Optional[set] = None) -> Dict:
    """Walk the extends chain and produce a fully-merged nameset.

    Modifies custom_namesets[qualified_id] in place. Idempotent.
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

    # Merge: parent fields are defaults; child fields override; categories use add/remove
    merged = dict(parent)
    # Remove resolved marker so we don't propagate it
    merged.pop("_extends_resolved", None)

    for key, value in nameset.items():
        if key in ("extends",):
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
```

Call `resolve_all_extends()` at the end of `discover_namesets`.

**Step 5: Run tests**

```bash
python tests/run_tests.py
```

Expected: All pass.

**Step 6: Commit**

```bash
git add scripts/ tests/
git commit -m "feat(namegen): inheritance via extends with add/remove on categories"
```

### Task 5.2: Cycle detection test

**Files:**
- Test: append to `tests/test_namegen_extends.py`
- Fixture: `tests/fixtures-extends/namesets/cycle.json`

**Step 1: Create cycle fixture**

`tests/fixtures-extends/namesets/cycle.json`:

```json
{
  "namespace": "test",
  "namesets": [
    {"id": "cycle-a", "extends": "cycle-b", "nameCategories": {"firstName": [{"name": "A"}]}},
    {"id": "cycle-b", "extends": "cycle-a", "nameCategories": {"firstName": [{"name": "B"}]}}
  ]
}
```

**Step 2: Write test**

```python
def test_circular_extends_detected(self):
    # Re-discover with cycle present
    fixtures_root = Path(__file__).parent / "fixtures-extends"
    # Capture stderr to check for the error message
    import io
    from contextlib import redirect_stderr
    buf = io.StringIO()
    with redirect_stderr(buf):
        namegen.discover_namesets(fixtures_root)
    self.assertIn("Circular extends detected", buf.getvalue())
```

**Step 3: Run test**

```bash
python -m unittest tests.test_namegen_extends.TestExtends.test_circular_extends_detected -v
```

Expected: PASS (resolve_extends_chain raises on cycle, resolve_all_extends prints to stderr).

**Step 4: Commit**

```bash
git add tests/
git commit -m "test(namegen): circular extends detection"
```

---

## Phase 6: Variable-depth Chains

Lowest demand, most exotic. Defer if scope creeps. Implementation outline below; expand into bite-sized tasks if proceeding.

### Task 6.1: Parse `{...}*N-M` syntax

**Files:**
- Modify: `scripts/namegen.py` — extend `parse_format` to recognize `{...}*N-M` after a brace group
- Test: `tests/test_namegen_chains.py`

**Step 1: Tests**

`tests/test_namegen_chains.py`:

```python
"""Variable-depth chain syntax {...}*N-M."""
import unittest
import namegen


class TestChainParsing(unittest.TestCase):
    def test_chain_parses_to_repeat_token(self):
        tokens = namegen.parse_format("{firstName}{ tessek}*0-3")
        # First token: placeholder firstName
        self.assertEqual(tokens[0]["type"], "placeholder")
        # Second token: repeat group with min=0, max=3
        self.assertEqual(tokens[1]["type"], "repeat")
        self.assertEqual(tokens[1]["min"], 0)
        self.assertEqual(tokens[1]["max"], 3)


class TestChainBuilding(unittest.TestCase):
    def setUp(self):
        import random
        random.seed(42)

    def test_chain_repeats_within_bounds(self):
        cats = {
            "firstName": [{"name": "X"}],
        }
        for _ in range(20):
            result = namegen.build_name_from_format("{firstName}{ tessek}*0-3", cats)
            count = result.count("tessek")
            self.assertTrue(0 <= count <= 3)
```

**Step 2: Implement parsing**

After parsing a `{...}` group in `parse_format`, peek for `*N-M`:

```python
# After capturing brace content and emitting placeholder/random token:
# Check for chain quantifier
if i < len(format_str) - 2 and format_str[i] == '*':
    chain_match = re.match(r'\*(\d+)-(\d+)', format_str[i:])
    if chain_match:
        # Convert previous token into a repeat group
        prev = tokens.pop()
        tokens.append({
            "type": "repeat",
            "min": int(chain_match.group(1)),
            "max": int(chain_match.group(2)),
            "content": [prev]
        })
        i += chain_match.end()
```

For chain *groups* (multi-token braces), this approach needs an alternative. Alternative cleanest design: treat `{...}` followed by `*N-M` as wrapping the brace's *inner* content, parsed into nested tokens. Implement as needed; refer to existing `optional` token handling for the parsing pattern.

**Step 3: Implement building**

Add to `build_name_from_tokens`:

```python
elif token["type"] == "repeat":
    repeats = random.randint(token["min"], token["max"])
    for _ in range(repeats):
        inner = build_name_from_tokens(token["content"], categories, gender, tag_filter, in_optional=True)
        result.append(inner)
```

**Step 4: Run tests**

```bash
python tests/run_tests.py
```

**Step 5: Commit**

```bash
git add scripts/ tests/
git commit -m "feat(namegen): variable-depth chains via {...}*N-M syntax"
```

---

## Phase 7: Tier 2 UX

### Task 7.1: List overhaul (briefer default, grouped by namespace)

**Files:**
- Modify: `scripts/namegen.py` — `list_namesets` rewrite
- Test: `tests/test_namegen_list_v2.py`

**Step 1: Write tests for grouped output**

`tests/test_namegen_list_v2.py`:

```python
"""Briefer list output, grouped by namespace."""
import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import namegen


class TestListV2(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures_root = Path(__file__).parent / "fixtures-namespaces"
        namegen.discover_namesets(fixtures_root)

    def test_list_groups_by_namespace(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            namegen.list_namesets()
        out = buf.getvalue()
        # Should have a "metropolitan" group header and "test" group header
        self.assertIn("metropolitan", out)
        self.assertIn("test", out)
        # Check ordering: namespace headers should appear once each
        self.assertEqual(out.count("metropolitan ("), 1)

    def test_list_brief_no_per_nameset_detail(self):
        # Brief output should NOT include "Setting:" or "Description:" lines by default
        buf = io.StringIO()
        with redirect_stdout(buf):
            namegen.list_namesets()
        self.assertNotIn("Description:", buf.getvalue())

    def test_list_verbose_includes_detail(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            namegen.list_namesets(verbose=True)
        # verbose should show more detail (existing v1 format)
        # Specific check: shows "Type:" for aggregates
        out = buf.getvalue()
        # only if there are aggregates in the fixtures
```

**Step 2: Implement**

Rewrite `list_namesets`:

```python
def list_namesets(namespace_filter=None, show_hidden=False, verbose=False, tag_filter=None, setting_filter=None, type_filter=None):
    if not custom_namesets:
        print("No namesets found")
        return

    # Group by namespace
    by_ns = {}
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
            items = [t for t in items if t[1].get("type") == type_filter or (type_filter == "simple" and "type" not in t[1] and "nameGroups" not in t[1]) or (type_filter == "grouped" and "nameGroups" in t[1])]

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
                # Old detailed format
                print(f"\n  {full_id}")
                if data.get("name"):
                    safe_print(f"    Name: {data['name']}")
                # ... etc, restore v1 detail ...
        else:
            # Brief: just IDs comma-separated
            ids = ", ".join(bare for bare, _, _ in sorted(shown))
            print(f"  {ids}")
```

CLI: parse `--verbose`, `--tag`, `--setting`, `--type` flags.

**Step 3: Run tests, then smoke-test in real campaigns**

```bash
python tests/run_tests.py
cd ../solorpg
python ../rpg-tools/scripts/namegen.py list 2>&1 | head -40
python ../rpg-tools/scripts/namegen.py list --verbose 2>&1 | head -20
cd ../rpg-tools
```

**Step 4: Commit**

```bash
git add scripts/ tests/
git commit -m "feat(namegen): briefer list grouped by namespace, with --verbose/--tag/--setting/--type filters"
```

### Task 7.2: Validate command

**Files:**
- Modify: `scripts/namegen.py` — add `validate` subcommand
- Test: `tests/test_namegen_validate.py`

**Step 1: Tests**

`tests/test_namegen_validate.py`:

```python
"""Validate command for nameset linting."""
import io
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

import namegen


class TestValidate(unittest.TestCase):
    def test_broken_aggregate_ref_reported(self):
        fixtures_root = Path(__file__).parent / "fixtures-aggregates"
        namegen.discover_namesets(fixtures_root)
        out_buf = io.StringIO()
        with redirect_stdout(out_buf):
            errors, warnings = namegen.validate_all()
        self.assertTrue(any("nonexistent-source" in e for e in errors))

    def test_undefined_format_placeholder_reported(self):
        fixtures_root = Path(__file__).parent / "fixtures-formats-bad"
        namegen.discover_namesets(fixtures_root)
        # Add fixture with format referencing undefined category
        # Then check errors include warning about undefined category
        out_buf = io.StringIO()
        with redirect_stdout(out_buf):
            errors, warnings = namegen.validate_all()
        # Test depends on fixture content — write fixture to match assertion
```

**Step 2: Implement validate**

```python
def validate_all() -> Tuple[List[str], List[str]]:
    errors = []
    warnings = []
    known_namespaces = set()
    for full_id in custom_namesets:
        ns, _ = full_id.split(":", 1)
        if ns:
            known_namespaces.add(ns)

    for full_id, nameset in custom_namesets.items():
        ns = full_id.split(":", 1)[0]

        # Check aggregate sources
        if nameset.get("type") == "aggregate":
            for source in nameset.get("sources", []):
                ref = source.get("nameset")
                resolved = resolve_nameset_ref(ref, current_namespace=ns) if ref else None
                if not resolved:
                    errors.append(f"{full_id} — source '{ref}' not found")

        # Check format placeholders
        formats = nameset.get("formats")
        if formats:
            categories = nameset.get("nameCategories", {}).keys()
            for fname, fdef in formats.items():
                template = fdef if isinstance(fdef, str) else fdef.get("template", "")
                tokens = parse_format(template)
                for tok in _flatten_tokens(tokens):
                    if tok["type"] == "placeholder":
                        cat = tok["value"]
                        if cat not in categories and nameset.get("type") != "aggregate":
                            warnings.append(f"{full_id} — format '{fname}' references undefined category '{{{cat}}}'")

        # Legacy format usage
        if "format" in nameset and "formats" not in nameset:
            warnings.append(f"{full_id} — uses legacy 'format' field, suggest migration to 'formats' map")

    print(f"\n✓ {len(custom_namesets)} namesets validated, {len(errors)} errors, {len(warnings)} warnings")
    for e in errors:
        print(f"✗ {e}")
    for w in warnings:
        print(f"⚠ {w}")
    return errors, warnings


def _flatten_tokens(tokens):
    for t in tokens:
        yield t
        if t["type"] == "optional":
            yield from _flatten_tokens(t["content"])
        elif t["type"] == "repeat":
            yield from _flatten_tokens(t["content"])
```

CLI: add `validate` subcommand in `main()`.

**Step 3: Run tests + smoke-test**

```bash
python tests/run_tests.py
cd ../solorpg
python ../rpg-tools/scripts/namegen.py validate 2>&1 | head -30
cd ../rpg-tools
```

**Step 4: Commit**

```bash
git add scripts/ tests/
git commit -m "feat(namegen): validate command for nameset linting"
```

### Task 7.3: --explain flag

**Files:**
- Modify: `scripts/namegen.py` — wire an `explain` mode through generation paths
- Test: `tests/test_namegen_explain.py`

**Step 1: Tests**

```python
"""--explain dump."""
import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import namegen


class TestExplain(unittest.TestCase):
    def test_explain_aggregate_shows_source_pick(self):
        fixtures_root = Path(__file__).parent / "fixtures-aggregates"
        namegen.discover_namesets(fixtures_root)
        buf = io.StringIO()
        with redirect_stdout(buf):
            namegen.generate_from_aggregate("test:diaspora-test", count=1, explain=True)
        out = buf.getvalue()
        self.assertIn("source pick", out.lower())
        self.assertIn("slot", out.lower())
```

**Step 2: Implement**

Thread an `explain=False` parameter through generation functions. When `explain=True`, print trace lines at each decision point. Keep the trace concise (one line per decision).

**Step 3: Run tests + commit**

```bash
python tests/run_tests.py
git add scripts/ tests/
git commit -m "feat(namegen): --explain dumps assembly trace"
```

---

## Phase 8: Documentation + Templates

### Task 8.1: Templates

**Files:**
- Create: `references/templates/simple.json`
- Create: `references/templates/aggregate.json`
- Create: `references/templates/grouped.json`
- Create: `references/templates/multi-nameset.json`
- Create: `references/templates/extends.json`

**Step 1: Write templates**

Each template is a heavily-commented JSON file (use `_comment` keys for inline documentation since JSON doesn't support real comments). Cover all the new fields with realistic examples.

**Step 2: Commit**

```bash
git add references/templates/
git commit -m "docs(namegen): templates for v2 nameset formats"
```

### Task 8.2: Guide rewrite

**Files:**
- Modify: `references/nameset-guide.md`

**Step 1: Restructure the guide**

Add new sections in order:
1. Quick reference (top of doc, all commands at-a-glance)
2. Namespaces & file layout
3. Schema (with all new fields)
4. Format strings (including new variants and chains)
5. Per-entry tags and filtering
6. Aggregates v2 (slot policies, overrides, nesting)
7. Inheritance / extends
8. Validation
9. Migration appendix (v1 → v2 examples)
10. Templates reference

Use the design doc as source material; rewrite for end-user reading rather than design rationale.

**Step 2: Commit**

```bash
git add references/nameset-guide.md
git commit -m "docs(namegen): rewrite nameset guide for v2"
```

---

## Phase 9: Real-Campaign Validation

Before merging back to develop.

### Task 9.1: Migrate one campaign as a smoke test

**Step 1: Pick a small campaign (e.g. Aegis or Threadlight) and migrate one or two namesets to v2 format.**

Add namespace, convert format → formats, add tags, mark hidden if appropriate. Verify generation still works.

```bash
cd ../solorpg
python ../rpg-tools/scripts/namegen.py validate
python ../rpg-tools/scripts/namegen.py list --namespace aegis
python ../rpg-tools/scripts/namegen.py full --nameset aegis:american-1940s --count 5
cd ../rpg-tools
```

**Step 2: If issues surface, add regression tests for them and fix.**

**Step 3: Commit any test additions.**

### Task 9.2: Run all existing campaigns through validate

Catch any incompatibilities the test fixtures didn't surface.

```bash
cd ../solorpg
python ../rpg-tools/scripts/namegen.py validate 2>&1 | tee /tmp/validate-report.txt
```

Triage anything reported. Most issues should be warnings about legacy format usage (expected, harmless).

---

## Phase 10: Bundle + PR

### Task 10.1: Update SKILL.md

**Files:**
- Modify: `SKILL.md` (if it documents namegen behavior)

Update any references to namegen behavior to reflect v2 capabilities.

### Task 10.2: Run bundle build

```bash
python bundle.py
```

Expected: builds `rpg-tools.skill` without errors.

### Task 10.3: Push branch and create PR

```bash
git push -u origin feature/namegen-v2
gh pr create --base develop --title "feat(namegen): v2 data model overhaul" --body "$(cat <<'EOF'
## Summary
- Namespaces (`namespace:id`) for nameset organization
- Multi-nameset files; flexible file layout (one or many namesets per JSON)
- Formalized `design` block for cultural/phonological metadata
- Named format variants with `when` documentation
- Per-entry `tags` array with `--filter` (AND semantics)
- Inheritance via `extends` with `add`/`remove` on categories
- Aggregate v2: nested aggregates, slot policies, per-source overrides, source filtering, graceful degradation
- Variable-depth chain syntax `{...}*N-M`
- New `validate` command and `--explain` flag
- Briefer `list` output with `--verbose`, `--namespace`, `--tag`, `--setting`, `--type` filters

Full design rationale: `docs/plans/2026-04-18-namegen-v2-design.md`
Full implementation plan: `docs/plans/2026-04-18-namegen-v2-implementation.md`

All v1 namesets continue to work unchanged. Migration is opt-in per nameset.

## Test plan
- [x] All baseline tests pass (regression locked v1 behavior)
- [x] All new feature tests pass
- [x] Validate command run against all real campaigns in `../solorpg`
- [x] Smoke-tested name generation across migrated and unmigrated namesets
- [x] Bundle build succeeds

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Notes for the Implementer

- **Incremental commits.** Every task ends in a commit. Don't batch.
- **Tests first, every time.** The TDD cycle (failing test → implement → passing test → commit) is mandatory; the existing namegen.py has no test coverage so this is your only safety net.
- **Don't over-refactor.** Each task changes the smallest scope possible. The temptation to "clean up while you're in there" will burn time and break things.
- **When in doubt, look at the design doc.** `docs/plans/2026-04-18-namegen-v2-design.md` is the source of truth for *what*. This document is the source of truth for *how*.
- **Smoke-test in real campaigns.** After any nontrivial change, run `python scripts/namegen.py list` and `python scripts/namegen.py full --nameset <something>` against `../solorpg/` to catch surprises the fixtures missed.
- **Backward compatibility is sacred.** Every existing v1 nameset must still load and generate correctly. The baseline regression tests guard this; if any of them fail, stop and figure out why before adding more code.
