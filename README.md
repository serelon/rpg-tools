# rpg-tools

A toolbox for solo RPG sessions with Claude. Solo RPG is a form of tabletop roleplaying where you play alone, using random generators and oracles to create emergent narrative. These tools handle the mechanical side—dice, oracles, campaign data—so you can focus on the story.

## Installation

### Claude Desktop (claude.ai)

1. Run `./build-skill.sh` to create `rpg-tools.skill`
2. Upload the skill file to Claude Desktop

### Claude Code / Local Use

Run scripts directly from `scripts/`. No dependencies beyond Python standard library.

## Tools

The tools fall into two categories:

### Instant Tools

Work immediately with no setup. All data is embedded.

| Tool | Purpose |
|------|---------|
| `dice.py` | Roll20-compatible dice notation |
| `tarot.py` | Tarot card draws (1-10 cards) |
| `oracle.py` | Multi-system oracle (tarot, runes, I Ching, fate, prompts) |

### Campaign Tools

Require JSON data files in specific directories. See [Campaign Data Structure](#campaign-data-structure).

| Tool | Purpose | Data Directory |
|------|---------|----------------|
| `namegen.py` | Name generation from custom namesets | `namesets/` |
| `characters.py` | Character data loading | `characters/` |
| `locations.py` | Location data with hierarchy | `locations/` |
| `stories.py` | Story collection retrieval | `stories/` |
| `memories.py` | Campaign memory tracking | `memories/` |

---

## Instant Tools

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

Multi-system oracle for injecting randomness. The oracle provides raw symbolic material—Claude interprets it creatively in context.

```bash
python scripts/oracle.py axis              # Multi-axis reading (tone/direction/element/action/twist)
python scripts/oracle.py omni              # Full reading (all systems combined)
python scripts/oracle.py tarot [n]         # Draw tarot card(s)
python scripts/oracle.py rune [n]          # Draw Elder Futhark rune(s)
python scripts/oracle.py iching            # Cast I Ching hexagram
python scripts/oracle.py fate [likelihood] # Yes/no oracle (impossible/unlikely/even/likely/certain)
python scripts/oracle.py prompt            # Action + Theme word pair
```

---

## Campaign Tools

These tools load data from JSON files. See guides for JSON schemas.

### Name Generation

```bash
python scripts/namegen.py list                              # Show available namesets
python scripts/namegen.py full --nameset ice-age-names      # Generate one name
python scripts/namegen.py full --nameset NAME --count 5     # Multiple names
```

### Characters

```bash
python scripts/characters.py list                    # List characters
python scripts/characters.py get NAME                # Get minimal profile
python scripts/characters.py get NAME --depth full   # Get full profile
python scripts/characters.py get NAME --section powers
```

### Locations

```bash
python scripts/locations.py list                     # List all locations
python scripts/locations.py tree                     # Show location hierarchy
python scripts/locations.py get NAME --depth full    # Get full profile
python scripts/locations.py connections NAME         # Show connections
```

### Stories

```bash
python scripts/stories.py meta --campaign NAME       # Show available tags
python scripts/stories.py random --campaign NAME     # Random story
python scripts/stories.py random --campaign NAME --theme loss --mood melancholic
```

### Memories

```bash
python scripts/memories.py list --campaign NAME      # List all memories
python scripts/memories.py random --campaign NAME    # Random memory
python scripts/memories.py search "query" --campaign NAME
python scripts/memories.py character NAME            # Memories involving character
```

---

## Campaign Data Structure

Campaign tools look for JSON files in these directories (relative to working directory):

```
your-campaign/
├── characters/     # Character profile JSON files
├── locations/      # Location profile JSON files
├── memories/       # Memory record JSON files
├── stories/        # Story collection JSON files
└── namesets/       # Name generation JSON files
```

### Test Data

The repo includes `test-data.zip` with example campaign data. Extract it to see the expected JSON formats:

```bash
unzip test-data.zip
python scripts/characters.py list    # Should show example characters
```

---

## Guides

JSON schema and workflow guides:

- [Creating Characters](guides/character-guide.md)
- [Creating Locations](guides/location-guide.md)
- [Creating Namesets](guides/nameset-guide.md)
- [Creating Memories](guides/memories-guide.md)
- [Using the Oracle](guides/oracle-guide.md)
- [Capturing Stories](guides/story-capture-guide.md)
- [Session Setup](guides/session-setup-guide.md)
- [Session Debrief](guides/session-debrief-guide.md)

---

## Building Your Own Skill Package

To bundle rpg-tools with your campaign data for Claude Desktop:

1. **Organize your campaign data** in the directory structure above
2. **Modify `build-skill.sh`** to include your data directories:
   ```bash
   # Add after the existing cp commands:
   cp -r "$REPO_ROOT/your-campaign/characters" "$SKILL_DIR/"
   cp -r "$REPO_ROOT/your-campaign/namesets" "$SKILL_DIR/"
   # etc.
   ```
3. **Build the skill:**
   ```bash
   ./build-skill.sh my-campaign.skill
   ```
4. **Upload** the resulting `.skill` file to Claude Desktop

The skill package is a zip archive containing SKILL.md (the entry point Claude reads), the scripts, guides, and your bundled data.

---

## Optional Skills

The `skills/` folder contains optional Claude Code skills:
- `character-creator.md` - Agent for creating character JSON files

## Modifiers

Optional behavior modifiers in `modifiers/`:
- `mature-content.md` - For authentic dark themes
- `combat-realism.md` - For grounded, consequential violence
