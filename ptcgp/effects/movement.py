"""Movement effect handlers — switch, return-to-hand, shuffle-to-deck."""
from __future__ import annotations

from ptcgp.cards.database import get_card
from ptcgp.cards.types import Element, Stage
from ptcgp.effects.registry import EffectContext, register_effect
from ptcgp.engine.actions import SlotRef
from ptcgp.engine.state import GameState


def _swap_active_with_bench(state: GameState, player_index: int, bench_slot: int) -> GameState:
    state = state.copy()
    p = state.players[player_index]
    old_active = p.active
    p.active = p.bench[bench_slot]
    p.bench[bench_slot] = old_active
    return state


@register_effect("switch_opponent_active")
def switch_opponent_active(ctx: EffectContext) -> GameState:
    """Force the opponent to switch their Active with a random bench Pokemon."""
    state = ctx.state
    opp_idx = 1 - ctx.acting_player
    bench_indices = [i for i, s in enumerate(state.players[opp_idx].bench) if s is not None]
    if not bench_indices:
        return state
    return _swap_active_with_bench(state, opp_idx, state.rng.choice(bench_indices))


@register_effect("switch_self_to_bench")
def switch_self_to_bench(ctx: EffectContext) -> GameState:
    """Swap the attacker with one of its own benched Pokemon.

    ``target_ref`` (if on a bench) is respected; otherwise random.
    """
    state = ctx.state
    pi = ctx.acting_player
    bench_indices = [i for i, s in enumerate(state.players[pi].bench) if s is not None]
    if not bench_indices:
        return state
    if ctx.target_ref is not None and ctx.target_ref.is_bench() and ctx.target_ref.player == pi:
        slot = ctx.target_ref.slot
    else:
        slot = state.rng.choice(bench_indices)
    return _swap_active_with_bench(state, pi, slot)


@register_effect("switch_opponent_basic_to_active")
def switch_opponent_basic_to_active(ctx: EffectContext) -> GameState:
    """Force one of the opponent's benched Basic Pokemon into their Active Spot."""
    state = ctx.state
    opp_idx = 1 - ctx.acting_player
    opponent = state.players[opp_idx]
    basic_bench: list[int] = []
    for i, s in enumerate(opponent.bench):
        if s is None:
            continue
        try:
            c = get_card(s.card_id)
        except KeyError:
            continue
        if c.stage == Stage.BASIC:
            basic_bench.append(i)
    if not basic_bench:
        return state
    return _swap_active_with_bench(state, opp_idx, state.rng.choice(basic_bench))


@register_effect("return_active_to_hand_named")
def return_active_to_hand_named(ctx: EffectContext, names: tuple = ()) -> GameState:
    """Koga: return your Muk or Weezing in the Active Spot to your hand."""
    state = ctx.state
    pi = ctx.acting_player
    p = state.players[pi]
    if p.active is None:
        return state
    try:
        card = get_card(p.active.card_id)
    except KeyError:
        return state
    name_set = {n.lower() for n in names}
    if name_set and card.name.lower() not in name_set:
        return state

    state = state.copy()
    p = state.players[pi]
    # Return card to hand; tool (if any) goes to discard; attached energies are lost.
    p.hand.append(p.active.card_id)
    if p.active.tool_card_id:
        p.discard.append(p.active.tool_card_id)
    p.active = None
    return state


@register_effect("switch_self_to_bench_typed")
def switch_self_to_bench_typed(ctx: EffectContext, element: str = "") -> GameState:
    """Switch this Pokemon with 1 of your Benched Pokemon of a specific type."""
    state = ctx.state
    pi = ctx.acting_player
    try:
        filter_el = Element.from_str(element) if element else None
    except ValueError:
        filter_el = None
    bench_indices: list[int] = []
    for i, s in enumerate(state.players[pi].bench):
        if s is None:
            continue
        if filter_el is not None:
            try:
                c = get_card(s.card_id)
                if c.element != filter_el:
                    continue
            except KeyError:
                continue
        bench_indices.append(i)
    if not bench_indices:
        return state
    slot = state.rng.choice(bench_indices)
    return _swap_active_with_bench(state, pi, slot)


@register_effect("ability_bench_to_active")
def ability_bench_to_active(ctx: EffectContext) -> GameState:
    """If this Pokemon is on your Bench, switch it with your Active."""
    state = ctx.state
    pi = ctx.acting_player
    player = state.players[pi]
    if ctx.source_ref is None or not ctx.source_ref.is_bench():
        return state
    bench_slot = ctx.source_ref.slot
    if player.bench[bench_slot] is None:
        return state
    return _swap_active_with_bench(state, pi, bench_slot)


@register_effect("switch_ultra_beast")
def switch_ultra_beast(ctx: EffectContext) -> GameState:
    """Switch your Active Ultra Beast with 1 of your Benched Ultra Beasts.

    For now, just swap with a random bench Pokemon (Ultra Beast check
    is complex and would need card tagging).
    """
    state = ctx.state
    pi = ctx.acting_player
    bench_indices = [i for i, s in enumerate(state.players[pi].bench) if s is not None]
    if not bench_indices:
        return state
    slot = state.rng.choice(bench_indices)
    return _swap_active_with_bench(state, pi, slot)


@register_effect("coin_flip_bounce_opponent")
def coin_flip_bounce_opponent(ctx: EffectContext) -> GameState:
    """Flip a coin. If heads, put opponent's Active back into their hand."""
    state = ctx.state
    if state.rng.random() >= 0.5:
        return state
    opp_idx = 1 - ctx.acting_player
    p = state.players[opp_idx]
    if p.active is None:
        return state
    state = state.copy()
    p = state.players[opp_idx]
    p.hand.append(p.active.card_id)
    if p.active.tool_card_id:
        p.discard.append(p.active.tool_card_id)
    p.active = None
    return state


@register_effect("shuffle_opponent_active_into_deck")
def shuffle_opponent_active_into_deck(ctx: EffectContext) -> GameState:
    """Coin flip: on heads, shuffle the opponent's Active back into their deck."""
    state = ctx.state
    if state.rng.random() >= 0.5:
        return state
    opp_idx = 1 - ctx.acting_player
    p = state.players[opp_idx]
    if p.active is None:
        return state

    state = state.copy()
    p = state.players[opp_idx]
    p.deck.append(p.active.card_id)
    if p.active.tool_card_id:
        p.discard.append(p.active.tool_card_id)
    p.active = None
    state.rng.shuffle(p.deck)
    return state
