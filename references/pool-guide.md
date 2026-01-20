# Pool Tool Guide

Manage ordered pools of tokens (cards, counters, etc.) with configurable draw modes and persistent state. Perfect for card decks, token bags, encounter pools, and any depleting collection.

## Contents

- [Quick Reference](#quick-reference)
- [Creating Pools](#creating-pools)
- [Drawing Tokens](#drawing-tokens)
- [Pool Settings](#pool-settings)
- [State Management](#state-management)
- [Pool Definition Schema](#pool-definition-schema)
- [CLI Shorthand](#cli-shorthand)
- [Examples](#examples)

---

## Quick Reference

```bash
python scripts/pool.py list                          # List available pools
python scripts/pool.py create NAME                   # Initialize from pools/NAME.json
python scripts/pool.py create NAME --tokens "a:5,b:3" # Create ad-hoc pool
python scripts/pool.py draw NAME [n]                 # Draw n tokens (default 1)
python scripts/pool.py peek NAME [n]                 # Look without removing
python scripts/pool.py status NAME                   # Show remaining tokens
python scripts/pool.py shuffle NAME                  # Shuffle remaining
python scripts/pool.py reset NAME                    # Restore to full
python scripts/pool.py return NAME TOKEN [--top|--bottom|--random]
```

---

## Creating Pools

### From Definition File

Place a JSON file in `pools/` directory, then initialize:

```bash
python scripts/pool.py create playing-cards
# Created pool 'playing-cards' with 52 tokens
```

### Ad-Hoc Pool

Create a quick pool without a definition file:

```bash
python scripts/pool.py create danger --tokens "safe:5,danger:3,doom:1"
# Created pool 'danger' with 9 tokens
```

---

## Drawing Tokens

### Basic Draw

```bash
python scripts/pool.py draw playing-cards
# 7 of Hearts

python scripts/pool.py draw playing-cards 5
# Queen of Spades
# 3 of Diamonds
# Ace of Clubs
# 10 of Hearts
# Jack of Spades
```

### Peek Without Removing

```bash
python scripts/pool.py peek playing-cards 3
# (Shows top 3 cards without removing them)
```

### Return Tokens

```bash
python scripts/pool.py return playing-cards "Ace of Spades" --top
# Returned 'Ace of Spades' to top of pool 'playing-cards'
```

---

## Pool Settings

Three configurable behaviors in pool definitions:

### draw_mode

How tokens are selected when drawing:

| Mode | Behavior |
|------|----------|
| `pop_top` | Draw from top of stack (default) |
| `pop_bottom` | Draw from bottom of stack |
| `random` | Draw randomly from anywhere |

### auto_shuffle

When to automatically shuffle the pool:

| Mode | Behavior |
|------|----------|
| `never` | Only shuffle when explicitly called |
| `on_reset` | Shuffle when created or reset (default) |
| `on_empty` | Shuffle when pool empties and resets |

### on_empty

What happens when drawing from an empty pool:

| Mode | Behavior |
|------|----------|
| `error` | Print error and exit (default) |
| `warn` | Print warning, return nothing |
| `reset` | Automatically reset and continue |

---

## State Management

### State Location

Pool state is stored in `~/.rpg-tools/pools/`. This keeps state:
- Separate from portable pool definitions
- Easy to clear (delete the directory)
- Cross-platform (works on any OS)

### Check Status

```bash
python scripts/pool.py status playing-cards
# Pool: playing-cards
# Total: 47 tokens
# Settings: draw_mode=pop_top, auto_shuffle=on_reset, on_empty=warn
#
# Token counts:
#   10 of Clubs: 1
#   10 of Diamonds: 1
#   ...
```

### Shuffle Remaining

```bash
python scripts/pool.py shuffle playing-cards
# Shuffled pool 'playing-cards' (47 tokens)
```

### Reset to Full

```bash
python scripts/pool.py reset playing-cards
# Reset pool 'playing-cards' (52 tokens)
```

---

## Pool Definition Schema

```json
{
  "id": "pool-name",
  "name": "Display Name",
  "description": "Optional description",
  "settings": {
    "draw_mode": "pop_top",
    "auto_shuffle": "on_reset",
    "on_empty": "error"
  },
  "tokens": [
    {"token": "red", "count": 5},
    {"token": "blue", "count": 3},
    "single-token"
  ]
}
```

### Token Formats

Tokens can be specified as:

```json
{"token": "red", "count": 5}

{"token": "red"}

"red"
```

- First example: Object with count (5 red tokens)
- Second example: Object without count (defaults to 1)
- Third example: Simple string (count 1)

---

## CLI Shorthand

For `--tokens` flag, use comma-separated `token:count` pairs:

```
"red:5,blue:3,green:1"  →  5 red, 3 blue, 1 green
"ace,king,queen"        →  1 of each (count defaults to 1)
"danger:3,doom"         →  3 danger, 1 doom
```

---

## Examples

### Playing Card Game

```bash
# Start a new game
python scripts/pool.py create playing-cards

# Deal 5 cards
python scripts/pool.py draw playing-cards 5

# Check remaining
python scripts/pool.py status playing-cards

# Shuffle for next round
python scripts/pool.py shuffle playing-cards

# Reset for new game
python scripts/pool.py reset playing-cards
```

### Danger Token Bag

```bash
# Create tension pool
python scripts/pool.py create danger --tokens "safe:5,danger:3,doom:1"

# Draw until doom
python scripts/pool.py draw danger
# safe
python scripts/pool.py draw danger
# danger
python scripts/pool.py draw danger
# safe
# ...eventually...
python scripts/pool.py draw danger
# doom
```

### Tarot Reading

```bash
# Initialize deck
python scripts/pool.py create tarot

# Draw a 3-card spread
python scripts/pool.py draw tarot 3

# Return a card to the deck
python scripts/pool.py return tarot "The Fool" --random
```

### Encounter Pool (Auto-Reset)

Create a pool definition with `on_empty: reset` for infinite draws:

```json
{
  "id": "encounters",
  "name": "Random Encounters",
  "settings": {
    "draw_mode": "random",
    "auto_shuffle": "on_empty",
    "on_empty": "reset"
  },
  "tokens": [
    {"token": "bandits", "count": 3},
    {"token": "wolves", "count": 2},
    {"token": "merchant", "count": 2},
    {"token": "nothing", "count": 5},
    {"token": "rare-event", "count": 1}
  ]
}
```

```bash
python scripts/pool.py create encounters
python scripts/pool.py draw encounters
# Draws forever, reshuffling when empty
```

---

## Bundled Pools

The following pools are included:

| Pool | Description |
|------|-------------|
| `playing-cards` | Standard 52-card deck |
| `tarot` | 78-card tarot (Major + Minor Arcana) |
| `tokens-example` | Danger tokens demo (safe/danger/doom) |
