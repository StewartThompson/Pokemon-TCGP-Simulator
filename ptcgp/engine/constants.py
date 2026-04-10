"""Game constants derived from RULES.md."""
from ptcgp.cards.types import Element

DECK_SIZE: int = 20
BENCH_SIZE: int = 3
INITIAL_HAND_SIZE: int = 5
POINTS_TO_WIN: int = 3
MAX_COPIES_PER_CARD: int = 2

# KO point values
POINTS_PER_KO: int = 1
POINTS_PER_EX_KO: int = 2
POINTS_PER_MEGA_EX_KO: int = 3

# Damage modifiers
WEAKNESS_BONUS: int = 20

# Status effect damage (applied during Pokemon Checkup)
POISON_DAMAGE: int = 10
BURN_DAMAGE: int = 20

# Turn limit: 30 turns per player = 60 total half-turns
MAX_TURNS: int = 60

# Weakness chart: defending type → attacking type that deals +20
WEAKNESS_CHART: dict[Element, Element] = {
    Element.GRASS:     Element.FIRE,
    Element.FIRE:      Element.WATER,
    Element.WATER:     Element.LIGHTNING,
    Element.LIGHTNING: Element.FIGHTING,
    Element.PSYCHIC:   Element.DARKNESS,
    Element.FIGHTING:  Element.PSYCHIC,
    Element.DARKNESS:  Element.FIGHTING,
    Element.METAL:     Element.FIRE,
}
