"""Attack and Ability dataclasses for Pokemon cards."""
from dataclasses import dataclass, field
from ptcgp.cards.types import CostSymbol


@dataclass(frozen=True)
class Attack:
    name: str
    damage: int
    cost: tuple[CostSymbol, ...]
    effect_text: str = ""
    handler: str = ""  # e.g. "heal_self(amount=30)" — direct dispatch, no regex
    cached_effects: tuple = field(default_factory=tuple)  # pre-parsed at load time


@dataclass(frozen=True)
class Ability:
    name: str
    effect_text: str
    is_passive: bool = False
    handler: str = ""  # e.g. "heal_all_own(amount=20)" — direct dispatch, no regex
    cached_effects: tuple = field(default_factory=tuple)  # pre-parsed at load time
