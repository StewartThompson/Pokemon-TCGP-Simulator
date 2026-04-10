"""Card dataclass — unified representation for Pokemon and Trainer cards."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from ptcgp.cards.types import CardKind, Element, Stage
from ptcgp.cards.attack import Attack, Ability


@dataclass(frozen=True)
class Card:
    # --- Core fields (all cards) ---
    id: str
    name: str
    kind: CardKind

    # --- Pokemon-only fields ---
    stage: Optional[Stage] = None
    element: Optional[Element] = None
    hp: int = 0
    weakness: Optional[Element] = None
    retreat_cost: int = 0
    is_ex: bool = False
    is_mega_ex: bool = False
    evolves_from: Optional[str] = None          # name of the prior-stage Pokemon
    attacks: tuple[Attack, ...] = field(default_factory=tuple)
    ability: Optional[Ability] = None

    # --- Trainer-only fields ---
    trainer_effect_text: str = ""
    trainer_handler: str = ""  # e.g. "draw_cards(count=2)" — direct dispatch
    cached_trainer_effects: tuple = field(default_factory=tuple)  # pre-parsed at load time

    # --- Properties ---

    @property
    def is_pokemon(self) -> bool:
        return self.kind == CardKind.POKEMON

    @property
    def is_basic(self) -> bool:
        return self.stage == Stage.BASIC

    @property
    def is_basic_pokemon(self) -> bool:
        return self.kind == CardKind.POKEMON and self.stage == Stage.BASIC

    @property
    def ko_points(self) -> int:
        """Points awarded to the opponent when this Pokemon is knocked out."""
        if self.is_mega_ex:
            return 3
        if self.is_ex:
            return 2
        return 1
