# Pool Tool Implementation Plan

**Date:** 2025-01-20
**Feature:** `pool.py` - Ordered pool/deck management tool
**Branch:** `feature/pool-tool`

## Overview

A flexible ordered-list pool/deck manager that tracks state as items are drawn. Supports card decks, token bags, encounter pools, and any depleting collection with configurable draw behavior.

## Design Summary

**Tool:** `scripts/pool.py` (standalone, no lib imports needed)

**State Management:**
- Definitions: `pools/*.json` (working directory, portable)
- State: `/home/claude/tmp/pools/<pool-name>.state.json` (ephemeral)

**Key Features:**
- Ordered token list (stack/deck) with configurable draw modes
- Three draw modes: `pop_top`, `pop_bottom`, `random`
- Auto-shuffle options: `never`, `on_reset`, `on_empty`
- Empty-pool handling: `error`, `reset`, `warn`
- CLI shorthand for quick ad-hoc pools
- Bundled definitions: playing cards, tarot

---

## Batch 1: Core Infrastructure

### Task 1.1: Create feature branch
```bash
git checkout -b feature/pool-tool develop
```

### Task 1.2: Create `scripts/pool.py` skeleton
- Basic CLI argument parsing
- Help text with all commands
- State directory constant (`/home/claude/tmp/pools/`)
- Pool definition discovery (search `pools/` in cwd)

### Task 1.3: Implement pool definition loading
- Load JSON from `pools/<name>.json`
- Parse settings with defaults:
  - `draw_mode`: default `pop_top`
  - `auto_shuffle`: default `on_reset`
  - `on_empty`: default `error`
- Expand tokens with counts (e.g., `{"token": "red", "count": 5}` → 5 "red" entries)
- Support both object format and shorthand parsing for CLI

### Task 1.4: Implement state file management
- `load_state(pool_name)` → returns ordered list or None if no state
- `save_state(pool_name, tokens)` → write to `/home/claude/tmp/pools/<name>.state.json`
- `delete_state(pool_name)` → remove state file
- Ensure directory exists on first write

---

## Batch 2: Core Commands

### Task 2.1: Implement `create` command
```bash
python pool.py create <name>                     # From pools/<name>.json
python pool.py create <name> --tokens "red:5,blue:3"  # Ad-hoc shorthand
```
- Load definition OR parse shorthand tokens
- Apply `auto_shuffle: on_reset` if set (shuffle initial list)
- Write state file
- Print confirmation with token count

### Task 2.2: Implement `draw` command
```bash
python pool.py draw <name> [n]    # Draw n tokens (default 1)
```
- Load state, error if not created
- Apply draw_mode:
  - `pop_top`: pop from index 0
  - `pop_bottom`: pop from index -1
  - `random`: random.choice + remove
- Handle empty pool per `on_empty` setting:
  - `error`: print error, exit 1
  - `warn`: print warning, return nothing
  - `reset`: reload definition, apply `auto_shuffle: on_empty` if set, continue draw
- Save updated state
- Print drawn token(s)

### Task 2.3: Implement `peek` command
```bash
python pool.py peek <name> [n]    # Look at n tokens without removing
```
- Same logic as draw but don't modify state
- For `pop_top`/`pop_bottom`: show first/last n
- For `random`: show n random (but note they won't be the actual draws)

### Task 2.4: Implement `status` command
```bash
python pool.py status <name>
```
- Load state
- Print total remaining
- Print token counts (grouped, e.g., "red: 3, blue: 2")
- Show pool settings (draw_mode, on_empty)

---

## Batch 3: State Manipulation Commands

### Task 3.1: Implement `shuffle` command
```bash
python pool.py shuffle <name>
```
- Load state
- `random.shuffle()` in place
- Save state
- Print confirmation

### Task 3.2: Implement `reset` command
```bash
python pool.py reset <name>
```
- Reload definition
- Apply `auto_shuffle: on_reset` if set
- Save as new state (replaces existing)
- Print confirmation with token count

### Task 3.3: Implement `return` command
```bash
python pool.py return <name> <token> [--top|--bottom|--random]
```
- Load state
- Insert token at specified position (default: bottom for deck-like behavior)
- Save state
- Print confirmation

### Task 3.4: Implement `list` command
```bash
python pool.py list
```
- Scan `pools/` directory
- For each `.json` file: show name, description, token count
- Mark which pools have active state files

---

## Batch 4: Pool Definitions

### Task 4.1: Create `pools/playing-cards.json`
```json
{
  "id": "playing-cards",
  "name": "Standard Playing Cards",
  "description": "52-card deck",
  "settings": {
    "draw_mode": "pop_top",
    "auto_shuffle": "on_reset",
    "on_empty": "warn"
  },
  "tokens": [
    {"token": "Ace of Spades", "count": 1},
    {"token": "2 of Spades", "count": 1},
    ...
  ]
}
```

### Task 4.2: Create `pools/tarot.json`
```json
{
  "id": "tarot",
  "name": "Tarot Deck",
  "description": "78-card tarot deck (Major + Minor Arcana)",
  "settings": {
    "draw_mode": "pop_top",
    "auto_shuffle": "on_reset",
    "on_empty": "warn"
  },
  "tokens": [...]
}
```

### Task 4.3: Create `pools/tokens-example.json`
Simple token pool demonstrating duplicates:
```json
{
  "id": "tokens-example",
  "name": "Danger Tokens",
  "description": "Example token pool with weighted distribution",
  "settings": {
    "draw_mode": "random",
    "auto_shuffle": "never",
    "on_empty": "error"
  },
  "tokens": [
    {"token": "safe", "count": 5},
    {"token": "danger", "count": 3},
    {"token": "doom", "count": 1}
  ]
}
```

---

## Batch 5: Documentation & Integration

### Task 5.1: Create `references/pool-guide.md`
- Quick reference
- Pool definition schema
- CLI shorthand format
- Settings reference (draw_mode, auto_shuffle, on_empty)
- Examples for cards, tokens, encounter pools

### Task 5.2: Update `SKILL.md`
Add pool.py to Instant Tools section with commands:
```bash
python scripts/pool.py list                          # Available pools
python scripts/pool.py create NAME                   # Initialize pool
python scripts/pool.py create NAME --tokens "a:5,b:3" # Ad-hoc pool
python scripts/pool.py draw NAME [n]                 # Draw tokens
python scripts/pool.py peek NAME [n]                 # Peek without drawing
python scripts/pool.py return NAME TOKEN [--top|--bottom]
python scripts/pool.py shuffle NAME                  # Shuffle remaining
python scripts/pool.py reset NAME                    # Restore to full
python scripts/pool.py status NAME                   # Show remaining
```

### Task 5.3: Update `CLAUDE.md`
Add pool.py to the Instant Tools list (since it needs no external campaign data, just its own pools/ directory).

---

## Batch 6: Final Polish

### Task 6.1: Add `--json` output flag
For programmatic use, add `--json` to output structured JSON for:
- `draw` (drawn tokens)
- `peek` (peeked tokens)
- `status` (full state)
- `list` (pool definitions)

### Task 6.2: Test all use cases
Manual testing:
- Playing cards: create, draw 5, shuffle, draw more, reset
- Tarot: create, peek 3, draw, check status
- Ad-hoc tokens: create with shorthand, draw until empty (test on_empty behavior)
- Return: verify top/bottom/random insertion

### Task 6.3: Create PR
- Summary of feature
- Link to pool-guide.md
- Test plan in PR body

---

## Pool Definition Schema

```json
{
  "id": "string (required)",
  "name": "string (required)",
  "description": "string (optional)",
  "settings": {
    "draw_mode": "pop_top|pop_bottom|random (default: pop_top)",
    "auto_shuffle": "never|on_reset|on_empty (default: on_reset)",
    "on_empty": "error|reset|warn (default: error)"
  },
  "tokens": [
    {"token": "string", "count": "number (default: 1)"},
    "string shorthand also works"
  ]
}
```

## State File Schema

```json
{
  "pool_id": "string",
  "created": "ISO timestamp",
  "tokens": ["ordered", "list", "of", "tokens"]
}
```

## CLI Shorthand Format

For `--tokens` flag:
- `"red:5,blue:3,green:1"` → 5 red, 3 blue, 1 green
- `"token:count,token:count,..."`
- Count defaults to 1 if omitted: `"ace,king,queen"` → 1 of each

---

## Notes

- Pool.py is standalone (no lib/ imports) since it follows the "instant tool" pattern
- State in `/home/claude/tmp/` keeps it ephemeral and separate from campaign data
- Definitions in `pools/` are portable and can be shared
- The ordered-list design enables both deterministic (pop) and random draws
- Duplicate token support (via count) enables weighted pools and realistic decks
