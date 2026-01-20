---
name: rpg-tools
description: Solo RPG mechanical tools for dice rolling, tarot draws, oracles, name generation, character/location/memory/faction management, and story retrieval. Use when the user asks to roll dice, draw tarot cards, consult oracles, generate names, load characters or locations, track memories or factions, or pull from story collections during RPG sessions.
---

# RPG Tools

Mechanical tools for solo RPG sessions. Run scripts from `scripts/`.

## Tool Categories

**Instant Tools** - Work immediately, no data files needed:
- `dice.py` - Dice rolling
- `tarot.py` - Tarot draws
- `oracle.py` - Multi-system oracle

**Campaign Tools** - Require JSON data files in specific directories:
- `namegen.py` - Name generation (needs `namesets/`)
- `characters.py` - Character profiles (needs `characters/`)
- `locations.py` - Location profiles (needs `locations/`)
- `stories.py` - Story collections (needs `stories/`)
- `memories.py` - Memory tracking (needs `memories/`)
- `factions.py` - Faction tracking (needs `factions/`)
- `log.py` - Campaign event log (needs `campaign/log.json`)
- `campaign.py` - Campaign management (needs `campaign/config.json`)

---

## Instant Tools

### Dice

Roll20-compatible notation: `kh/kl` (keep), `dh/dl` (drop), `r/rr` (reroll), `!`/`!!`/`!p` (exploding), comparison operators.

```bash
python scripts/dice.py "2d6+5"      # Basic roll
python scripts/dice.py "4d6kh3"     # Keep highest 3
python scripts/dice.py "8d6!"       # Exploding dice
python scripts/dice.py "2d6r1"      # Reroll 1s once
python scripts/dice.py "6d10>=7"    # Count successes
```

### Tarot

```bash
python scripts/tarot.py       # Single card
python scripts/tarot.py 3     # Three-card spread
```

Max 10 cards. Full 78-card deck.

### Oracle

See **[oracle-guide.md](references/oracle-guide.md)** for when to use each type.

```bash
python scripts/oracle.py axis               # Tone/direction/element/action/twist
python scripts/oracle.py omni               # Full reading (all systems)
python scripts/oracle.py tarot [n]          # Draw tarot
python scripts/oracle.py rune [n]           # Draw runes
python scripts/oracle.py iching             # I Ching hexagram
python scripts/oracle.py fate [likelihood]  # Yes/no (impossible/unlikely/even/likely/certain)
python scripts/oracle.py prompt             # Action + Theme pair
```

---

## Campaign Tools

### Name Generation

See **[nameset-guide.md](references/nameset-guide.md)** for creating namesets.

```bash
python scripts/namegen.py list                          # Available namesets
python scripts/namegen.py full --nameset NAME           # Generate name
python scripts/namegen.py full --nameset NAME --count 5 --gender female
python scripts/namegen.py groups --nameset NAME         # List groups/sources
```

### Characters

See **[character-guide.md](references/character-guide.md)** for schema.

```bash
python scripts/characters.py list [--short]                    # List characters
python scripts/characters.py get NAME [--depth full]           # Get profile
python scripts/characters.py get NAME --section SECTION        # Get section
python scripts/characters.py sections NAME                     # List sections
python scripts/characters.py memories NAME                     # Related memories
python scripts/characters.py create ID --name N --role R --essence E
python scripts/characters.py update NAME --field F --value V --reason R
python scripts/characters.py delete NAME [--force]
```

Filters: `--faction`, `--subfaction`, `--tag`, `--location`, `--branch`

### Locations

See **[location-guide.md](references/location-guide.md)** for schema.

```bash
python scripts/locations.py list [--short]              # List locations
python scripts/locations.py get NAME [--depth full]     # Get profile
python scripts/locations.py sections NAME               # List sections
python scripts/locations.py tree [NAME]                 # Show hierarchy
python scripts/locations.py path NAME                   # Path to root
python scripts/locations.py connections NAME            # Graph connections
python scripts/locations.py memories NAME               # Related memories
python scripts/locations.py create ID --name N --type T --essence E [--parent P]
python scripts/locations.py update NAME --field F --value V
python scripts/locations.py delete NAME
```

Filters: `--tag`, `--parent`, `--type`

### Stories

See **[story-capture-guide.md](references/story-capture-guide.md)** for schema.

```bash
python scripts/stories.py meta --campaign NAME          # Tags/counts
python scripts/stories.py list --campaign NAME          # List stories
python scripts/stories.py get --campaign NAME --story ID
python scripts/stories.py show --campaign NAME --story ID
python scripts/stories.py random --campaign NAME
python scripts/stories.py create --campaign NAME --title T --text C
```

Filters: `--collection`, `--theme`, `--mood`, `--era`

### Memories

See **[memories-guide.md](references/memories-guide.md)** for schema.

```bash
python scripts/memories.py list --campaign NAME         # List memories
python scripts/memories.py get MEMORY_ID                # Get specific
python scripts/memories.py random --campaign NAME
python scripts/memories.py recent --campaign NAME       # Most recent
python scripts/memories.py search "query" --campaign NAME
python scripts/memories.py character NAME               # By character
python scripts/memories.py location NAME                # By location
python scripts/memories.py connections MEMORY_ID        # Cross-references
python scripts/memories.py chain MEMORY_ID              # Follow related
python scripts/memories.py meta --campaign NAME         # Counts
python scripts/memories.py create --campaign NAME --title T --text C
```

Filters: `--character`, `--location`, `--type`, `--tag`, `--era`, `--session`, `--intensity`, `--perspective`

### Factions

See **[faction-guide.md](references/faction-guide.md)** for schema.

```bash
python scripts/factions.py list [--short]               # List factions
python scripts/factions.py get NAME [--depth full]      # Get profile
python scripts/factions.py tree [NAME]                  # Hierarchy
python scripts/factions.py members NAME                 # List members
python scripts/factions.py relationships NAME           # Relationships
python scripts/factions.py economy NAME                 # Economy
python scripts/factions.py resources NAME               # Resources
python scripts/factions.py create ID --name N --type T --essence E
python scripts/factions.py update NAME --field F --value V --reason R
python scripts/factions.py delete NAME
```

Filters: `--type`, `--tag`

### Campaign Log

See **[campaign-state-guide.md](references/campaign-state-guide.md)** for full documentation.

```bash
python scripts/log.py add "Event" --date Y3.D45         # Add entry
python scripts/log.py add "Event" --date-loose "after the festival"
python scripts/log.py add "Event" --characters "juno:defining,tam:present"
python scripts/log.py list                              # List entries
python scripts/log.py show ID                           # Show entry
python scripts/log.py delete ID                         # Delete entry
python scripts/log.py digest                            # Tiered summary
```

Add options: `--date`, `--date-loose`, `--branch`, `--characters`, `--locations`, `--importance`, `--tags`, `--session`

Filters: `--branch`, `--character`, `--location`, `--importance`, `--tag`, `--from`, `--to`, `--limit`

### Campaign Management

See **[campaign-state-guide.md](references/campaign-state-guide.md)** for full documentation.

```bash
python scripts/campaign.py init "Campaign Name"
python scripts/campaign.py show
python scripts/campaign.py branch list
python scripts/campaign.py branch switch BRANCH
python scripts/campaign.py branch create ID "Name" [--from BRANCH] [--protagonists "a,b"]
python scripts/campaign.py state show [--character NAME]
python scripts/campaign.py state set CHAR field "value" --reason R
python scripts/campaign.py state delete CHAR field --reason R
python scripts/campaign.py changelog show [--character NAME] [--limit N]
python scripts/campaign.py export [--output FILE.zip]
python scripts/campaign.py import FILE.zip [--into DIR]
```

---

## Session Workflow

- **[Campaign Zero](references/campaign-zero-guide.md)** - Pre-campaign brainstorming and bundle creation
- **[Session Setup](references/session-setup-guide.md)** - Calibrate tone, direction, and pacing
- **[Session Debrief](references/session-debrief-guide.md)** - Post-session reflection and character growth

**Optional modifiers:**
- [Mature Content](modifiers/mature-content.md) - For authentic dark themes
- [Combat Realism](modifiers/combat-realism.md) - For grounded, consequential violence

---

## Creating Campaign Data

- **[character-guide.md](references/character-guide.md)** - Character JSON schema
- **[location-guide.md](references/location-guide.md)** - Location hierarchy and connections
- **[faction-guide.md](references/faction-guide.md)** - Faction hierarchy and economy
- **[memories-guide.md](references/memories-guide.md)** - Memory tracking
- **[nameset-guide.md](references/nameset-guide.md)** - Name generation collections
- **[story-capture-guide.md](references/story-capture-guide.md)** - Story extraction
- **[oracle-guide.md](references/oracle-guide.md)** - Oracle types
- **[campaign-state-guide.md](references/campaign-state-guide.md)** - Branches, log, state
