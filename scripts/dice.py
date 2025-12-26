#!/usr/bin/env python3
"""Enhanced dice rolling tool with Roll20-compatible notation support."""

import re
import random
import sys
from typing import List, Dict, Any


class DiceRoll:
    """Class to represent and process a dice roll with Roll20-compatible notation."""

    def __init__(self, notation: str):
        self.original_notation = notation
        self.notation = notation.lower().replace(" ", "")
        self.dice_sets = []
        self.static_mod = 0
        self.result = None
        self.details = {}
        self.error = None

        try:
            self._parse_notation()
        except Exception as e:
            self.error = f"Error parsing dice notation: {str(e)}"

    def _parse_notation(self):
        """Parse the dice notation into components."""
        # Match dice sets like 2d6, 4d8kh3, etc.
        # Parse dice FIRST to avoid extracting modifiers from notation like 2d6+5d4
        dice_pattern = r'(\d*)d(\d+|f)(?:(kh|kl|dh|dl|r|rr)(\d+)?)?(?:(!{1,2}p?)?)?(?:(>=|<=|>|<|=)(\d+)?)?'
        dice_matches = re.findall(dice_pattern, self.notation)

        # Remove dice patterns from notation to find remaining static modifiers
        remaining = re.sub(dice_pattern, '', self.notation)

        # Extract static modifiers from remaining text
        mod_pattern = r'([+-]\d+)'
        mod_matches = re.findall(mod_pattern, remaining)
        for mod in mod_matches:
            self.static_mod += int(mod)

        if not dice_matches:
            raise ValueError(f"No valid dice notation found in '{self.original_notation}'")

        for match in dice_matches:
            count = int(match[0]) if match[0] else 1  # Default to 1 if omitted (e.g., "d6")

            # Handle Fudge/Fate dice specially
            if match[1].lower() == 'f':
                sides = 'f'  # Special marker for Fudge dice
            else:
                sides = int(match[1])

            # Parse modifier type and value
            mod_type = match[2] if match[2] else None
            mod_value = int(match[3]) if match[3] else None

            # Parse exploding dice
            explode_type = match[4] if match[4] else None

            # Parse target/success counting
            target_op = match[5] if match[5] else None
            target_value = int(match[6]) if match[6] else None

            self.dice_sets.append({
                'count': count,
                'sides': sides,
                'mod_type': mod_type,
                'mod_value': mod_value,
                'explode_type': explode_type,
                'target_op': target_op,
                'target_value': target_value
            })

    def roll(self) -> Dict[str, Any]:
        """Execute the dice roll and apply all modifiers."""
        if self.error:
            return {'error': self.error}

        all_rolls = []
        all_kept = []
        all_totals = []
        successes = 0

        for dice_set in self.dice_sets:
            count = dice_set['count']
            sides = dice_set['sides']

            # Roll the initial dice
            if sides == 'f':  # Fudge/Fate dice (-1, 0, 1)
                rolls = [random.randint(-1, 1) for _ in range(count)]
            else:
                rolls = [random.randint(1, sides) for _ in range(count)]

            # Process rerolls
            if dice_set['mod_type'] in ('r', 'rr'):
                rolls = self._apply_rerolls(rolls, dice_set)

            # Process exploding dice
            if dice_set['explode_type']:
                rolls = self._apply_exploding(rolls, dice_set)

            # Process keep/drop modifiers
            if dice_set['mod_type'] in ('kh', 'kl', 'dh', 'dl'):
                kept = self._apply_keep_drop(rolls, dice_set)
            else:
                kept = rolls.copy()

            # Process target/success counting
            if dice_set['target_op'] and dice_set['target_value'] is not None:
                success_count = self._count_successes(kept, dice_set)
                successes += success_count

            all_rolls.append(rolls)
            all_kept.append(kept)
            all_totals.append(sum(kept))

        # Calculate final total
        total = sum(all_totals) + self.static_mod

        # Prepare the result
        result = {
            'total': total if not any(ds['target_op'] for ds in self.dice_sets) else successes,
            'rolls': all_rolls,
            'kept': all_kept,
            'notation': self.original_notation,
            'details': {
                'dice_sets': self.dice_sets,
                'static_mod': self.static_mod
            }
        }

        self.result = result
        return result

    def _apply_rerolls(self, rolls: List[int], dice_set: Dict[str, Any]) -> List[int]:
        """Apply reroll modifiers to the dice."""
        sides = dice_set['sides']
        mod_type = dice_set['mod_type']
        mod_value = dice_set['mod_value'] or 1  # Default to rerolling 1s

        result = rolls.copy()

        # Handle 'reroll once'
        if mod_type == 'r':
            for i, val in enumerate(result):
                if val <= mod_value:
                    if sides == 'f':
                        result[i] = random.randint(-1, 1)
                    else:
                        result[i] = random.randint(1, sides)

        # Handle 'reroll always'
        elif mod_type == 'rr':
            for i, val in enumerate(result):
                while val <= mod_value:
                    if sides == 'f':
                        val = random.randint(-1, 1)
                    else:
                        val = random.randint(1, sides)
                    result[i] = val

        return result

    def _apply_exploding(self, rolls: List[int], dice_set: Dict[str, Any]) -> List[int]:
        """Apply exploding dice modifiers."""
        sides = dice_set['sides']
        explode_type = dice_set['explode_type']

        # Skip for Fudge dice
        if sides == 'f':
            return rolls

        result = rolls.copy()

        # Basic exploding (!): Add new dice for each max value
        if explode_type == '!':
            i = 0
            while i < len(result):
                if result[i] == sides:  # Check for max value
                    new_roll = random.randint(1, sides)
                    result.append(new_roll)
                i += 1

        # Compounding exploding (!!): Add to original dice
        elif explode_type == '!!':
            for i in range(len(rolls)):
                value = rolls[i]
                while value == sides:
                    extra = random.randint(1, sides)
                    value += extra
                result[i] = value

        # Penetrating exploding (!p): Like exploding but -1 from extra rolls
        # Track raw values separately to check for continued explosions
        elif explode_type == '!p':
            # Process original dice
            for i in range(len(rolls)):
                if result[i] == sides:
                    # Explode: roll new die, check raw value, store penalized
                    raw_roll = random.randint(1, sides)
                    while raw_roll == sides:
                        result.append(max(1, raw_roll - 1))  # Store with -1 penalty
                        raw_roll = random.randint(1, sides)  # Roll again
                    result.append(max(1, raw_roll - 1))  # Final non-exploding roll

        return result

    def _apply_keep_drop(self, rolls: List[int], dice_set: Dict[str, Any]) -> List[int]:
        """Apply keep/drop modifiers to dice rolls, preserving original order."""
        mod_type = dice_set['mod_type']
        mod_value = dice_set['mod_value'] or 1  # Default to 1 if not specified

        # Ensure mod_value is not larger than the number of dice
        mod_value = min(mod_value, len(rolls))

        # Create indexed rolls to preserve original order
        indexed = list(enumerate(rolls))

        if mod_type == 'kh':  # Keep highest
            # Sort by value descending, take top mod_value, restore original order
            kept_indices = {i for i, _ in sorted(indexed, key=lambda x: -x[1])[:mod_value]}
            return [v for i, v in indexed if i in kept_indices]
        elif mod_type == 'kl':  # Keep lowest
            kept_indices = {i for i, _ in sorted(indexed, key=lambda x: x[1])[:mod_value]}
            return [v for i, v in indexed if i in kept_indices]
        elif mod_type == 'dh':  # Drop highest
            drop_indices = {i for i, _ in sorted(indexed, key=lambda x: -x[1])[:mod_value]}
            return [v for i, v in indexed if i not in drop_indices]
        elif mod_type == 'dl':  # Drop lowest
            drop_indices = {i for i, _ in sorted(indexed, key=lambda x: x[1])[:mod_value]}
            return [v for i, v in indexed if i not in drop_indices]

        return rolls  # Default: keep all rolls

    def _count_successes(self, rolls: List[int], dice_set: Dict[str, Any]) -> int:
        """Count successes based on target number and operator."""
        target_op = dice_set['target_op']
        target_value = dice_set['target_value']

        successes = 0

        for roll in rolls:
            success = False

            if target_op == '>':
                success = roll > target_value
            elif target_op == '>=':
                success = roll >= target_value
            elif target_op == '<':
                success = roll < target_value
            elif target_op == '<=':
                success = roll <= target_value
            elif target_op == '=':
                success = roll == target_value

            if success:
                successes += 1

        return successes

    def format_result(self) -> str:
        """Format the roll result as a readable string."""
        if self.error:
            return self.error

        if not self.result:
            self.roll()

        result = self.result

        # For simple cases, format as "total [dice]"
        if len(self.dice_sets) == 1 and not any(ds['target_op'] for ds in self.dice_sets):
            all_kept = [val for sublist in result['kept'] for val in sublist]
            return f"{result['total']} {all_kept}"

        # For more complex results, format more verbosely
        formatted = f"Result: {result['total']}\n"

        for i, (dice_set, rolls, kept) in enumerate(zip(self.dice_sets, result['rolls'], result['kept'])):
            set_description = self._describe_dice_set(dice_set)

            if dice_set['mod_type'] in ('kh', 'kl', 'dh', 'dl'):
                formatted += f"Set {i+1}: {set_description}\n"
                formatted += f"  Rolled: {rolls}\n"
                formatted += f"  Kept: {kept}\n"
            else:
                formatted += f"Set {i+1}: {set_description}\n"
                formatted += f"  Rolled: {rolls}\n"

        if self.static_mod != 0:
            formatted += f"Static modifier: {'+' if self.static_mod > 0 else ''}{self.static_mod}\n"

        return formatted

    def _describe_dice_set(self, dice_set: Dict[str, Any]) -> str:
        """Create a human-readable description of a dice set."""
        count = dice_set['count']
        sides = dice_set['sides']
        mod_type = dice_set['mod_type']
        mod_value = dice_set['mod_value']
        explode_type = dice_set['explode_type']
        target_op = dice_set['target_op']
        target_value = dice_set['target_value']

        description = f"{count}d{sides}"

        if mod_type and mod_value:
            description += f"{mod_type}{mod_value}"
        elif mod_type:
            description += f"{mod_type}"

        if explode_type:
            description += f"{explode_type}"

        if target_op and target_value is not None:
            description += f"{target_op}{target_value}"

        return description


def main():
    if len(sys.argv) != 2 or sys.argv[1] in ('--help', '-h'):
        print("Usage: python dice.py <notation>")
        print("\nExamples:")
        print("  python dice.py 2d6           # Basic roll")
        print("  python dice.py 4d6kh3        # Keep highest 3")
        print("  python dice.py 2d20+5        # With modifier")
        print("  python dice.py 3d6!          # Exploding dice")
        print("  python dice.py 5d10>7        # Count successes")
        print("  python dice.py 4dF           # Fudge/Fate dice")
        sys.exit(0 if len(sys.argv) > 1 and sys.argv[1] in ('--help', '-h') else 1)

    notation = sys.argv[1]
    dice_roll = DiceRoll(notation)
    if dice_roll.error:
        print(dice_roll.error)
        sys.exit(1)
    dice_roll.roll()
    print(dice_roll.format_result())


if __name__ == "__main__":
    main()
