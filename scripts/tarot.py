#!/usr/bin/env python3
"""Tarot card drawing tool for solo RPG games."""

import random
import sys

# Tarot card data
TAROT_CARDS = {
    "majorArcana": [
        "The Fool", "The Magician", "The High Priestess", "The Empress",
        "The Emperor", "The Hierophant", "The Lovers", "The Chariot",
        "Strength", "The Hermit", "Wheel of Fortune", "Justice",
        "The Hanged Man", "Death", "Temperance", "The Devil",
        "The Tower", "The Star", "The Moon", "The Sun",
        "Judgement", "The World"
    ],
    "minorArcana": {
        "wands": ["Ace of Wands", "Two of Wands", "Three of Wands", "Four of Wands", "Five of Wands",
                "Six of Wands", "Seven of Wands", "Eight of Wands", "Nine of Wands", "Ten of Wands",
                "Page of Wands", "Knight of Wands", "Queen of Wands", "King of Wands"],
        "cups": ["Ace of Cups", "Two of Cups", "Three of Cups", "Four of Cups", "Five of Cups",
                "Six of Cups", "Seven of Cups", "Eight of Cups", "Nine of Cups", "Ten of Cups",
                "Page of Cups", "Knight of Cups", "Queen of Cups", "King of Cups"],
        "swords": ["Ace of Swords", "Two of Swords", "Three of Swords", "Four of Swords", "Five of Swords",
                "Six of Swords", "Seven of Swords", "Eight of Swords", "Nine of Swords", "Ten of Swords",
                "Page of Swords", "Knight of Swords", "Queen of Swords", "King of Swords"],
        "pentacles": ["Ace of Pentacles", "Two of Pentacles", "Three of Pentacles", "Four of Pentacles", "Five of Pentacles",
                    "Six of Pentacles", "Seven of Pentacles", "Eight of Pentacles", "Nine of Pentacles", "Ten of Pentacles",
                    "Page of Pentacles", "Knight of Pentacles", "Queen of Pentacles", "King of Pentacles"]
    }
}

# Flatten the card list for easier random selection
ALL_CARDS = (
    TAROT_CARDS["majorArcana"] +
    TAROT_CARDS["minorArcana"]["wands"] +
    TAROT_CARDS["minorArcana"]["cups"] +
    TAROT_CARDS["minorArcana"]["swords"] +
    TAROT_CARDS["minorArcana"]["pentacles"]
)


def draw_card():
    """Draw a single tarot card."""
    return random.choice(ALL_CARDS)


def draw_spread(num_cards):
    """Draw multiple tarot cards to form a spread."""
    if num_cards < 1:
        print("Error: Please request at least one card.")
        sys.exit(1)
    if num_cards > 10:
        print("Error: Maximum 10 cards can be drawn at once.")
        sys.exit(1)

    cards = random.sample(ALL_CARDS, min(num_cards, len(ALL_CARDS)))
    for i, card in enumerate(cards, 1):
        print(f"{i}. {card}")


def main():
    if len(sys.argv) == 1:
        # No arguments: draw single card
        print(draw_card())
    elif len(sys.argv) == 2:
        # One argument: draw spread
        try:
            num_cards = int(sys.argv[1])
            draw_spread(num_cards)
        except ValueError:
            print(f"Error: '{sys.argv[1]}' is not a valid number")
            print("Usage: python tarot.py [num_cards]")
            print("  No arguments: draw single card")
            print("  num_cards: draw a spread of N cards (1-10)")
            sys.exit(1)
    else:
        print("Usage: python tarot.py [num_cards]")
        print("  No arguments: draw single card")
        print("  num_cards: draw a spread of N cards (1-10)")
        sys.exit(1)


if __name__ == "__main__":
    main()
