"""Heal effect handlers — heal_self, heal_all_own, heal_target, heal_grass_target."""
from __future__ import annotations

from typing import Optional

from ptcgp.cards.database import get_card
from ptcgp.cards.types import Element
from ptcgp.effects.registry import EffectContext, register_effect
from ptcgp.engine.actions import SlotRef
from ptcgp.engine.slot_utils import get_slot, mutate_slot
from ptcgp.engine.state import GameState


def _heal_slot(state: GameState, ref: SlotRef, amount: int) -> GameState:
    return mutate_slot(
        state,
        ref,
        lambda s: setattr(s, "current_hp", min(s.max_hp, s.current_hp + amount)),
    )


def _most_damaged(
    state: GameState,
    player_index: int,
    element_filter: Optional[Element] = None,
) -> Optional[SlotRef]:
    """Return a SlotRef for the player's most-damaged Pokemon, or None."""
    player = state.players[player_index]
    best: Optional[tuple[int, SlotRef]] = None

    def consider(slot, ref: SlotRef) -> None:
        nonlocal best
        if slot is None:
            return
        if element_filter is not None:
            card = get_card(slot.card_id)
            if card.element != element_filter:
                return
        damage = slot.max_hp - slot.current_hp
        if damage <= 0:
            return
        if best is None or damage > best[0]:
            best = (damage, ref)

    consider(player.active, SlotRef.active(player_index))
    for i, bench_slot in enumerate(player.bench):
        consider(bench_slot, SlotRef.bench(player_index, i))

    return best[1] if best else None


@register_effect("heal_self")
def heal_self(ctx: EffectContext, amount: int) -> GameState:
    if ctx.source_ref is None:
        return ctx.state
    return _heal_slot(ctx.state, ctx.source_ref, amount)


@register_effect("heal_target")
def heal_target(ctx: EffectContext, amount: int) -> GameState:
    target = ctx.target_ref or _most_damaged(ctx.state, ctx.acting_player)
    if target is None:
        return ctx.state
    return _heal_slot(ctx.state, target, amount)


@register_effect("heal_grass_target")
def heal_grass_target(ctx: EffectContext, amount: int) -> GameState:
    target = ctx.target_ref or _most_damaged(
        ctx.state, ctx.acting_player, element_filter=Element.GRASS
    )
    if target is None:
        return ctx.state
    return _heal_slot(ctx.state, target, amount)


@register_effect("heal_all_own")
def heal_all_own(ctx: EffectContext, amount: int) -> GameState:
    """Heal `amount` HP from every Pokemon belonging to the acting player."""
    state = ctx.state
    player_index = ctx.acting_player
    state = _heal_slot(state, SlotRef.active(player_index), amount)
    for i in range(len(state.players[player_index].bench)):
        state = _heal_slot(state, SlotRef.bench(player_index, i), amount)
    return state
