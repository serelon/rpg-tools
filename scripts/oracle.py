#!/usr/bin/env python3
"""Oracle systems for solo RPG games.

Multi-system oracle tool designed to stimulate LLM imagination by injecting
unexpected context and friction into storytelling.
"""

import random
import sys

# =============================================================================
# AXIS ORACLE - Multi-dimensional reading
# =============================================================================

TONE = [
    "Ominous",
    "Desperate",
    "Tense",
    "Melancholy",
    "Mysterious",
    "Volatile",
    "Quiet",
    "Hopeful",
    "Triumphant",
    "Chaotic",
    "Intimate",
    "Uncanny",
]

# Weighted toward interesting results (shifts/escalates more likely)
DIRECTION = [
    "Advances",      # progress toward goal
    "Retreats",      # setback, loss of ground
    "Shifts",        # tangent, new angle
    "Shifts",        # (weighted)
    "Escalates",     # stakes rise
    "Stalls",        # pause, tension builds
    "Fractures",     # something breaks/splits
    "Inverts",       # reversal, opposite of expected
]

ELEMENT = [
    "An ally",
    "An enemy",
    "A stranger",
    "The self",
    "A group/faction",
    "A place",
    "An object",
    "A secret",
    "A promise/oath",
    "A memory",
    "A resource",
    "A barrier",
    "A message",
    "A wound",
    "A power/ability",
    "A relationship",
    "A belief",
    "A deadline/pressure",
    "An opportunity",
    "A debt/obligation",
]

ACTION = [
    "Appears/arrives",
    "Vanishes/departs",
    "Transforms/changes",
    "Breaks/fails",
    "Connects/binds",
    "Reveals/exposes",
    "Conceals/obscures",
    "Demands/compels",
    "Offers/tempts",
    "Threatens/endangers",
    "Protects/shields",
    "Echoes/repeats",
]

# ~50% chance of complication
TWIST = [
    None,
    None,
    None,
    "...but loyalties are tested",
    "...but it costs something",
    "...but something else stirs",
]


def axis_reading():
    """Generate a multi-axis oracle reading."""
    return {
        "tone": random.choice(TONE),
        "direction": random.choice(DIRECTION),
        "element": random.choice(ELEMENT),
        "action": random.choice(ACTION),
        "twist": random.choice(TWIST),
    }


def print_axis(reading):
    """Print axis reading in a clean format."""
    print(f"Tone:      {reading['tone']}")
    print(f"Direction: {reading['direction']}")
    print(f"Element:   {reading['element']}")
    print(f"Action:    {reading['action']}")
    if reading['twist']:
        print(f"Twist:     {reading['twist']}")


# =============================================================================
# RUNES - Elder Futhark (24)
# =============================================================================

RUNES = [
    ("Fehu", "wealth, cattle, prosperity, energy"),
    ("Uruz", "strength, endurance, untamed potential"),
    ("Thurisaz", "thorn, giant, danger, conflict, catalyst"),
    ("Ansuz", "signals, mouth, communication, wisdom, Odin"),
    ("Raidho", "journey, riding, movement, rhythm"),
    ("Kenaz", "torch, knowledge, illumination, craft"),
    ("Gebo", "gift, exchange, balance, partnership"),
    ("Wunjo", "joy, harmony, fellowship, fulfillment"),
    ("Hagalaz", "hail, disruption, uncontrolled forces"),
    ("Nauthiz", "need, constraint, necessity, endurance"),
    ("Isa", "ice, stillness, stagnation, waiting"),
    ("Jera", "year, harvest, cycles, patience rewarded"),
    ("Eihwaz", "yew, death/rebirth, endurance, axis"),
    ("Perthro", "dice cup, fate, mystery, the unknown"),
    ("Algiz", "elk-sedge, protection, sanctuary, awareness"),
    ("Sowilo", "sun, victory, vitality, guidance"),
    ("Tiwaz", "Tyr, justice, sacrifice, honor, victory"),
    ("Berkano", "birch, growth, renewal, nurturing"),
    ("Ehwaz", "horse, partnership, trust, movement"),
    ("Mannaz", "humanity, self, interdependence"),
    ("Laguz", "water, flow, intuition, the unconscious"),
    ("Ingwaz", "Ing, fertility, internal growth, potential"),
    ("Dagaz", "day, breakthrough, transformation, dawn"),
    ("Othala", "heritage, inheritance, home, legacy"),
]


def rune_draw(count=1):
    """Draw runes without replacement."""
    count = min(count, len(RUNES))
    return random.sample(RUNES, count)


def print_runes(runes):
    """Print runes with their meanings."""
    for name, meaning in runes:
        print(f"{name}: {meaning}")


# =============================================================================
# I CHING - 64 Hexagrams
# =============================================================================

HEXAGRAMS = [
    (1, "Qian", "The Creative", "pure yang, heaven, strength, initiative"),
    (2, "Kun", "The Receptive", "pure yin, earth, yielding, devotion"),
    (3, "Zhun", "Difficulty at the Beginning", "birth pains, chaos before order"),
    (4, "Meng", "Youthful Folly", "inexperience, learning, seeking guidance"),
    (5, "Xu", "Waiting", "patience, nourishment, clouds gathering"),
    (6, "Song", "Conflict", "opposition, caution against aggression"),
    (7, "Shi", "The Army", "discipline, organization, collective force"),
    (8, "Bi", "Holding Together", "union, seeking allies, belonging"),
    (9, "Xiao Chu", "Small Taming", "gentle restraint, small accumulations"),
    (10, "Lu", "Treading", "conduct, careful steps, treading on tiger's tail"),
    (11, "Tai", "Peace", "harmony, heaven and earth in communion"),
    (12, "Pi", "Standstill", "stagnation, blocked communication"),
    (13, "Tong Ren", "Fellowship", "community, shared purpose"),
    (14, "Da You", "Great Possession", "abundance, supreme success"),
    (15, "Qian", "Modesty", "humility, balance, the mountain within earth"),
    (16, "Yu", "Enthusiasm", "joy in movement, momentum, thunder over earth"),
    (17, "Sui", "Following", "adapting, going with, attraction"),
    (18, "Gu", "Work on the Decayed", "repair, correcting what went wrong"),
    (19, "Lin", "Approach", "advance, growing influence, spring coming"),
    (20, "Guan", "Contemplation", "observation, perspective from height"),
    (21, "Shi He", "Biting Through", "decisive action, breaking obstacles"),
    (22, "Bi", "Grace", "beauty, form, adornment over substance"),
    (23, "Bo", "Splitting Apart", "decay, deterioration, shedding"),
    (24, "Fu", "Return", "turning point, renewal, the light returns"),
    (25, "Wu Wang", "Innocence", "spontaneity, unexpected, without guile"),
    (26, "Da Chu", "Great Taming", "restraint of great power, accumulation"),
    (27, "Yi", "Nourishment", "what we take in, what we give out"),
    (28, "Da Guo", "Great Exceeding", "critical mass, the beam sags"),
    (29, "Kan", "The Abysmal", "water, repeated danger, depth"),
    (30, "Li", "The Clinging", "fire, clarity, dependence, illumination"),
    (31, "Xian", "Influence", "attraction, mutual resonance, courtship"),
    (32, "Heng", "Duration", "perseverance, enduring, marriage"),
    (33, "Dun", "Retreat", "withdrawal, strategic retreat, not flight"),
    (34, "Da Zhuang", "Great Power", "strength in movement, thunder in heaven"),
    (35, "Jin", "Progress", "sunrise, advancing, rapid progress"),
    (36, "Ming Yi", "Darkening of the Light", "injury, hiding brightness, eclipse"),
    (37, "Jia Ren", "The Family", "household, inner relationships"),
    (38, "Kui", "Opposition", "estrangement, misunderstanding, fire and water"),
    (39, "Jian", "Obstruction", "difficulty, the mountain before you"),
    (40, "Xie", "Deliverance", "release, relief, thunder and rain"),
    (41, "Sun", "Decrease", "sacrifice, giving up, simplification"),
    (42, "Yi", "Increase", "gain, benefit, wind and thunder"),
    (43, "Guai", "Breakthrough", "determination, removing corruption"),
    (44, "Gou", "Coming to Meet", "unexpected encounter, temptation"),
    (45, "Cui", "Gathering Together", "assembly, the lake rises"),
    (46, "Sheng", "Pushing Upward", "gradual advance, growing within earth"),
    (47, "Kun", "Oppression", "exhaustion, confined, adversity"),
    (48, "Jing", "The Well", "unchanging source, community resource"),
    (49, "Ge", "Revolution", "fundamental change, molting, fire in lake"),
    (50, "Ding", "The Cauldron", "transformation, nourishment, civilization"),
    (51, "Zhen", "The Arousing", "shock, thunder, sudden awakening"),
    (52, "Gen", "Keeping Still", "mountain, meditation, stillness"),
    (53, "Jian", "Development", "gradual progress, tree on mountain"),
    (54, "Gui Mei", "The Marrying Maiden", "subordinate position, improper unions"),
    (55, "Feng", "Abundance", "fullness, zenith, thunder and lightning"),
    (56, "Lu", "The Wanderer", "travel, stranger, impermanence"),
    (57, "Xun", "The Gentle", "wind, penetrating, subtle influence"),
    (58, "Dui", "The Joyous", "lake, pleasure, exchange, openness"),
    (59, "Huan", "Dispersion", "dissolving, wind over water, scattering"),
    (60, "Jie", "Limitation", "boundaries, restraint, articulation"),
    (61, "Zhong Fu", "Inner Truth", "sincerity, confidence, the empty heart"),
    (62, "Xiao Guo", "Small Exceeding", "small preponderance, attention to detail"),
    (63, "Ji Ji", "After Completion", "order achieved, vigilance needed"),
    (64, "Wei Ji", "Before Completion", "almost there, transition, fox crossing ice"),
]


def iching_reading():
    """Cast a hexagram."""
    return random.choice(HEXAGRAMS)


def print_iching(hexagram):
    """Print hexagram reading."""
    num, pinyin, name, meaning = hexagram
    print(f"{num}. {name} ({pinyin})")
    print(f"   {meaning}")


# =============================================================================
# FATE ORACLE - Weighted yes/no with complications
# =============================================================================

FATE_TABLE = [
    # (min, max, result)
    (1, 10, "No, and..."),      # hard no + consequence
    (11, 25, "No"),             # simple no
    (26, 40, "No, but..."),     # no with silver lining
    (41, 60, "Yes, but..."),    # yes with cost/complication
    (61, 80, "Yes"),            # simple yes
    (81, 95, "Yes, and..."),    # yes with bonus
    (96, 100, "Extraordinary"), # something unexpected entirely
]

LIKELIHOOD_MODS = {
    "impossible": -40,
    "unlikely": -20,
    "even": 0,
    "likely": 20,
    "certain": 40,
}


def fate_roll(likelihood="even"):
    """Roll on the fate table with optional likelihood modifier."""
    mod = LIKELIHOOD_MODS.get(likelihood.lower(), 0)
    roll = random.randint(1, 100)
    modified = max(1, min(100, roll + mod))

    for min_val, max_val, result in FATE_TABLE:
        if min_val <= modified <= max_val:
            return {"roll": roll, "modified": modified, "likelihood": likelihood, "result": result}

    return {"roll": roll, "modified": modified, "likelihood": likelihood, "result": "Yes"}


def print_fate(fate):
    """Print fate result."""
    if fate["likelihood"] != "even":
        print(f"Fate ({fate['likelihood']}): {fate['result']}")
    else:
        print(f"Fate: {fate['result']}")


# =============================================================================
# PROMPT - Action/Theme word pairs
# =============================================================================

ACTIONS = [
    "Reveal", "Conceal", "Advance", "Retreat", "Create", "Destroy",
    "Unite", "Divide", "Protect", "Threaten", "Offer", "Demand",
    "Betray", "Honor", "Pursue", "Abandon", "Transform", "Preserve",
    "Challenge", "Yield", "Awaken", "Suppress", "Liberate", "Bind",
    "Seek", "Avoid", "Embrace", "Reject", "Question", "Affirm",
    "Remember", "Forget", "Claim", "Surrender", "Ignite", "Extinguish",
    "Open", "Close", "Ascend", "Descend", "Gather", "Scatter",
    "Heal", "Wound", "Trust", "Doubt", "Begin", "End",
]

THEMES = [
    "Secret", "Power", "Love", "Fear", "Hope", "Duty",
    "Freedom", "Tradition", "Change", "Identity", "Truth", "Illusion",
    "Sacrifice", "Ambition", "Innocence", "Corruption", "Justice", "Mercy",
    "Vengeance", "Forgiveness", "Faith", "Doubt", "Pride", "Shame",
    "Bond", "Isolation", "Home", "Exile", "Legacy", "Oblivion",
    "Nature", "Civilization", "Chaos", "Order", "Past", "Future",
    "Wealth", "Poverty", "Knowledge", "Mystery", "Life", "Death",
    "Sanctuary", "Threat", "Promise", "Betrayal", "Gift", "Curse",
]


def prompt_pair():
    """Generate an action + theme pair."""
    return (random.choice(ACTIONS), random.choice(THEMES))


def print_prompt(pair):
    """Print prompt pair."""
    print(f"Prompt: {pair[0]} + {pair[1]}")


# =============================================================================
# TAROT - Full deck (can also use tarot.py standalone)
# =============================================================================

MAJOR_ARCANA = [
    "The Fool", "The Magician", "The High Priestess", "The Empress",
    "The Emperor", "The Hierophant", "The Lovers", "The Chariot",
    "Strength", "The Hermit", "Wheel of Fortune", "Justice",
    "The Hanged Man", "Death", "Temperance", "The Devil",
    "The Tower", "The Star", "The Moon", "The Sun",
    "Judgement", "The World"
]

MINOR_ARCANA = []
for suit in ["Wands", "Cups", "Swords", "Pentacles"]:
    for rank in ["Ace", "Two", "Three", "Four", "Five", "Six", "Seven",
                 "Eight", "Nine", "Ten", "Page", "Knight", "Queen", "King"]:
        MINOR_ARCANA.append(f"{rank} of {suit}")

ALL_TAROT = MAJOR_ARCANA + MINOR_ARCANA


def tarot_draw(count=1):
    """Draw tarot cards without replacement."""
    count = min(count, len(ALL_TAROT))
    return random.sample(ALL_TAROT, count)


def print_tarot(cards):
    """Print tarot cards."""
    if len(cards) == 1:
        print(f"Tarot: {cards[0]}")
    else:
        print("Tarot:")
        for i, card in enumerate(cards, 1):
            print(f"  {i}. {card}")


# =============================================================================
# OMNI - Everything at once
# =============================================================================

def omni_reading():
    """Generate a reading from all systems."""
    return {
        "axis": axis_reading(),
        "tarot": tarot_draw(1)[0],
        "rune": rune_draw(1)[0],
        "iching": iching_reading(),
        "fate": fate_roll("even"),
        "prompt": prompt_pair(),
        "d100": random.randint(1, 100),
    }


def print_omni(reading):
    """Print full omni reading."""
    print("=" * 50)
    print("OMNI READING")
    print("=" * 50)
    print()

    # Axis
    print("-- Axis --")
    print_axis(reading["axis"])
    print()

    # Traditional
    print("-- Traditional --")
    print(f"Tarot:   {reading['tarot']}")
    rune_name, rune_meaning = reading["rune"]
    print(f"Rune:    {rune_name} ({rune_meaning})")
    num, pinyin, name, meaning = reading["iching"]
    print(f"I Ching: {num}. {name} - {meaning}")
    print()

    # Oracles
    print("-- Oracle --")
    print(f"Fate:    {reading['fate']['result']}")
    print(f"Prompt:  {reading['prompt'][0]} + {reading['prompt'][1]}")
    print(f"d100:    {reading['d100']}")
    print()
    print("=" * 50)


# =============================================================================
# CLI
# =============================================================================

def print_usage():
    """Print usage information."""
    print("Usage: python oracle.py <command> [args]")
    print()
    print("Commands:")
    print("  axis              Multi-axis reading (tone/direction/element/action/twist)")
    print("  omni              Full reading from all systems")
    print("  tarot [n]         Draw tarot card(s), default 1")
    print("  rune [n]          Draw rune(s), default 1")
    print("  iching            Cast I Ching hexagram")
    print("  fate [likelihood] Yes/no oracle (impossible/unlikely/even/likely/certain)")
    print("  prompt            Action + Theme word pair")
    print()
    print("Examples:")
    print("  python oracle.py axis")
    print("  python oracle.py omni")
    print("  python oracle.py tarot 3")
    print("  python oracle.py fate likely")


def main():
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == "axis":
        print_axis(axis_reading())

    elif command == "omni":
        print_omni(omni_reading())

    elif command == "tarot":
        count = 1
        if len(sys.argv) > 2:
            try:
                count = int(sys.argv[2])
            except ValueError:
                print(f"Error: '{sys.argv[2]}' is not a valid number")
                sys.exit(1)
        if count < 1 or count > 10:
            print("Error: Draw 1-10 cards")
            sys.exit(1)
        print_tarot(tarot_draw(count))

    elif command == "rune":
        count = 1
        if len(sys.argv) > 2:
            try:
                count = int(sys.argv[2])
            except ValueError:
                print(f"Error: '{sys.argv[2]}' is not a valid number")
                sys.exit(1)
        if count < 1 or count > 24:
            print("Error: Draw 1-24 runes")
            sys.exit(1)
        print_runes(rune_draw(count))

    elif command == "iching":
        print_iching(iching_reading())

    elif command == "fate":
        likelihood = "even"
        if len(sys.argv) > 2:
            likelihood = sys.argv[2].lower()
            if likelihood not in LIKELIHOOD_MODS:
                print(f"Error: Unknown likelihood '{likelihood}'")
                print("Options: impossible, unlikely, even, likely, certain")
                sys.exit(1)
        print_fate(fate_roll(likelihood))

    elif command == "prompt":
        print_prompt(prompt_pair())

    elif command in ["help", "-h", "--help"]:
        print_usage()

    else:
        print(f"Error: Unknown command '{command}'")
        print_usage()
        sys.exit(1)


if __name__ == "__main__":
    main()
