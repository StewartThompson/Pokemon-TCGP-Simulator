"""Attack and Ability dataclasses for Pokemon cards."""
from dataclasses import dataclass, field
from ptcgp.cards.types import CostSymbol


@dataclass(frozen=True)
class Attack:
    name: str
    damage: int
    cost: tuple[CostSymbol, ...]
    effect_text: str = ""


@dataclass(frozen=True)
class Ability:
    name: str
    effect_text: str
    is_passive: bool = False
