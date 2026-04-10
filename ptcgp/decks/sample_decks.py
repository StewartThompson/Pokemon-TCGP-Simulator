"""Pre-built sample decks using a1-genetic-apex (and related) cards.

All included cards have been verified to pass ``is_card_fully_implemented``.
Both decks contain exactly 20 cards with no more than 2 copies of any card.
"""
from __future__ import annotations

from ptcgp.cards.types import Element


# ---------------------------------------------------------------------------
# Grass deck — Bulbasaur / Ivysaur / Venusaur ex + Caterpie line + Petilil line
# ---------------------------------------------------------------------------
GRASS_DECK: list[str] = [
    "a1-001", "a1-001",   # Bulbasaur x2
    "a1-002", "a1-002",   # Ivysaur x2
    "a1-004", "a1-004",   # Venusaur ex x2
    "a1-225", "a1-225",   # Sabrina x2
    "a1-219", "a1-219",   # Erika x2
    "pa-005", "pa-005",   # Pokeball x2
    "a1-029", "a1-029",   # Petilil x2
    "a1-030", "a1-030",   # Lilligant x2
    "pa-001", "pa-001",   # Potion x2
    "pa-007", "pa-007",   # Professor's Research x2
]  # 20 cards

# ---------------------------------------------------------------------------
# Fire deck — Charmander / Charizard ex + Vulpix / Ninetales + Weedle line
# ---------------------------------------------------------------------------
FIRE_DECK: list[str] = [
    "a1-230", "a1-230",   # Charmander x2
    "a2b-010", "a2b-010", # Charizard ex x2
    "a1-037", "a1-037",   # Vulpix x2
    "a1-038", "a1-038",   # Ninetales x2
    "a3-144", "a3-144",   # Rare Candy x2
    "a2-154", "a2-154",   # Dawn x2
    "a2-148", "a2-148",   # Beedrill x2
    "pa-005", "pa-005",   # Poke Ball x2
    "pa-001", "pa-001",   # Potion x2
    "a2-147", "a2-147",   # Giant Cape x2
]  # 20 cards

GRASS_ENERGY_TYPES: list[Element] = [Element.GRASS]
FIRE_ENERGY_TYPES: list[Element] = [Element.FIRE]

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
_SAMPLE_DECKS: dict[str, tuple[list[str], list[Element]]] = {
    "grass": (GRASS_DECK, GRASS_ENERGY_TYPES),
    "fire": (FIRE_DECK, FIRE_ENERGY_TYPES),
}


def get_sample_deck(name: str) -> tuple[list[str], list[Element]]:
    """Return ``(card_ids, energy_types)`` for a named sample deck.

    Parameters
    ----------
    name : One of ``"grass"`` or ``"fire"`` (case-insensitive).

    Raises
    ------
    KeyError
        If the requested deck name is not found.
    """
    key = name.strip().lower()
    if key not in _SAMPLE_DECKS:
        available = ", ".join(sorted(_SAMPLE_DECKS))
        raise KeyError(
            f"Unknown sample deck {name!r}. Available decks: {available}"
        )
    card_ids, energy_types = _SAMPLE_DECKS[key]
    # Return copies so callers cannot mutate the module-level constants
    return list(card_ids), list(energy_types)
