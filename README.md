# rpg-tools

Portable RPG tools for solo RPG sessions with Claude. Provides dice rolling, tarot draws, name generation, and campaign data management.

## Installation

### Claude Desktop (claude.ai)

1. Run `./build-skill.sh` to create `rpg-tools.skill`
2. Upload the skill file to Claude Desktop

### Claude Code / Local Use

Run scripts directly from the `scripts/` directory:

```bash
python scripts/dice.py 2d6+5
python scripts/tarot.py 3
python scripts/namegen.py list
```

## Tools

| Tool | Purpose |
|------|---------|
| `dice.py` | Roll20-compatible dice notation |
| `tarot.py` | Tarot card draws (1-10 cards) |
| `namegen.py` | Name generation from custom namesets |
| `stories.py` | Story collection retrieval |
| `characters.py` | Character data loading |
| `locations.py` | Location data with hierarchy |
| `memories.py` | Campaign memory tracking |
| `oracle.py` | Multi-system oracle (tarot, runes, I Ching, fate) |

### Dice Rolling

Roll20-compatible notation with full modifier support.

```bash
python scripts/dice.py "2d6+5"        # Basic roll with modifier
python scripts/dice.py "4d6kh3"       # Keep highest 3 (ability scores)
python scripts/dice.py "2d20kh1+5"    # Advantage
python scripts/dice.py "8d6!"         # Exploding dice
python scripts/dice.py "4dF"          # Fudge/Fate dice
python scripts/dice.py "6d10>=7"      # Count successes
```

### Tarot

```bash
python scripts/tarot.py         # Single card
python scripts/tarot.py 3       # Three-card spread
python scripts/tarot.py 5       # Five-card spread
```

### Oracle

Multi-system oracle for injecting randomness.

```bash
python scripts/oracle.py axis              # Multi-axis reading
python scripts/oracle.py omni              # Full reading (all systems)
python scripts/oracle.py tarot [n]         # Draw tarot card(s)
python scripts/oracle.py rune [n]          # Draw Elder Futhark rune(s)
python scripts/oracle.py iching            # Cast I Ching hexagram
python scripts/oracle.py fate [likelihood] # Yes/no oracle
python scripts/oracle.py prompt            # Action + Theme word pair
```

### Name Generation

```bash
python scripts/namegen.py list                              # Show available namesets
python scripts/namegen.py full --nameset ice-age-names      # Generate one name
python scripts/namegen.py full --nameset NAME --count 5     # Multiple names
```

### Characters, Locations, Memories

Load campaign data on-demand. Requires JSON files in the appropriate directories.

```bash
python scripts/characters.py list                    # List characters
python scripts/characters.py get NAME --depth full   # Get full profile
python scripts/locations.py tree                     # Show location hierarchy
python scripts/memories.py list --campaign NAME      # List all memories
```

## Data Requirements

The tools look for data in these locations (relative to script parent):
- `namesets/` - Name collection JSON files
- `stories/` - Story collection JSON files
- `characters/` - Character profile JSON files
- `locations/` - Location profile JSON files
- `memories/` - Memory record JSON files

## Guides

- [Creating Characters](guides/character-guide.md)
- [Creating Locations](guides/location-guide.md)
- [Creating Namesets](guides/nameset-guide.md)
- [Capturing Stories](guides/story-capture-guide.md)
- [Session Setup](guides/session-setup-guide.md)
- [Session Debrief](guides/session-debrief-guide.md)

## Optional Skills

The `skills/` folder contains optional Claude Code skills:
- `character-creator.md` - Agent for creating character JSON files

## Building the Skill Package

```bash
./build-skill.sh              # Creates rpg-tools.skill
./build-skill.sh output.skill # Custom output path
```
