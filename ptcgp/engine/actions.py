"""Action types for the game engine."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import NamedTuple, Optional


class SlotRef(NamedTuple):
    """Reference to a Pokemon slot on the board.

    player: 0 or 1
    slot:   -1 = active slot; 0-2 = bench index
    """
    player: int
    slot: int  # -1 = active, 0-2 = bench

    @classmethod
    def active(cls, player: int) -> "SlotRef":
        return cls(player=player, slot=-1)

    @classmethod
    def bench(cls, player: int, index: int) -> "SlotRef":
        assert 0 <= index <= 2
        return cls(player=player, slot=index)

    def is_active(self) -> bool:
        return self.slot == -1

    def is_bench(self) -> bool:
        return self.slot >= 0


class ActionKind(Enum):
    PLAY_CARD = "play_card"          # play a card from hand (basic, item, supporter, tool)
    ATTACH_ENERGY = "attach_energy"  # attach Energy Zone energy to a Pokemon
    EVOLVE = "evolve"                # evolve a Pokemon in play
    USE_ABILITY = "use_ability"      # activate an active ability
    RETREAT = "retreat"              # retreat active → bench swap
    ATTACK = "attack"                # declare an attack (ends turn)
    END_TURN = "end_turn"            # pass without attacking
    PROMOTE = "promote"              # choose bench Pokemon to replace KO'd active


@dataclass(frozen=True)
class Action:
    kind: ActionKind

    # PLAY_CARD: index in hand list
    hand_index: Optional[int] = None

    # PLAY_CARD (basic to bench), ATTACH_ENERGY, EVOLVE, USE_ABILITY: destination slot
    # RETREAT: which bench Pokemon to swap in
    # PROMOTE: which bench slot to promote
    target: Optional[SlotRef] = None

    # ATTACK: 0 or 1 (index into card's attacks list)
    attack_index: Optional[int] = None

    # Secondary hand index — used by Rare Candy to point at the Stage 2 card
    # that will be consumed alongside the Rare Candy itself.
    extra_hand_index: Optional[int] = None

    def __repr__(self) -> str:
        parts = [f"Action({self.kind.name}"]
        if self.hand_index is not None:
            parts.append(f" hand={self.hand_index}")
        if self.extra_hand_index is not None:
            parts.append(f" extra_hand={self.extra_hand_index}")
        if self.target is not None:
            slot_str = "active" if self.target.is_active() else f"bench[{self.target.slot}]"
            parts.append(f" target=p{self.target.player}:{slot_str}")
        if self.attack_index is not None:
            parts.append(f" atk={self.attack_index}")
        parts.append(")")
        return "".join(parts)
