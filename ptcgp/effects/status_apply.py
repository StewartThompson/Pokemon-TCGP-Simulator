"""Handlers that inflict status effects on a target Pokemon."""
from __future__ import annotations

from ptcgp.effects.registry import EffectContext, register_effect
from ptcgp.engine.actions import SlotRef
from ptcgp.engine.slot_utils import mutate_slot
from ptcgp.engine.state import GameState, StatusEffect


def _opponent_active(ctx: EffectContext) -> SlotRef:
    return SlotRef.active(1 - ctx.acting_player)


def _apply_status(state: GameState, target: SlotRef, effect: StatusEffect) -> GameState:
    return mutate_slot(state, target, lambda s: s.status_effects.add(effect))


@register_effect("apply_poison")
def apply_poison(ctx: EffectContext) -> GameState:
    return _apply_status(ctx.state, _opponent_active(ctx), StatusEffect.POISONED)


@register_effect("apply_sleep")
def apply_sleep(ctx: EffectContext) -> GameState:
    return _apply_status(ctx.state, _opponent_active(ctx), StatusEffect.ASLEEP)


@register_effect("apply_paralysis")
def apply_paralysis(ctx: EffectContext) -> GameState:
    return _apply_status(ctx.state, _opponent_active(ctx), StatusEffect.PARALYZED)


@register_effect("apply_burn")
def apply_burn(ctx: EffectContext) -> GameState:
    return _apply_status(ctx.state, _opponent_active(ctx), StatusEffect.BURNED)


@register_effect("apply_confusion")
def apply_confusion(ctx: EffectContext) -> GameState:
    return _apply_status(ctx.state, _opponent_active(ctx), StatusEffect.CONFUSED)


@register_effect("coin_flip_apply_paralysis")
def coin_flip_apply_paralysis(ctx: EffectContext) -> GameState:
    """Flip a coin; on heads, paralyze the opponent's active."""
    if ctx.state.rng.random() < 0.5:
        return _apply_status(ctx.state, _opponent_active(ctx), StatusEffect.PARALYZED)
    return ctx.state


@register_effect("coin_flip_apply_sleep")
def coin_flip_apply_sleep(ctx: EffectContext) -> GameState:
    if ctx.state.rng.random() < 0.5:
        return _apply_status(ctx.state, _opponent_active(ctx), StatusEffect.ASLEEP)
    return ctx.state


@register_effect("self_confuse")
def self_confuse(ctx: EffectContext) -> GameState:
    """This Pokemon is now Confused."""
    if ctx.source_ref is None:
        return ctx.state
    return _apply_status(ctx.state, ctx.source_ref, StatusEffect.CONFUSED)


@register_effect("self_sleep")
def self_sleep(ctx: EffectContext) -> GameState:
    """This Pokemon is now Asleep."""
    if ctx.source_ref is None:
        return ctx.state
    return _apply_status(ctx.state, ctx.source_ref, StatusEffect.ASLEEP)


@register_effect("apply_random_status")
def apply_random_status(ctx: EffectContext) -> GameState:
    """Apply a random Special Condition to opponent's Active."""
    conditions = list(StatusEffect)
    chosen = ctx.state.rng.choice(conditions)
    return _apply_status(ctx.state, _opponent_active(ctx), chosen)


@register_effect("toxic_poison")
def toxic_poison(ctx: EffectContext) -> GameState:
    """Opponent's Active takes +10 from Poison. For now, just apply Poison."""
    return _apply_status(ctx.state, _opponent_active(ctx), StatusEffect.POISONED)
