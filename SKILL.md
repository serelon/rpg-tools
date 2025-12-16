---
name: rpg-tools
description: Solo RPG mechanical tools for dice rolling, tarot draws, name generation, and story/folklore retrieval. Use when the user asks to roll dice, draw tarot cards, generate character names, or pull from story collections during RPG sessions.
---

# RPG Tools

Mechanical tools for solo RPG sessions. Run scripts from `scripts/`.

## Dice Rolling

Roll20-compatible notation with full modifier support.

```bash
python scripts/dice.py "2d6+5"        # Basic roll with modifier
python scripts/dice.py "4d6kh3"       # Keep highest 3 (ability scores)
python scripts/dice.py "2d20kh1+5"    # Advantage
python scripts/dice.py "8d6!"         # Exploding dice
python scripts/dice.py "4dF"          # Fudge/Fate dice
python scripts/dice.py "6d10>=7"      # Count successes
```

Supports: `kh/kl` (keep), `dh/dl` (drop), `r/rr` (reroll), `!` (exploding), `!!` (compounding), `!p` (penetrating), comparison operators for success counting.

## Tarot

Draw cards for oracular guidance.

```bash
python scripts/tarot.py         # Single card
python scripts/tarot.py 3       # Three-card spread (past/present/future)
python scripts/tarot.py 5       # Five-card spread
```

Max 10 cards per draw. Full 78-card deck (Major + Minor Arcana).

## Name Generation

Generate names from campaign namesets. **Requires nameset JSON files** in `namesets/` directory relative to script parent.

```bash
python scripts/namegen.py list                              # Show available namesets
python scripts/namegen.py full --nameset ice-age-names      # Generate one name
python scripts/namegen.py full --nameset early-neolithic-names --count 5
```

Namesets define format strings (e.g., `{firstName} {epithet}`) and weighted name categories.

## Story Collections

Retrieve folklore and character stories. **Requires story JSON files** in `stories/` directory relative to script parent.

```bash
python scripts/stories.py meta --campaign SESSION           # Show available tags/counts
python scripts/stories.py list --campaign SESSION           # List all stories
python scripts/stories.py random --campaign SESSION         # Random story
python scripts/stories.py random --campaign SESSION --theme loss --mood melancholic
python scripts/stories.py show --campaign SESSION --story STORY_ID
```

Filter options: `--collection`, `--theme`, `--mood`, `--era`

## Characters

Load character profiles on-demand. **Requires character JSON files** in `characters/` directory relative to script parent.

```bash
python scripts/characters.py list                        # List character names
python scripts/characters.py list --short                # Show minimal profiles
python scripts/characters.py get NAME                    # Get minimal profile
python scripts/characters.py get NAME --depth full       # Get full profile
python scripts/characters.py get NAME --section powers   # Get specific section
python scripts/characters.py sections NAME               # List available sections
```

Filter options: `--faction`, `--subfaction`, `--tag`

## Locations

Load location profiles with hierarchy/graph support. **Requires location JSON files** in `locations/` directory relative to script parent.

```bash
python scripts/locations.py list                         # List all locations
python scripts/locations.py list --tag settlement        # Filter by tag
python scripts/locations.py list --parent LOCATION       # List children
python scripts/locations.py tree                         # Show full hierarchy
python scripts/locations.py tree LOCATION                # Show subtree
python scripts/locations.py get NAME                     # Get minimal profile
python scripts/locations.py get NAME --depth full        # Get full profile
python scripts/locations.py path NAME                    # Show path from root
python scripts/locations.py connections NAME             # Show all connections
```

Filter options: `--tag`, `--parent`, `--type`

---

## Session Workflow

Guides for before and after play:

- **[Session Setup](guides/session-setup-guide.md)** - Calibrate tone, direction, and pacing before starting
- **[Session Debrief](guides/session-debrief-guide.md)** - Post-session reflection for closure and character growth

**Optional modifiers** to load when needed:
- [Mature Content](modifiers/mature-content.md) - For authentic dark themes
- [Combat Realism](modifiers/combat-realism.md) - For grounded, consequential violence

---

## Content Creation

For creating new campaign content, see the detailed guides:

- **[Creating Namesets](guides/nameset-guide.md)** - Schema and guidelines for building name collections for new cultures/eras
- **[Capturing Stories](guides/story-capture-guide.md)** - Template and workflow for extracting stories from sessions into JSON collections
- **[Creating Characters](guides/character-guide.md)** - Schema and workflow for building character JSON profiles
- **[Creating Locations](guides/location-guide.md)** - Schema and workflow for hierarchical location data
