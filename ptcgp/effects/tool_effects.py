"""Tool effect handlers — hp_bonus."""
from __future__ import annotations

from ptcgp.effects.registry import register_effect, EffectContext
from ptcgp.engine.state import GameState
from ptcgp.engine.slot_utils import get_slot, set_slot


@register_effect("hp_bonus")
def hp_bonus(ctx: EffectContext, amount: int) -> GameState:
    """Increase the target Pokemon's max_hp and current_hp by `amount` (Giant Cape).

    Called when the tool is attached. The tool remains attached until the
    Pokemon is knocked out, at which point the entire slot (including tool) is discarded.
    The HP gain also heals the Pokemon by `amount` to match PTCGP behaviour.
    """
    state = ctx.state
    if ctx.target_ref is None:
        return state
    slot = get_slot(state, ctx.target_ref)
    if slot is None:
        return state

    new_slot = slot.copy()
    new_slot.max_hp += amount
    new_slot.current_hp += amount  # also heal the HP gain
    return set_slot(state, ctx.target_ref, new_slot)
