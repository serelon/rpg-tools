# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Portable RPG tools for solo RPG sessions with Claude. Provides dice rolling, tarot draws, oracles, name generation, and campaign data management (characters, locations, memories, stories).

## Tools

All tools are standalone Python scripts in `scripts/`. No dependencies beyond Python standard library. No build step, no tests, no linting.

**Instant Tools** (work immediately, no data files):
- `dice.py` - Roll20-compatible dice notation
- `tarot.py` - Tarot card draws
- `oracle.py` - Multi-system oracle (axis, runes, I Ching, fate, prompts)
- `pool.py` - Pool/deck management (needs `pools/` for definitions)

**Campaign Tools** (require JSON data files):
- `namegen.py` - Name generation (needs `namesets/`)
- `characters.py` - Character profiles (needs `characters/`)
- `locations.py` - Location profiles (needs `locations/`)
- `stories.py` - Story collections (needs `stories/`)
- `memories.py` - Memory tracking (needs `memories/`)
- `log.py` - Session logging with automatic changelog generation (needs `campaign/`)
- `campaign.py` - Campaign state management and queries (needs `campaign/`)

## Building the Skill Package

For Claude Desktop deployment:
```bash
python bundle.py              # Creates rpg-tools.skill (cross-platform)
./build-skill.sh              # Alternative (requires bash + zip)
```

## Architecture

See `docs/architecture.md` for detailed documentation of the data tool patterns.

**Shared library** - Campaign tools share common code in `scripts/lib/`:
- `discovery.py` - Multi-path data file discovery
- `lookup.py` - Item search by ID/name with fuzzy matching
- `parsers.py` - Era and session string parsing
- `changelog.py` - Automatic changelog generation from session logs
- `calendars/` - Modular calendar system for date conversion

**Instant tools** (dice, tarot, oracle, pool) remain fully standalone with no imports.

**Data patterns** - Tools follow a read-anywhere, write-canonical pattern:
- **Discovery**: Searches 7 locations, merges all found data (see `docs/architecture.md`)
- **Write**: New items go to `{cwd}/{data_type}/{id}.json`
- **Update**: Find original file, modify in place

**Tiered data loading** - Character and location tools use progressive disclosure: minimal profiles load by default, with `--depth full` or `--section NAME` for additional detail. This minimizes context consumption during RPG sessions.

**SKILL.md** - Entry point for Claude Desktop skill. Contains tool documentation and links to guides. When deployed as a skill, Claude reads this file to understand available tools.

## Data Directories

Campaign data is NOT included in this repo. Tools expect JSON files in the appropriate directories. See `references/` for JSON schemas:
- `references/character-guide.md` - Character JSON structure
- `references/location-guide.md` - Location JSON with hierarchy/connections
- `references/memories-guide.md` - Memory JSON with cross-references
- `references/nameset-guide.md` - Nameset format with weighted categories
- `references/story-capture-guide.md` - Story collection structure
- `references/oracle-guide.md` - Oracle types and usage patterns
- `references/pool-guide.md` - Pool/deck management with state tracking
- `references/campaign-state-guide.md` - Campaign state system and session logging

## Modifiers

Optional behavior modifiers in `modifiers/` can be loaded during sessions:
- `modifiers/mature-content.md` - For authentic dark themes
- `modifiers/combat-realism.md` - For grounded, consequential violence

## Git Branching

- **develop** - Default branch. Active development happens here.
- **stable** - Release branch. Skill packages are built from here.
- **feature/*** - Short-lived feature branches off `develop`, merged back when complete.

Flow: `feature/xyz` → `develop` → `stable`

## Workflow

- Always create a feature branch before implementing changes from plan mode.
- When creating PRs that fix issues, include "Closes #N" in the PR body to auto-close on merge.
- After merging, verify related issues are closed. If not auto-closed, close them manually with a comment referencing the PR.

## Deferred / Tech Debt

### Nameset schema

- **Nested namespaces** — Current resolver enforces exactly two segments (`namespace:id`, single colon). In practice, campaigns like Emberfall would benefit from nesting (`emberfall:caldworth:humans`, `emberfall:velundhar:*`) to represent sub-settings within a campaign scope. Supporting this would require: multi-segment key format, resolver walking up the hierarchy for bare-ref fallback, and guide/docs reflow. Non-trivial. Until then, sub-settings fold into campaign namespace with tags for disambiguation.
- **Nameset-guide examples** — The "Setting" row in the Recommended Namespace Taxonomy table (`references/nameset-guide.md`) uses `valdran`, `caldworth`, `solramis` as examples of "specific worlds shared across campaigns." In practice these are all scoped *inside* a single campaign namespace — the "shared across campaigns" criterion isn't the real use case. Either drop the examples, replace with genuinely-shared examples (if any exist), or restructure the tier to reflect how settings actually get scoped.
