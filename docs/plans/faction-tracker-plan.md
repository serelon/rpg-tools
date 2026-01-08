# Faction Tracker Implementation Plan

## Overview
Build `factions.py` - a tool to track factions as characters with agency. Supports hierarchical organizations, relationships, economy, and member management.

**Primary use cases:**
- Delacroix Fleet (tight, ~40 members, economic focus)
- INS Leviathan (ship, ~1,200 abstracted, military structure)
- House Verdania (vast, key figures only, opposing subfactions)

---

## Phase 1: Foundation

### 1.1 Create faction schema and base file structure
- [ ] Create `references/faction-guide.md` documenting the full schema
- [ ] Define minimal/full/sections tiers
- [ ] Document relationship edge types and their schemas
- [ ] Include examples for each scale (tight/ship/vast)

### 1.2 Create `scripts/factions.py` skeleton
- [ ] Set up argument parser with all planned commands (stubbed)
- [ ] Import shared lib (discovery, lookup, persistence, changelog)
- [ ] Implement `discover_factions()` using existing patterns
- [ ] Test discovery finds faction JSON files

### 1.3 Implement core CRUD commands
- [ ] `list` - show all factions with optional filters (--type, --tag)
- [ ] `get` - retrieve faction with tiered loading (--depth, --section)
- [ ] `create` - create new faction with required fields
- [ ] `update` - update field with changelog integration
- [ ] `delete` - remove faction (with reference check)

**Checkpoint:** Can create, read, update, delete faction files. Changelog records changes.

---

## Phase 2: Hierarchy & Members

### 2.1 Implement subfaction hierarchy
- [ ] Support `parent` field linking subfactions
- [ ] `tree` command - show faction hierarchy with depth control
- [ ] Handle `autonomous` flag per subfaction
- [ ] Validate parent references exist

### 2.2 Implement member management
- [ ] `members` command - list affiliated characters
- [ ] Query characters by faction/subfaction field
- [ ] Support named members, named units, abstract pools
- [ ] `add-member` command with bidirectional sync
- [ ] `remove-member` command with bidirectional sync
- [ ] Warn on faction/character mismatch

### 2.3 Unit and pool tracking
- [ ] Define unit schema (count, morale, role, location, linked_members)
- [ ] Define pool schema (description, count, state)
- [ ] Include units in `members` output
- [ ] Support `--unit UNIT` filter

**Checkpoint:** Can model Leviathan's departments, Marines (unit), and 1,200 crew (pool).

---

## Phase 3: Relationships

### 3.1 Implement relationship edges
- [ ] Define relationship structure (type, target, state, notes)
- [ ] Support typed schemas per relationship type:
  - `debtor` (principal, rate, accruing)
  - `ally` (trust, terms)
  - `enemy` (threat, conflict)
  - `vassal` (obligations)
  - `reports_to` (via, bypasses)
- [ ] Allow freeform extension of any type

### 3.2 Relationship commands
- [ ] `relationships` command - list faction's edges
- [ ] `--type TYPE` filter
- [ ] `add-relationship` command
- [ ] `update-relationship` command (modify state)
- [ ] `remove-relationship` command
- [ ] Validate target exists (faction or character)

### 3.3 Sibling relationships
- [ ] Allow relationships between subfactions of same parent
- [ ] Model opposing subfactions (rivals within House)

**Checkpoint:** Can model Perseverance's 5M debt to Delacroix, Delacroix-Verdania Letter of Marque relationship.

---

## Phase 4: Economy Submodule

### 4.1 Account tracking
- [ ] Define account schema (id, category, balance, interest?, notes)
- [ ] Categories: liquid, receivables, payables, other
- [ ] Interest calculation for loans
- [ ] `economy FACTION --accounts` output

### 4.2 Running costs
- [ ] Define cost schema (id, description, amount, formula?)
- [ ] Support line items that sum
- [ ] Optional formula support (crew = headcount * rate)
- [ ] `economy FACTION --costs` output
- [ ] Calculate monthly burn rate

### 4.3 Inventory management
- [ ] Define inventory schema (item, qty, value?, location?, legality?, notes)
- [ ] Default legality = legal unless specified
- [ ] `economy FACTION --inventory` output
- [ ] Optional location tracking (which subfaction/ship)

### 4.4 Asset tracking
- [ ] Define asset schema (id, name, type, value, details{})
- [ ] Freeform details for complex assets (ships, properties)
- [ ] Assets with value feed into economy summary

### 4.5 Economy summary
- [ ] `economy FACTION` (no flag) shows summary:
  - Total liquid
  - Total receivables
  - Total payables
  - Net worth
  - Monthly burn
  - Runway (liquid / burn)
- [ ] `economy FACTION --summary` explicit

**Checkpoint:** Can model Delacroix's 400k liquid, 500k debt, 230k burn, 3-week runway.

---

## Phase 5: Resources & Polish

### 5.1 Faction-defined resources
- [ ] `resources` section with arbitrary categories
- [ ] Examples: supply, ammunition, jumps, environmental
- [ ] Optional depletion tracking (capacity vs current)
- [ ] Include in `get --depth full` output

### 5.2 Output formatting
- [ ] JSON output (default, structured)
- [ ] Markdown output (`--format md`) for human reading
- [ ] Tiered output respects depth flag

### 5.3 Validation and warnings
- [ ] Validate parent faction exists
- [ ] Validate relationship targets exist
- [ ] Validate member characters exist
- [ ] Warn on character faction field mismatch
- [ ] Warn on orphaned subfactions

### 5.4 Integration with existing tools
- [ ] Update `characters.py` to support `--faction` filter (if not present)
- [ ] Ensure changelog integration works for all updates
- [ ] Test with log tool event references

**Checkpoint:** Full-featured faction tool working with all three test cases.

---

## Phase 6: Test & Document

### 6.1 Create test data
- [ ] Create `factions/delacroix-fleet.json` from savefile data
- [ ] Create `factions/leviathan.json` from reference docs
- [ ] Create `factions/house-verdania.json` (sketch)
- [ ] Create `factions/perseverance.json` as allied subfaction

### 6.2 Update SKILL.md
- [ ] Add factions.py to tool list
- [ ] Document all commands with examples
- [ ] Link to faction-guide.md

### 6.3 Update references
- [ ] Cross-reference from character-guide.md
- [ ] Cross-reference from location-guide.md
- [ ] Add faction field documentation

---

## Task Sizing

| Phase | Tasks | Complexity |
|-------|-------|------------|
| Phase 1: Foundation | 4 major | Medium - follows existing patterns |
| Phase 2: Hierarchy | 3 major | Medium - new concepts |
| Phase 3: Relationships | 3 major | Medium - edge system |
| Phase 4: Economy | 5 major | High - most novel code |
| Phase 5: Polish | 4 major | Low-Medium - refinement |
| Phase 6: Test | 3 major | Low - documentation |

**Recommended order:** Phases 1-3 first (core structure), then Phase 4 (economy), then 5-6 (polish).

---

## Dependencies

- `scripts/lib/discovery.py` - reuse for faction discovery
- `scripts/lib/lookup.py` - reuse for find_item
- `scripts/lib/persistence.py` - reuse for save/delete
- `scripts/lib/changelog.py` - reuse for update logging
- `scripts/characters.py` - reference implementation, bidirectional sync target

---

## Open Questions (Deferred)

1. **Filter system for large factions** - exclude/include subfactions by tag
2. **Spoils calculation** - currently reference doc, could be structured data
3. **12th Fleet order of battle** - 1,200 ships in abstract, extreme scale test
4. **Formula DSL for costs** - how complex should formulas get?

---

## Success Criteria

- [ ] Can fully model Delacroix Fleet with economy
- [ ] Can model Leviathan with departments, units, pools
- [ ] Can model House Verdania at abstract scale
- [ ] Can model Perseverance as allied subfaction with debt
- [ ] Bidirectional character sync works without data loss
- [ ] All updates logged to changelog
- [ ] Markdown export readable as faction "character sheet"
