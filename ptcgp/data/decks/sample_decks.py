"""Sample pre-built decks for PTCGP."""

from ptcgp.engine.types import EnergyType


# Grass deck - Bulbasaur evolution line + support
GRASS_DECK = {
    "name": "Grass Power",
    "cards": [
        "a1-001", "a1-001",  # Bulbasaur x2
        "a1-002", "a1-002",  # Ivysaur x2
        "a1-004",            # Venusaur ex
        "a1-005", "a1-005",  # Caterpie x2
        "a1-006", "a1-006",  # Metapod x2
        "a1-007",            # Butterfree
        "a1-008", "a1-008",  # Weedle x2
        "a1-029", "a1-029",  # Petilil x2
        "pa-001", "pa-001",  # Potion x2
        "pa-007", "pa-007",  # Professor's Research x2
        "pa-005",            # Poke Ball
    ],
    "energy_types": [EnergyType.GRASS],
}

# Fire deck - Charmander line + Vulpix
FIRE_DECK = {
    "name": "Fire Storm",
    "cards": [
        "a1-230", "a1-230",  # Charmander x2
        "a1-037", "a1-037",  # Vulpix x2
        "a1-038", "a1-038",  # Ninetales x2
        "a1-029", "a1-029",  # Petilil x2 (filler basics)
        "a1-005", "a1-005",  # Caterpie x2 (filler basics)
        "a1-008", "a1-008",  # Weedle x2 (filler basics)
        "pa-001", "pa-001",  # Potion x2
        "pa-007", "pa-007",  # Professor's Research x2
        "pa-005", "pa-005",  # Poke Ball x2
    ],
    "energy_types": [EnergyType.FIRE],
}

ALL_DECKS = {
    "grass": GRASS_DECK,
    "fire": FIRE_DECK,
}


def get_deck(name: str) -> dict:
    """Get a deck by name."""
    return ALL_DECKS[name.lower()]


def list_decks() -> list[str]:
    """List available deck names."""
    return list(ALL_DECKS.keys())
