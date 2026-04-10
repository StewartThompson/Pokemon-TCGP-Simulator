"""Effect registry — maps effect names to handler functions."""
from __future__ import annotations
import warnings
from dataclasses import dataclass, field
from typing import Callable, Optional

from ptcgp.engine.state import GameState
from ptcgp.engine.actions import SlotRef


@dataclass
class EffectContext:
    state: GameState
    acting_player: int          # index 0 or 1
    source_ref: Optional[SlotRef]  # where the effect originated (attacker/ability user)
    target_ref: Optional[SlotRef]  # explicit target (e.g., Potion target)
    amount: int = 0             # generic amount param (damage, heal, count)
    extra: dict = field(default_factory=dict)  # any other params


# Internal registry: effect_name → handler function
_REGISTRY: dict[str, Callable] = {}


def register_effect(name: str):
    """Decorator: @register_effect('heal_self')"""
    def decorator(fn: Callable) -> Callable:
        _REGISTRY[name] = fn
        return fn
    return decorator


def resolve_effect(ctx: EffectContext, effect) -> GameState:
    """Dispatch an Effect to its registered handler.

    Returns new GameState. If effect is UnknownEffect or has no handler,
    logs a warning and returns ctx.state unchanged.
    """
    from ptcgp.effects.base import UnknownEffect
    if isinstance(effect, UnknownEffect):
        warnings.warn(f"Unhandled effect: {effect.raw_text!r}", stacklevel=2)
        return ctx.state
    handler = _REGISTRY.get(effect.name)
    if handler is None:
        warnings.warn(f"No handler registered for effect: {effect.name!r}", stacklevel=2)
        return ctx.state
    return handler(ctx, **effect.params)


def is_effect_implemented(effect_name: str) -> bool:
    return effect_name in _REGISTRY


def list_registered_effects() -> list[str]:
    return list(_REGISTRY.keys())
