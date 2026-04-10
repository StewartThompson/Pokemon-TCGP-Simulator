"""Item card effect handlers — rare_candy_evolve."""
from __future__ import annotations

from ptcgp.cards.database import get_card
from ptcgp.effects.registry import EffectContext, register_effect
from ptcgp.engine.slot_utils import get_slot, set_slot
from ptcgp.engine.state import GameState


@register_effect("rare_candy_evolve")
def rare_candy_evolve(ctx: EffectContext) -> GameState:
    """Evolve a Basic Pokemon directly to Stage 2, skipping Stage 1.

    Reads:
      - ``ctx.target_ref``: which Basic Pokemon in play to evolve.
      - ``ctx.extra["evo_card_id"]``: the Stage 2 card ID.
      - ``ctx.extra["evo_hand_index"]``: the index of the Stage 2 card in the
        acting player's hand (so it can be removed after the evolution).

    ``legal_actions`` already guarantees the evolution path is valid and the
    turn restrictions are satisfied; this handler just performs the swap.
    """
    state = ctx.state
    if ctx.target_ref is None:
        return state

    evo_card_id = ctx.extra.get("evo_card_id")
    evo_hand_index = ctx.extra.get("evo_hand_index")
    if not evo_card_id:
        return state

    old_slot = get_slot(state, ctx.target_ref)
    if old_slot is None:
        return state

    new_card = get_card(evo_card_id)

    # Preserve damage taken across the evolution.
    damage_taken = old_slot.max_hp - old_slot.current_hp
    new_hp = max(0, new_card.hp - damage_taken)

    new_slot = old_slot.copy()
    new_slot.card_id = evo_card_id
    new_slot.max_hp = new_card.hp
    new_slot.current_hp = new_hp
    new_slot.status_effects = set()
    new_slot.evolved_this_turn = True
    new_slot.ability_used_this_turn = False

    state = set_slot(state, ctx.target_ref, new_slot)

    # Remove the Stage 2 card from the acting player's hand.
    if evo_hand_index is not None:
        state = state.copy()
        p = state.players[ctx.acting_player]
        if 0 <= evo_hand_index < len(p.hand) and p.hand[evo_hand_index] == evo_card_id:
            p.hand.pop(evo_hand_index)

    return state
