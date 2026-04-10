"""High-level helper for parsing and dispatching card effect text."""
from __future__ import annotations

from typing import Optional

from ptcgp.effects.parser import parse_effect_text
from ptcgp.effects.registry import EffectContext, resolve_effect
from ptcgp.engine.actions import SlotRef
from ptcgp.engine.state import GameState


def apply_effects(
    state: GameState,
    effect_text: str,
    acting_player: int,
    source_ref: Optional[SlotRef] = None,
    target_ref: Optional[SlotRef] = None,
    extra: Optional[dict] = None,
) -> GameState:
    """Parse ``effect_text`` and dispatch each resulting effect token.

    Unknown effects log a warning via ``resolve_effect`` and leave state unchanged.
    """
    if not effect_text:
        return state

    for effect in parse_effect_text(effect_text):
        ctx = EffectContext(
            state=state,
            acting_player=acting_player,
            source_ref=source_ref,
            target_ref=target_ref,
            extra=dict(extra) if extra else {},
        )
        state = resolve_effect(ctx, effect)
    return state
