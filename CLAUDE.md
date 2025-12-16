# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Portable RPG tools for solo RPG sessions with Claude. Provides dice rolling, tarot draws, oracles, name generation, and campaign data management (characters, locations, memories, stories).

## Running Tools

All tools are standalone Python scripts in `scripts/`. Run directly:

```bash
python scripts/dice.py "2d6+5"
python scripts/tarot.py 3
python scripts/oracle.py axis
python scripts/namegen.py list
python scripts/characters.py list
python scripts/locations.py tree
python scripts/memories.py list --campaign NAME
python scripts/stories.py meta --campaign NAME
```

No dependencies beyond Python standard library. No build step, no tests, no linting.

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
- `guides/nameset-guide.md` - Nameset format with weighted categories
- `guides/story-capture-guide.md` - Story collection structure

## Modifiers

Optional behavior modifiers in `modifiers/` can be loaded during sessions:
- `modifiers/mature-content.md` - For authentic dark themes
- `modifiers/combat-realism.md` - For grounded, consequential violence

## Git Branching

- **main** - Stable branch. Skill packages are built from here.
- **develop** - Integration branch. Features merge here first.
- **feature/*** - Short-lived feature branches off `develop`, merged back when complete.

Flow: `feature/xyz` → `develop` → `main`
