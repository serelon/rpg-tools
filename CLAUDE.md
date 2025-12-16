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

**Campaign Tools** (require JSON data files):
- `namegen.py` - Name generation (needs `namesets/`)
- `characters.py` - Character profiles (needs `characters/`)
- `locations.py` - Location profiles (needs `locations/`)
- `stories.py` - Story collections (needs `stories/`)
- `memories.py` - Memory tracking (needs `memories/`)

## Building the Skill Package

For Claude Desktop deployment:
```bash
./build-skill.sh              # Creates rpg-tools.skill
```

## Architecture

**Standalone scripts** - Each tool is self-contained with no shared code between scripts. Tools discover campaign data by looking for JSON files in directories relative to the current working directory or script parent:
- `characters/` - Character profile JSON files
- `locations/` - Location profile JSON files
- `memories/` - Memory record JSON files
- `stories/` - Story collection JSON files
- `namesets/` - Name generation JSON files

**Tiered data loading** - Character and location tools use progressive disclosure: minimal profiles load by default, with `--depth full` or `--section NAME` for additional detail. This minimizes context consumption during RPG sessions.

**SKILL.md** - Entry point for Claude Desktop skill. Contains tool documentation and links to guides. When deployed as a skill, Claude reads this file to understand available tools.

## Data Directories

Campaign data is NOT included in this repo. Tools expect JSON files in the appropriate directories. See `guides/` for JSON schemas:
- `guides/character-guide.md` - Character JSON structure
- `guides/location-guide.md` - Location JSON with hierarchy/connections
- `guides/memories-guide.md` - Memory JSON with cross-references
- `guides/nameset-guide.md` - Nameset format with weighted categories
- `guides/story-capture-guide.md` - Story collection structure
- `guides/oracle-guide.md` - Oracle types and usage patterns

## Modifiers

Optional behavior modifiers in `modifiers/` can be loaded during sessions:
- `modifiers/mature-content.md` - For authentic dark themes
- `modifiers/combat-realism.md` - For grounded, consequential violence

## Git Branching

- **main** - Stable branch. Skill packages are built from here.
- **develop** - Integration branch. Features merge here first.
- **feature/*** - Short-lived feature branches off `develop`, merged back when complete.

Flow: `feature/xyz` → `develop` → `main`
