"""Colors, symbols, and the shared Console singleton for the terminal UI."""
from rich.console import Console

from ptcgp.cards.types import Element

# Shared Rich console — import this from anywhere in ptcgp.ui so all output
# goes through one sink.
console = Console()

ELEMENT_COLORS: dict[Element, str] = {
    Element.GRASS:     "green",
    Element.FIRE:      "red",
    Element.WATER:     "blue",
    Element.LIGHTNING: "yellow",
    Element.PSYCHIC:   "magenta",
    Element.FIGHTING:  "dark_orange",
    Element.DARKNESS:  "grey50",
    Element.METAL:     "white",
}

ELEMENT_SYMBOLS: dict[Element, str] = {
    Element.GRASS:     "🌿",
    Element.FIRE:      "🔥",
    Element.WATER:     "💧",
    Element.LIGHTNING: "⚡",
    Element.PSYCHIC:   "🔮",
    Element.FIGHTING:  "👊",
    Element.DARKNESS:  "🌑",
    Element.METAL:     "⚙️",
}

STATUS_SYMBOLS: dict = {
    "POISONED":  "☠ PSN",
    "BURNED":    "🔥 BRN",
    "PARALYZED": "⚡ PAR",
    "ASLEEP":    "💤 SLP",
    "CONFUSED":  "💫 CNF",
}


def element_str(element) -> str:
    """Return colored symbol string for an element."""
    if element is None:
        return "?"
    sym = ELEMENT_SYMBOLS.get(element, "?")
    return sym
