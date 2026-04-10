"""Damage-dealing side effects: self-damage, bench damage, splash, random hits."""
from __future__ import annotations

from ptcgp.effects.registry import EffectContext, register_effect
from ptcgp.engine.actions import SlotRef
from ptcgp.engine.slot_utils import mutate_slot
from ptcgp.engine.state import GameState


def _damage_slot(state: GameState, target: SlotRef, amount: int) -> GameState:
    """Deal ``amount`` damage to the slot at ``target`` without triggering KO."""
    def _apply(slot):
        slot.current_hp = max(0, slot.current_hp - amount)
    return mutate_slot(state, target, _apply)


@register_effect("self_damage")
def self_damage(ctx: EffectContext, amount: int) -> GameState:
    if ctx.source_ref is None:
        return ctx.state
    return _damage_slot(ctx.state, ctx.source_ref, amount)


@register_effect("self_damage_on_coin_flip_result")
def self_damage_on_coin_flip_result(ctx: EffectContext) -> GameState:
    """Apply self-damage that was scheduled by a prior coin-flip damage modifier.

    Triggered when the paired modifier wrote ``self_damage_on_tails`` into the
    effect context's ``extra`` dict. No-op otherwise.
    """
    amount = ctx.extra.get("self_damage_on_tails", 0)
    if not amount or ctx.source_ref is None:
        return ctx.state
    return _damage_slot(ctx.state, ctx.source_ref, amount)


@register_effect("splash_bench_opponent")
def splash_bench_opponent(ctx: EffectContext, amount: int) -> GameState:
    """Deal ``amount`` damage to each of the opponent's benched Pokemon."""
    state = ctx.state
    opp_idx = 1 - ctx.acting_player
    for i, slot in enumerate(state.players[opp_idx].bench):
        if slot is not None:
            state = _damage_slot(state, SlotRef.bench(opp_idx, i), amount)
    return state


@register_effect("splash_bench_own")
def splash_bench_own(ctx: EffectContext, amount: int) -> GameState:
    """Deal ``amount`` damage to one of your own benched Pokemon (random pick)."""
    state = ctx.state
    pi = ctx.acting_player
    bench_indices = [i for i, s in enumerate(state.players[pi].bench) if s is not None]
    if not bench_indices:
        return state
    idx = state.rng.choice(bench_indices)
    return _damage_slot(state, SlotRef.bench(pi, idx), amount)


@register_effect("bench_hit_opponent")
def bench_hit_opponent(ctx: EffectContext, amount: int) -> GameState:
    """Deal ``amount`` damage to one of the opponent's Pokemon (caller picks bench).

    When ctx.target_ref is a bench slot, that slot is hit. Otherwise a random
    opponent Pokemon (including Active) is chosen.
    """
    state = ctx.state
    opp_idx = 1 - ctx.acting_player
    target = ctx.target_ref
    if target is None or target.player != opp_idx:
        candidates: list[SlotRef] = []
        if state.players[opp_idx].active is not None:
            candidates.append(SlotRef.active(opp_idx))
        for i, s in enumerate(state.players[opp_idx].bench):
            if s is not None:
                candidates.append(SlotRef.bench(opp_idx, i))
        if not candidates:
            return state
        target = state.rng.choice(candidates)
    return _damage_slot(state, target, amount)


@register_effect("splash_all_opponent")
def splash_all_opponent(ctx: EffectContext, amount: int) -> GameState:
    """Deal ``amount`` damage to each of the opponent's Pokemon (Active + Bench)."""
    state = ctx.state
    opp_idx = 1 - ctx.acting_player
    opp = state.players[opp_idx]
    if opp.active is not None:
        state = _damage_slot(state, SlotRef.active(opp_idx), amount)
    for i, slot in enumerate(opp.bench):
        if slot is not None:
            state = _damage_slot(state, SlotRef.bench(opp_idx, i), amount)
    return state


@register_effect("random_hit_one")
def random_hit_one(ctx: EffectContext, amount: int) -> GameState:
    """Pick 1 random opponent Pokemon and deal ``amount`` damage."""
    state = ctx.state
    opp_idx = 1 - ctx.acting_player
    opp = state.players[opp_idx]
    candidates: list[SlotRef] = []
    if opp.active is not None:
        candidates.append(SlotRef.active(opp_idx))
    for i, s in enumerate(opp.bench):
        if s is not None:
            candidates.append(SlotRef.bench(opp_idx, i))
    if not candidates:
        return state
    target = state.rng.choice(candidates)
    return _damage_slot(state, target, amount)


@register_effect("random_multi_hit")
def random_multi_hit(ctx: EffectContext, times: int, amount: int) -> GameState:
    """Pick a random opponent Pokemon ``times`` times and deal ``amount`` each time."""
    state = ctx.state
    opp_idx = 1 - ctx.acting_player
    for _ in range(times):
        opponent = state.players[opp_idx]
        candidates: list[SlotRef] = []
        if opponent.active is not None and opponent.active.current_hp > 0:
            candidates.append(SlotRef.active(opp_idx))
        for i, s in enumerate(opponent.bench):
            if s is not None and s.current_hp > 0:
                candidates.append(SlotRef.bench(opp_idx, i))
        if not candidates:
            break
        target = state.rng.choice(candidates)
        state = _damage_slot(state, target, amount)
    return state
