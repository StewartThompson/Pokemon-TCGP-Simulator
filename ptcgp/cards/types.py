"""Enums for card types used throughout the simulator."""
from enum import Enum


class Element(Enum):
    """The 8 real energy types. These are the only types that exist in the
    Energy Zone or can be attached to a Pokemon. Colorless is NOT included."""
    GRASS = "Grass"
    FIRE = "Fire"
    WATER = "Water"
    LIGHTNING = "Lightning"
    PSYCHIC = "Psychic"
    FIGHTING = "Fighting"
    DARKNESS = "Darkness"
    METAL = "Metal"

    @classmethod
    def from_str(cls, value: str) -> "Element":
        for member in cls:
            if member.value.lower() == value.strip().lower():
                return member
        raise ValueError(f"Unknown Element: {value!r}")


class CostSymbol(Enum):
    """All symbols that can appear in an attack's energy cost list.
    Includes all 8 Elements plus COLORLESS (meaning 'any energy type')."""
    GRASS = "Grass"
    FIRE = "Fire"
    WATER = "Water"
    LIGHTNING = "Lightning"
    PSYCHIC = "Psychic"
    FIGHTING = "Fighting"
    DARKNESS = "Darkness"
    METAL = "Metal"
    COLORLESS = "Colorless"

    @classmethod
    def from_str(cls, value: str) -> "CostSymbol":
        for member in cls:
            if member.value.lower() == value.strip().lower():
                return member
        raise ValueError(f"Unknown CostSymbol: {value!r}")

    def to_element(self) -> "Element":
        """Convert to Element (raises for COLORLESS)."""
        if self == CostSymbol.COLORLESS:
            raise ValueError("COLORLESS has no corresponding Element")
        return Element(self.value)


class Stage(Enum):
    BASIC = "Basic"
    STAGE_1 = "Stage 1"
    STAGE_2 = "Stage 2"

    @classmethod
    def from_str(cls, value: str) -> "Stage":
        mapping = {
            "basic": cls.BASIC,
            "stage 1": cls.STAGE_1,
            "stage1": cls.STAGE_1,
            "stage 2": cls.STAGE_2,
            "stage2": cls.STAGE_2,
        }
        key = value.strip().lower()
        if key in mapping:
            return mapping[key]
        raise ValueError(f"Unknown Stage: {value!r}")


class CardKind(Enum):
    POKEMON = "Pokemon"
    ITEM = "Item"
    SUPPORTER = "Supporter"
    TOOL = "Tool"

    @classmethod
    def from_str(cls, value: str) -> "CardKind":
        mapping = {
            "pokemon": cls.POKEMON,
            "item": cls.ITEM,
            "supporter": cls.SUPPORTER,
            "tool": cls.TOOL,
        }
        key = value.strip().lower()
        if key in mapping:
            return mapping[key]
        raise ValueError(f"Unknown CardKind: {value!r}")
