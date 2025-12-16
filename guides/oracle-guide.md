# Using the Oracle

The oracle tool provides randomness to stimulate interpretation. It gives you raw symbolic material—Claude (or any LLM) interprets it creatively in the context of your story.

There are no predefined meanings. A rune doesn't "mean" one thing. A hexagram doesn't dictate an outcome. The oracle provides friction, surprise, and direction. The narrative intelligence does the rest.

## When to Consult the Oracle

Use the oracle when you need:
- **Direction** - The story could go multiple ways and you want external input
- **Surprise** - You're falling into predictable patterns
- **Tone** - You need a mood or emotional register for a scene
- **Yes/No** - A character attempts something uncertain
- **Inspiration** - You're stuck and need a creative spark

Don't overuse it. The oracle works best as punctuation, not continuous narration.

## Oracle Types

### Axis Reading

```bash
python scripts/oracle.py axis
```

Multi-dimensional reading that suggests scene parameters:
- **Tone** - Emotional register (ominous, hopeful, intimate, chaotic, etc.)
- **Direction** - How the situation moves (advances, retreats, shifts, escalates, fractures, inverts)
- **Element** - What's involved (an ally, a secret, a wound, a deadline, etc.)
- **Action** - What happens (appears, transforms, reveals, threatens, etc.)
- **Twist** - Optional complication (~50% chance)

Use for: Scene setup, turning points, "what happens next?"

### Omni Reading

```bash
python scripts/oracle.py omni
```

Everything at once: axis reading + tarot + rune + I Ching + fate + prompt + d100.

Use for: Major story moments, session starts, when you want maximum input to synthesize.

### Tarot

```bash
python scripts/oracle.py tarot      # Single card
python scripts/oracle.py tarot 3    # Three cards
```

Draws from the full 78-card deck (Major and Minor Arcana).

Use for: Character insight, thematic guidance, symbolic weight.

### Runes

```bash
python scripts/oracle.py rune       # Single rune
python scripts/oracle.py rune 3     # Three runes
```

Draws from the 24 Elder Futhark runes. Each includes traditional associations.

Use for: Primal forces, Germanic/Norse themes, fundamental energies.

### I Ching

```bash
python scripts/oracle.py iching
```

Casts one of 64 hexagrams with name and core meaning.

Use for: Situational wisdom, philosophical perspective, the shape of change.

### Fate

```bash
python scripts/oracle.py fate               # Even odds
python scripts/oracle.py fate likely        # Favorable
python scripts/oracle.py fate unlikely      # Unfavorable
python scripts/oracle.py fate certain       # Very favorable
python scripts/oracle.py fate impossible    # Very unfavorable
```

Yes/no oracle with complications. Results range from "No, and..." through "Yes, and..." to "Extraordinary."

Use for: Uncertain actions, NPC reactions, whether something works.

### Prompt

```bash
python scripts/oracle.py prompt
```

Generates an Action + Theme pair (e.g., "Reveal + Secret", "Embrace + Fear").

Use for: Quick inspiration, scene seeds, character motivation nudges.

## Working with Oracle Output

The oracle provides raw material. You (or Claude) weave it into narrative.

**Example:** You roll `axis` before a scene where the protagonist enters a negotiation:

```
Tone:      Volatile
Direction: Fractures
Element:   A promise/oath
Action:    Reveals/exposes
Twist:     ...but loyalties are tested
```

This doesn't tell you what happens. It suggests that the scene should feel unstable, that something splits or breaks, that a promise is involved, that something hidden comes to light, and that someone's loyalty wavers.

How that manifests depends on your story. Maybe the negotiation falls apart. Maybe an old oath resurfaces. Maybe the protagonist's ally reveals a secret that changes everything. The oracle gave you direction; you gave it meaning.

## Combining Systems

Different oracles work well for different purposes:

| Need | Oracle |
|------|--------|
| Scene mood/direction | Axis |
| Yes/no with stakes | Fate |
| Deep symbolic weight | Tarot, I Ching |
| Primal/elemental force | Runes |
| Quick inspiration | Prompt |
| Everything at once | Omni |

You can also chain them: use `fate` to determine if something succeeds, then `axis` to determine the consequences.

## Philosophy

The oracle is a partner, not an authority. It injects the unexpected—the thing you wouldn't have thought of—and trusts you to make it meaningful.

When the oracle gives you something that doesn't seem to fit, that's often the most interesting moment. The tension between "this doesn't fit" and "but the oracle said it" can crack open new story directions.

Don't fight the oracle. Don't reroll until you get what you wanted. Lean into the friction. That's where the emergent narrative lives.
