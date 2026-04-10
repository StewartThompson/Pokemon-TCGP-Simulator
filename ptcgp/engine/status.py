"""Status effect application logic for the battle engine."""
from __future__ import annotations

from ptcgp.engine.state import GameState, StatusEffect
from ptcgp.engine.actions import SlotRef
from ptcgp.engine.slot_utils import get_slot, set_slot


def apply_status(state: GameState, target: SlotRef, effect: StatusEffect) -> GameState:
    """Apply a status effect to the Pokemon at target slot.

    Status effects can only be applied to the Active Pokemon (not bench).
    Multiple effects can coexist — all 5 statuses can stack.
    """
    if not target.is_active():
        raise ValueError(
            f"Status effects can only be applied to the Active Pokemon, not bench slot {target.slot}"
        )

    slot = get_slot(state, target)
    if slot is None:
        raise ValueError(f"No Pokemon at active slot for player {target.player}")

    new_slot = slot.copy()
    new_slot.status_effects.add(effect)

    state = set_slot(state, target, new_slot)
    return state
