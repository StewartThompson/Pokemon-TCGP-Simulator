"""Ability activation logic for the battle engine."""
from __future__ import annotations

from ptcgp.cards.database import get_card
from ptcgp.engine.actions import SlotRef
from ptcgp.engine.slot_utils import get_slot, mutate_slot
from ptcgp.engine.state import GameState


def use_ability(state: GameState, slot_ref: SlotRef) -> GameState:
    """Activate the ability of the Pokemon at ``slot_ref``.

    Passive abilities (is_passive=True) are always active and do not need activation.
    Only non-passive abilities can be activated with this function.
    """
    slot = get_slot(state, slot_ref)

    if slot is None:
        raise ValueError(f"No Pokemon at slot {slot_ref}")

    card = get_card(slot.card_id)

    if card.ability is None:
        raise ValueError(f"{card.name} has no ability")

    if card.ability.is_passive:
        raise ValueError(
            f"{card.name}'s ability '{card.ability.name}' is passive and cannot be activated manually"
        )

    if slot.ability_used_this_turn:
        raise ValueError(
            f"{card.name}'s ability '{card.ability.name}' has already been used this turn"
        )

    state = mutate_slot(state, slot_ref, lambda s: setattr(s, "ability_used_this_turn", True))

    if card.ability.effect_text or card.ability.handler:
        from ptcgp.effects.apply import apply_effects
        state = apply_effects(
            state,
            card.ability.effect_text,
            acting_player=slot_ref.player,
            source_ref=slot_ref,
            handler_str=card.ability.handler,
            cached_effects=card.ability.cached_effects,
        )

    return state
