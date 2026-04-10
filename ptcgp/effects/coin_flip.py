"""Coin flip effect handlers — cant_attack_next_turn."""
from __future__ import annotations

from ptcgp.effects.registry import register_effect, EffectContext
from ptcgp.engine.state import GameState


@register_effect("cant_attack_next_turn")
def cant_attack_next_turn(ctx: EffectContext) -> GameState:
    """Flip a coin. If heads, the Defending Pokemon can't attack next turn.

    Used by Vulpix Tail Whip: Flip a coin. If heads, the Defending Pokemon
    can't attack during your opponent's next turn.

    The coin flip is handled here. On tails, do nothing.
    On heads, set cant_attack_next_turn = True on the opponent's active Pokemon.
    """
    state = ctx.state.copy()

    # Flip coin
    heads = state.rng.random() < 0.5
    if not heads:
        return state

    opponent_idx = 1 - ctx.acting_player
    opponent = state.players[opponent_idx]
    if opponent.active is not None:
        new_active = opponent.active.copy()
        new_active.cant_attack_next_turn = True
        state.players[opponent_idx].active = new_active

    return state
