#!/usr/bin/env python3
"""Pool/deck management tool for solo RPG games.

Manages ordered pools of tokens (cards, counters, etc.) with configurable
draw modes and state persistence. Supports card decks, token bags, encounter
pools, and any depleting collection.
"""

import json
import random
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any


# State directory for active pools (ephemeral)
STATE_DIR = Path.home() / ".rpg-tools" / "pools"

# Default settings for pools
DEFAULT_SETTINGS = {
    "draw_mode": "pop_top",      # pop_top, pop_bottom, random
    "auto_shuffle": "on_reset",  # never, on_reset, on_empty
    "on_empty": "error",         # error, reset, warn
}


# =============================================================================
# Pool Definition Loading
# =============================================================================

def find_pools_dir() -> Optional[Path]:
    """Find the pools directory in cwd."""
    pools_dir = Path.cwd() / "pools"
    if pools_dir.exists():
        return pools_dir
    return None


def list_pool_definitions() -> Dict[str, Path]:
    """List all available pool definition files."""
    pools = {}
    pools_dir = find_pools_dir()
    if pools_dir:
        for path in pools_dir.glob("*.json"):
            pools[path.stem] = path
    return pools


def load_pool_definition(name: str) -> Optional[Dict[str, Any]]:
    """Load a pool definition by name."""
    pools_dir = find_pools_dir()
    if not pools_dir:
        return None

    path = pools_dir / f"{name}.json"
    if not path.exists():
        return None

    try:
        with open(path, encoding='utf-8-sig') as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"Error loading pool definition: {e}", file=sys.stderr)
        return None


def get_settings(definition: Dict[str, Any]) -> Dict[str, str]:
    """Extract settings from definition with defaults."""
    settings = definition.get("settings", {})
    return {
        "draw_mode": settings.get("draw_mode", DEFAULT_SETTINGS["draw_mode"]),
        "auto_shuffle": settings.get("auto_shuffle", DEFAULT_SETTINGS["auto_shuffle"]),
        "on_empty": settings.get("on_empty", DEFAULT_SETTINGS["on_empty"]),
    }


def expand_tokens(tokens: List[Any]) -> List[str]:
    """Expand token definitions into a flat list.

    Handles:
    - {"token": "red", "count": 5} -> ["red", "red", "red", "red", "red"]
    - "red" -> ["red"]
    - {"token": "red"} -> ["red"] (count defaults to 1)
    """
    expanded = []
    for item in tokens:
        if isinstance(item, str):
            expanded.append(item)
        elif isinstance(item, dict):
            token = item.get("token")
            if token is None:
                print(f"Warning: token item missing 'token' key: {item}", file=sys.stderr)
                continue
            count = item.get("count", 1)
            expanded.extend([token] * count)
    return expanded


def parse_shorthand_tokens(shorthand: str) -> List[str]:
    """Parse CLI shorthand tokens into expanded list.

    Format: "red:5,blue:3,green" -> ["red"]*5 + ["blue"]*3 + ["green"]
    """
    expanded = []
    for part in shorthand.split(","):
        part = part.strip()
        if not part:
            continue
        if ":" in part:
            token, count_str = part.rsplit(":", 1)
            try:
                count = int(count_str)
            except ValueError:
                count = 1
        else:
            token = part
            count = 1
        expanded.extend([token] * count)
    return expanded


# =============================================================================
# State Management
# =============================================================================

def get_state_path(pool_name: str) -> Path:
    """Get the state file path for a pool."""
    return STATE_DIR / f"{pool_name}.state.json"


def load_state(pool_name: str) -> Optional[Dict[str, Any]]:
    """Load state for a pool. Returns None if no state exists."""
    path = get_state_path(pool_name)
    if not path.exists():
        return None

    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"Error loading state: {e}", file=sys.stderr)
        return None


def save_state(pool_name: str, tokens: List[str], settings: Dict[str, str],
               definition_name: Optional[str] = None) -> bool:
    """Save state for a pool."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)

    state = {
        "pool_id": pool_name,
        "definition": definition_name or pool_name,
        "created": datetime.now().isoformat(),
        "settings": settings,
        "tokens": tokens,
    }

    try:
        path = get_state_path(pool_name)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2)
        return True
    except OSError as e:
        print(f"Error saving state: {e}", file=sys.stderr)
        return False


def delete_state(pool_name: str) -> bool:
    """Delete state for a pool."""
    path = get_state_path(pool_name)
    if path.exists():
        try:
            path.unlink()
            return True
        except OSError as e:
            print(f"Error deleting state: {e}", file=sys.stderr)
            return False
    return False


def list_active_pools() -> List[str]:
    """List pools with active state files."""
    if not STATE_DIR.exists():
        return []
    return [p.stem.replace(".state", "") for p in STATE_DIR.glob("*.state.json")]


# =============================================================================
# Commands
# =============================================================================

def cmd_list(output_json: bool = False) -> None:
    """List available pool definitions."""
    definitions = list_pool_definitions()
    active = list_active_pools()

    if output_json:
        result = []
        for name, path in definitions.items():
            defn = load_pool_definition(name)
            result.append({
                "id": name,
                "name": defn.get("name", name) if defn else name,
                "description": defn.get("description", "") if defn else "",
                "active": name in active,
            })
        print(json.dumps(result, indent=2))
        return

    if not definitions:
        print("No pool definitions found in pools/")
        return

    print("Available pools:")
    for name, path in sorted(definitions.items()):
        defn = load_pool_definition(name)
        display_name = defn.get("name", name) if defn else name
        desc = defn.get("description", "") if defn else ""
        active_marker = " [active]" if name in active else ""

        if desc:
            print(f"  {name}: {display_name} - {desc}{active_marker}")
        else:
            print(f"  {name}: {display_name}{active_marker}")

    print(f"\nTotal: {len(definitions)} pool(s)")


def cmd_create(name: str, tokens_shorthand: Optional[str] = None,
               output_json: bool = False) -> None:
    """Create/initialize a pool from definition or shorthand."""
    if tokens_shorthand:
        # Ad-hoc pool from shorthand
        tokens = parse_shorthand_tokens(tokens_shorthand)
        settings = DEFAULT_SETTINGS.copy()
        definition_name = None
    else:
        # Load from definition
        defn = load_pool_definition(name)
        if not defn:
            print(f"Error: Pool definition '{name}' not found", file=sys.stderr)
            print("Use --tokens to create an ad-hoc pool, or check pools/ directory", file=sys.stderr)
            sys.exit(1)

        tokens = expand_tokens(defn.get("tokens", []))
        settings = get_settings(defn)
        definition_name = name

    if not tokens:
        print("Error: No tokens in pool", file=sys.stderr)
        sys.exit(1)

    # Apply auto_shuffle on_reset
    if settings["auto_shuffle"] in ("on_reset", "on_empty"):
        random.shuffle(tokens)

    if save_state(name, tokens, settings, definition_name):
        if output_json:
            print(json.dumps({
                "pool": name,
                "tokens": len(tokens),
                "settings": settings,
            }, indent=2))
        else:
            print(f"Created pool '{name}' with {len(tokens)} tokens")
    else:
        sys.exit(1)


def cmd_draw(name: str, count: int = 1, output_json: bool = False) -> None:
    """Draw tokens from a pool."""
    state = load_state(name)
    if not state:
        print(f"Error: Pool '{name}' not initialized. Use 'create' first.", file=sys.stderr)
        sys.exit(1)

    tokens = state["tokens"]
    settings = state.get("settings", DEFAULT_SETTINGS)
    definition_name = state.get("definition")
    drawn = []

    for _ in range(count):
        if not tokens:
            # Handle empty pool
            on_empty = settings.get("on_empty", "error")
            if on_empty == "error":
                if drawn:
                    # Save what we drew so far
                    save_state(name, tokens, settings, definition_name)
                print(f"Error: Pool '{name}' is empty", file=sys.stderr)
                sys.exit(1)
            elif on_empty == "warn":
                print(f"Warning: Pool '{name}' is empty", file=sys.stderr)
                break
            elif on_empty == "reset":
                # Reload from definition
                defn = load_pool_definition(definition_name or name)
                if defn:
                    tokens = expand_tokens(defn.get("tokens", []))
                    if settings.get("auto_shuffle") == "on_empty":
                        random.shuffle(tokens)
                    print(f"Pool '{name}' reset ({len(tokens)} tokens)", file=sys.stderr)
                else:
                    print(f"Error: Cannot reset - definition '{definition_name}' not found", file=sys.stderr)
                    break

        if not tokens:
            break

        # Draw based on mode
        draw_mode = settings.get("draw_mode", "pop_top")
        if draw_mode == "pop_top":
            drawn.append(tokens.pop(0))
        elif draw_mode == "pop_bottom":
            drawn.append(tokens.pop())
        else:  # random
            idx = random.randrange(len(tokens))
            drawn.append(tokens.pop(idx))

    # Save updated state
    save_state(name, tokens, settings, definition_name)

    if output_json:
        print(json.dumps({
            "drawn": drawn,
            "remaining": len(tokens),
        }, indent=2))
    else:
        for token in drawn:
            print(token)


def cmd_peek(name: str, count: int = 1, output_json: bool = False) -> None:
    """Peek at tokens without removing them."""
    state = load_state(name)
    if not state:
        print(f"Error: Pool '{name}' not initialized. Use 'create' first.", file=sys.stderr)
        sys.exit(1)

    tokens = state["tokens"]
    settings = state.get("settings", DEFAULT_SETTINGS)

    if not tokens:
        print(f"Pool '{name}' is empty", file=sys.stderr)
        return

    draw_mode = settings.get("draw_mode", "pop_top")
    count = min(count, len(tokens))

    if draw_mode == "pop_top":
        peeked = tokens[:count]
    elif draw_mode == "pop_bottom":
        peeked = tokens[-count:][::-1]  # Reverse to show in draw order
    else:  # random
        peeked = random.sample(tokens, count)
        print("(Note: random mode - actual draws may differ)", file=sys.stderr)

    if output_json:
        print(json.dumps({
            "peeked": peeked,
            "remaining": len(tokens),
        }, indent=2))
    else:
        for token in peeked:
            print(token)


def cmd_status(name: str, output_json: bool = False) -> None:
    """Show pool status."""
    state = load_state(name)
    if not state:
        print(f"Error: Pool '{name}' not initialized. Use 'create' first.", file=sys.stderr)
        sys.exit(1)

    tokens = state["tokens"]
    settings = state.get("settings", DEFAULT_SETTINGS)

    # Count token types
    counts: Dict[str, int] = {}
    for token in tokens:
        counts[token] = counts.get(token, 0) + 1

    if output_json:
        print(json.dumps({
            "pool": name,
            "total": len(tokens),
            "counts": counts,
            "settings": settings,
        }, indent=2))
    else:
        print(f"Pool: {name}")
        print(f"Total: {len(tokens)} tokens")
        print(f"Settings: draw_mode={settings['draw_mode']}, "
              f"auto_shuffle={settings['auto_shuffle']}, "
              f"on_empty={settings['on_empty']}")
        if counts:
            print("\nToken counts:")
            for token, count in sorted(counts.items()):
                print(f"  {token}: {count}")


def cmd_shuffle(name: str) -> None:
    """Shuffle remaining tokens in a pool."""
    state = load_state(name)
    if not state:
        print(f"Error: Pool '{name}' not initialized. Use 'create' first.", file=sys.stderr)
        sys.exit(1)

    tokens = state["tokens"]
    settings = state.get("settings", DEFAULT_SETTINGS)
    definition_name = state.get("definition")

    random.shuffle(tokens)
    save_state(name, tokens, settings, definition_name)
    print(f"Shuffled pool '{name}' ({len(tokens)} tokens)")


def cmd_reset(name: str, output_json: bool = False) -> None:
    """Reset a pool to its full definition."""
    state = load_state(name)
    definition_name = state.get("definition", name) if state else name

    defn = load_pool_definition(definition_name)
    if not defn:
        print(f"Error: Pool definition '{definition_name}' not found", file=sys.stderr)
        sys.exit(1)

    tokens = expand_tokens(defn.get("tokens", []))
    settings = get_settings(defn)

    # Apply auto_shuffle on_reset
    if settings["auto_shuffle"] in ("on_reset", "on_empty"):
        random.shuffle(tokens)

    save_state(name, tokens, settings, definition_name)

    if output_json:
        print(json.dumps({
            "pool": name,
            "tokens": len(tokens),
        }, indent=2))
    else:
        print(f"Reset pool '{name}' ({len(tokens)} tokens)")


def cmd_return(name: str, token: str, position: str = "bottom") -> None:
    """Return a token to the pool."""
    state = load_state(name)
    if not state:
        print(f"Error: Pool '{name}' not initialized. Use 'create' first.", file=sys.stderr)
        sys.exit(1)

    tokens = state["tokens"]
    settings = state.get("settings", DEFAULT_SETTINGS)
    definition_name = state.get("definition")

    if position == "top":
        tokens.insert(0, token)
    elif position == "random":
        idx = random.randint(0, len(tokens))
        tokens.insert(idx, token)
    else:  # bottom (default)
        tokens.append(token)

    save_state(name, tokens, settings, definition_name)
    print(f"Returned '{token}' to {position} of pool '{name}'")


# =============================================================================
# CLI
# =============================================================================

def print_usage():
    """Print usage information."""
    print("Usage: python pool.py <command> [options]")
    print()
    print("Commands:")
    print("  list                          List available pool definitions")
    print("  create <name>                 Initialize pool from pools/<name>.json")
    print("  create <name> --tokens T      Create ad-hoc pool (T = 'red:5,blue:3')")
    print("  draw <name> [n]               Draw n tokens (default 1)")
    print("  peek <name> [n]               Peek at n tokens without removing")
    print("  status <name>                 Show pool status and token counts")
    print("  shuffle <name>                Shuffle remaining tokens")
    print("  reset <name>                  Reset pool to full definition")
    print("  return <name> <token>         Return token to pool")
    print()
    print("Options:")
    print("  --tokens T                    Shorthand tokens for create ('red:5,blue:3')")
    print("  --top                         Return token to top of pool")
    print("  --bottom                      Return token to bottom (default)")
    print("  --random                      Return token to random position")
    print("  --json                        Output as JSON")
    print()
    print("Pool settings (in definition JSON):")
    print("  draw_mode:    pop_top, pop_bottom, random")
    print("  auto_shuffle: never, on_reset, on_empty")
    print("  on_empty:     error, reset, warn")


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ('--help', '-h'):
        print_usage()
        sys.exit(0 if len(sys.argv) > 1 else 1)

    command = sys.argv[1]

    # Parse options
    pool_name = None
    count = 1
    tokens_shorthand = None
    position = "bottom"
    return_token = None
    output_json = False

    i = 2
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == "--tokens" and i + 1 < len(sys.argv):
            tokens_shorthand = sys.argv[i + 1]
            i += 2
        elif arg == "--top":
            position = "top"
            i += 1
        elif arg == "--bottom":
            position = "bottom"
            i += 1
        elif arg == "--random":
            position = "random"
            i += 1
        elif arg == "--json":
            output_json = True
            i += 1
        elif arg.startswith("--"):
            print(f"Unknown option: {arg}", file=sys.stderr)
            sys.exit(1)
        elif pool_name is None:
            pool_name = arg
            i += 1
        elif command in ("draw", "peek"):
            try:
                count = int(arg)
            except ValueError:
                print(f"Error: Invalid count '{arg}'", file=sys.stderr)
                sys.exit(1)
            i += 1
        elif command == "return" and return_token is None:
            return_token = arg
            i += 1
        else:
            i += 1

    # Execute command
    if command == "list":
        cmd_list(output_json)
    elif command == "create":
        if not pool_name:
            print("Error: Pool name required", file=sys.stderr)
            sys.exit(1)
        cmd_create(pool_name, tokens_shorthand, output_json)
    elif command == "draw":
        if not pool_name:
            print("Error: Pool name required", file=sys.stderr)
            sys.exit(1)
        cmd_draw(pool_name, count, output_json)
    elif command == "peek":
        if not pool_name:
            print("Error: Pool name required", file=sys.stderr)
            sys.exit(1)
        cmd_peek(pool_name, count, output_json)
    elif command == "status":
        if not pool_name:
            print("Error: Pool name required", file=sys.stderr)
            sys.exit(1)
        cmd_status(pool_name, output_json)
    elif command == "shuffle":
        if not pool_name:
            print("Error: Pool name required", file=sys.stderr)
            sys.exit(1)
        cmd_shuffle(pool_name)
    elif command == "reset":
        if not pool_name:
            print("Error: Pool name required", file=sys.stderr)
            sys.exit(1)
        cmd_reset(pool_name, output_json)
    elif command == "return":
        if not pool_name:
            print("Error: Pool name required", file=sys.stderr)
            sys.exit(1)
        if not return_token:
            print("Error: Token to return required", file=sys.stderr)
            sys.exit(1)
        cmd_return(pool_name, return_token, position)
    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        print_usage()
        sys.exit(1)


if __name__ == "__main__":
    main()
