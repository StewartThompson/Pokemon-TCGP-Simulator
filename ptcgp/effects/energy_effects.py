"""Energy effect handlers — attach_energy_zone_self, attach_energy_zone_bench, discard_energy_self."""
from __future__ import annotations

from typing import Optional

from ptcgp.cards.database import get_card
from ptcgp.cards.types import Element
from ptcgp.effects.registry import EffectContext, register_effect
from ptcgp.engine.actions import SlotRef
from ptcgp.engine.slot_utils import get_slot, mutate_slot
from ptcgp.engine.state import GameState


def _add_energy(slot, element: Element, count: int) -> None:
    slot.attached_energy[element] = slot.attached_energy.get(element, 0) + count


def _remove_one_energy(slot, element: Element) -> None:
    remaining = slot.attached_energy.get(element, 0)
    if remaining <= 1:
        slot.attached_energy.pop(element, None)
    else:
        slot.attached_energy[element] = remaining - 1


def _find_bench_target(
    state: GameState,
    player_index: int,
    element_filter: Optional[Element],
) -> Optional[SlotRef]:
    player = state.players[player_index]
    for i, slot in enumerate(player.bench):
        if slot is None:
            continue
        if element_filter is None:
            return SlotRef.bench(player_index, i)
        card = get_card(slot.card_id)
        if card.element == element_filter:
            return SlotRef.bench(player_index, i)
    return None


@register_effect("attach_energy_zone_self")
def attach_energy_zone_self(ctx: EffectContext, count: int, energy_type: str) -> GameState:
    """Take `count` energy of `energy_type` and attach it to the source Pokemon."""
    if ctx.source_ref is None:
        return ctx.state
    element = Element.from_str(energy_type)
    return mutate_slot(ctx.state, ctx.source_ref, lambda s: _add_energy(s, element, count))


@register_effect("attach_energy_zone_bench")
def attach_energy_zone_bench(
    ctx: EffectContext, energy_type: str, target_type: str
) -> GameState:
    """Attach one `energy_type` Energy to a benched Pokemon of ``target_type``."""
    target = ctx.target_ref
    if target is None or not target.is_bench():
        try:
            filter_element = Element.from_str(target_type)
        except ValueError:
            filter_element = None
        target = _find_bench_target(ctx.state, ctx.acting_player, filter_element)
    if target is None:
        return ctx.state
    element = Element.from_str(energy_type)
    return mutate_slot(ctx.state, target, lambda s: _add_energy(s, element, 1))


@register_effect("discard_energy_self")
def discard_energy_self(ctx: EffectContext, energy_type: str) -> GameState:
    """Discard one ``energy_type`` Energy from the source Pokemon, if any."""
    if ctx.source_ref is None:
        return ctx.state
    slot = get_slot(ctx.state, ctx.source_ref)
    if slot is None or slot.attached_energy.get(Element.from_str(energy_type), 0) == 0:
        return ctx.state
    element = Element.from_str(energy_type)
    return mutate_slot(ctx.state, ctx.source_ref, lambda s: _remove_one_energy(s, element))


@register_effect("discard_n_energy_self")
def discard_n_energy_self(ctx: EffectContext, count: int, energy_type: str) -> GameState:
    """Discard ``count`` energy of ``energy_type`` from the source Pokemon."""
    if ctx.source_ref is None:
        return ctx.state
    element = Element.from_str(energy_type)
    state = ctx.state
    for _ in range(count):
        slot = get_slot(state, ctx.source_ref)
        if slot is None or slot.attached_energy.get(element, 0) == 0:
            break
        state = mutate_slot(state, ctx.source_ref, lambda s: _remove_one_energy(s, element))
    return state


@register_effect("discard_all_energy_self")
def discard_all_energy_self(ctx: EffectContext) -> GameState:
    """Discard all energy from the source Pokemon."""
    if ctx.source_ref is None:
        return ctx.state
    return mutate_slot(ctx.state, ctx.source_ref, lambda s: s.attached_energy.clear())


@register_effect("discard_random_energy_opponent")
def discard_random_energy_opponent(ctx: EffectContext) -> GameState:
    """Discard one random energy from the opponent's Active Pokemon."""
    state = ctx.state
    opp_idx = 1 - ctx.acting_player
    opp_active = state.players[opp_idx].active
    if opp_active is None or not opp_active.attached_energy:
        return state
    # Build a flat list then sample one
    flat: list[Element] = []
    for el, n in opp_active.attached_energy.items():
        flat.extend([el] * n)
    chosen = state.rng.choice(flat)

    def _remove(slot):
        _remove_one_energy(slot, chosen)

    return mutate_slot(state, SlotRef.active(opp_idx), _remove)


@register_effect("coin_flip_discard_random_energy_opponent")
def coin_flip_discard_random_energy_opponent(ctx: EffectContext) -> GameState:
    if ctx.state.rng.random() >= 0.5:
        return ctx.state
    return discard_random_energy_opponent(ctx)


@register_effect("move_all_electric_to_active_named")
def move_all_electric_to_active_named(ctx: EffectContext, names: tuple = ()) -> GameState:
    """Move all Lightning energy from own Bench to Active, if Active matches names."""
    from ptcgp.cards.database import get_card as _get_card
    state = ctx.state
    pi = ctx.acting_player
    active = state.players[pi].active
    if active is None:
        return state
    try:
        active_card = _get_card(active.card_id)
    except KeyError:
        return state
    if names and active_card.name.lower() not in {n.lower() for n in names}:
        return state

    state = state.copy()
    p = state.players[pi]
    moved = 0
    for i, bslot in enumerate(p.bench):
        if bslot is None:
            continue
        n = bslot.attached_energy.get(Element.LIGHTNING, 0)
        if n <= 0:
            continue
        moved += n
        new_bench = bslot.copy()
        new_bench.attached_energy.pop(Element.LIGHTNING, None)
        p.bench[i] = new_bench
    if moved == 0:
        return state
    new_active = p.active.copy()
    new_active.attached_energy[Element.LIGHTNING] = (
        new_active.attached_energy.get(Element.LIGHTNING, 0) + moved
    )
    p.active = new_active
    return state


@register_effect("attach_energy_zone_named")
def attach_energy_zone_named(
    ctx: EffectContext, energy_type: str, names: tuple = ()
) -> GameState:
    """Attach one ``energy_type`` Energy to the caller's Pokemon matching one of ``names``.

    Used by Brock: "Take a Fighting Energy from your Energy Zone and attach it
    to Golem or Onix." The chosen target is any of your own Pokemon whose name
    matches. Prefers the Active slot if eligible; otherwise the first bench slot.
    """
    from ptcgp.cards.database import get_card as _get_card
    state = ctx.state
    pi = ctx.acting_player
    player = state.players[pi]
    element = Element.from_str(energy_type)
    name_set = {n.lower() for n in names}

    def _matches(slot) -> bool:
        try:
            return _get_card(slot.card_id).name.lower() in name_set
        except KeyError:
            return False

    target: SlotRef | None = None
    if player.active is not None and _matches(player.active):
        target = SlotRef.active(pi)
    else:
        for i, bslot in enumerate(player.bench):
            if bslot is not None and _matches(bslot):
                target = SlotRef.bench(pi, i)
                break
    if target is None:
        return state
    return mutate_slot(state, target, lambda s: _add_energy(s, element, 1))


@register_effect("coin_flip_until_tails_attach_energy")
def coin_flip_until_tails_attach_energy(
    ctx: EffectContext, energy_type: str, element_filter: str = ""
) -> GameState:
    """Misty: flip coins until tails, attach that many Water energy to target."""
    state = ctx.state
    heads = 0
    while state.rng.random() < 0.5:
        heads += 1
    if heads == 0 or ctx.target_ref is None:
        return state
    element = Element.from_str(energy_type)
    return mutate_slot(state, ctx.target_ref, lambda s: _add_energy(s, element, heads))


@register_effect("move_bench_energy_to_active")
def move_bench_energy_to_active(ctx: EffectContext) -> GameState:
    """Dawn: move one energy from a specified benched Pokemon to your Active.

    ``ctx.target_ref`` selects which benched Pokemon donates the energy. If
    no target is provided, the handler picks the first benched Pokemon that
    has any energy attached.
    """
    state = ctx.state
    pi = ctx.acting_player
    player = state.players[pi]
    if player.active is None:
        return state

    # Determine source slot and element to move.
    source_ref = ctx.target_ref
    if source_ref is None or not source_ref.is_bench() or source_ref.player != pi:
        for i, s in enumerate(player.bench):
            if s is not None and s.attached_energy:
                source_ref = SlotRef.bench(pi, i)
                break
    if source_ref is None:
        return state

    source = get_slot(state, source_ref)
    if source is None or not source.attached_energy:
        return state

    # Pick the first element with count > 0 (deterministic, reproducible).
    element = next(iter(source.attached_energy.keys()))

    state = mutate_slot(state, source_ref, lambda s: _remove_one_energy(s, element))
    state = mutate_slot(
        state, SlotRef.active(pi), lambda s: _add_energy(s, element, 1)
    )
    return state


@register_effect("attach_n_energy_zone_bench")
def attach_n_energy_zone_bench(ctx: EffectContext, count: int, energy_type: str) -> GameState:
    """Take N energy from Energy Zone and attach to 1 benched Pokemon."""
    element = Element.from_str(energy_type)
    target = ctx.target_ref
    if target is None or not target.is_bench():
        target = _find_bench_target(ctx.state, ctx.acting_player, None)
    if target is None:
        return ctx.state
    return mutate_slot(ctx.state, target, lambda s: _add_energy(s, element, count))


@register_effect("attach_energy_zone_bench_bracket")
def attach_energy_zone_bench_bracket(ctx: EffectContext, energy_type: str, target_type: str) -> GameState:
    """Bracket notation attach: [L] energy to benched [L] Pokemon."""
    _TYPE_MAP = {"L": "Lightning", "W": "Water", "G": "Grass", "F": "Fire",
                 "P": "Psychic", "R": "Fighting", "D": "Darkness", "M": "Metal"}
    etype = _TYPE_MAP.get(energy_type, energy_type)
    ttype = _TYPE_MAP.get(target_type, target_type)
    try:
        element = Element.from_str(etype)
        filter_el = Element.from_str(ttype)
    except ValueError:
        return ctx.state
    target = _find_bench_target(ctx.state, ctx.acting_player, filter_el)
    if target is None:
        return ctx.state
    return mutate_slot(ctx.state, target, lambda s: _add_energy(s, element, 1))


@register_effect("attach_energy_zone_self_bracket")
def attach_energy_zone_self_bracket(ctx: EffectContext, energy_type: str) -> GameState:
    """Bracket notation: [L] energy to self."""
    _TYPE_MAP = {"L": "Lightning", "W": "Water", "G": "Grass", "F": "Fire",
                 "P": "Psychic", "R": "Fighting", "D": "Darkness", "M": "Metal"}
    etype = _TYPE_MAP.get(energy_type, energy_type)
    if ctx.source_ref is None:
        return ctx.state
    try:
        element = Element.from_str(etype)
    except ValueError:
        return ctx.state
    return mutate_slot(ctx.state, ctx.source_ref, lambda s: _add_energy(s, element, 1))


@register_effect("attach_energy_zone_bench_any_bracket")
def attach_energy_zone_bench_any_bracket(ctx: EffectContext, energy_type: str) -> GameState:
    """Bracket notation: [L] energy to any benched Pokemon."""
    _TYPE_MAP = {"L": "Lightning", "W": "Water", "G": "Grass", "F": "Fire",
                 "P": "Psychic", "R": "Fighting", "D": "Darkness", "M": "Metal"}
    etype = _TYPE_MAP.get(energy_type, energy_type)
    try:
        element = Element.from_str(etype)
    except ValueError:
        return ctx.state
    target = ctx.target_ref
    if target is None or not target.is_bench():
        target = _find_bench_target(ctx.state, ctx.acting_player, None)
    if target is None:
        return ctx.state
    return mutate_slot(ctx.state, target, lambda s: _add_energy(s, element, 1))


@register_effect("attach_colorless_energy_zone_bench")
def attach_colorless_energy_zone_bench(ctx: EffectContext) -> GameState:
    """Colorless Energy doesn't exist in the Energy Zone — no-op."""
    return ctx.state


@register_effect("first_turn_energy_attach")
def first_turn_energy_attach(ctx: EffectContext, energy_type: str = "L") -> GameState:
    """At end of first turn, attach energy to self. Handled structurally; no-op."""
    # PASSIVE: handled structurally
    return ctx.state


@register_effect("attach_water_two_bench")
def attach_water_two_bench(ctx: EffectContext) -> GameState:
    """Choose 2 benched Pokemon, attach a Water Energy from zone to each."""
    state = ctx.state
    pi = ctx.acting_player
    player = state.players[pi]
    eligible = [i for i, s in enumerate(player.bench) if s is not None]
    if not eligible:
        return state
    chosen = state.rng.sample(eligible, min(2, len(eligible)))
    for idx in chosen:
        state = mutate_slot(
            state, SlotRef.bench(pi, idx), lambda s: _add_energy(s, Element.WATER, 1)
        )
    return state


@register_effect("attach_energy_zone_to_grass")
def attach_energy_zone_to_grass(ctx: EffectContext) -> GameState:
    """Take a Grass Energy from zone and attach to 1 of your Grass Pokemon."""
    from ptcgp.cards.database import get_card as _get_card
    state = ctx.state
    pi = ctx.acting_player
    player = state.players[pi]
    target: Optional[SlotRef] = None
    # Check active first
    if player.active is not None:
        try:
            if _get_card(player.active.card_id).element == Element.GRASS:
                target = SlotRef.active(pi)
        except KeyError:
            pass
    if target is None:
        for i, s in enumerate(player.bench):
            if s is None:
                continue
            try:
                if _get_card(s.card_id).element == Element.GRASS:
                    target = SlotRef.bench(pi, i)
                    break
            except KeyError:
                pass
    if target is None:
        return state
    return mutate_slot(state, target, lambda s: _add_energy(s, Element.GRASS, 1))


@register_effect("ability_attach_energy_end_turn")
def ability_attach_energy_end_turn(ctx: EffectContext) -> GameState:
    """Take Psychic Energy from zone, attach to self. Turn ends after."""
    if ctx.source_ref is None:
        return ctx.state
    return mutate_slot(ctx.state, ctx.source_ref, lambda s: _add_energy(s, Element.PSYCHIC, 1))


@register_effect("discard_all_typed_energy_self")
def discard_all_typed_energy_self(ctx: EffectContext, energy_type: str) -> GameState:
    """Discard all energy of a specific type from this Pokemon."""
    if ctx.source_ref is None:
        return ctx.state
    try:
        element = Element.from_str(energy_type)
    except ValueError:
        return ctx.state
    return mutate_slot(ctx.state, ctx.source_ref, lambda s: s.attached_energy.pop(element, None))


@register_effect("discard_random_energy_both_active")
def discard_random_energy_both_active(ctx: EffectContext) -> GameState:
    """Discard a random energy from both Active Pokemon."""
    state = ctx.state
    for pi in range(2):
        active = state.players[pi].active
        if active is None or not active.attached_energy:
            continue
        flat: list[Element] = []
        for el, n in active.attached_energy.items():
            flat.extend([el] * n)
        if not flat:
            continue
        chosen = state.rng.choice(flat)
        state = mutate_slot(state, SlotRef.active(pi), lambda s: _remove_one_energy(s, chosen))
    return state


@register_effect("discard_random_energy_all_pokemon")
def discard_random_energy_all_pokemon(ctx: EffectContext) -> GameState:
    """Discard a random energy from among all Pokemon in play."""
    state = ctx.state
    # Build list of (player_idx, slot_ref, element) for all attached energy
    candidates: list[tuple[SlotRef, Element]] = []
    for pi in range(2):
        p = state.players[pi]
        if p.active is not None:
            for el, n in p.active.attached_energy.items():
                for _ in range(n):
                    candidates.append((SlotRef.active(pi), el))
        for i, s in enumerate(p.bench):
            if s is None:
                continue
            for el, n in s.attached_energy.items():
                for _ in range(n):
                    candidates.append((SlotRef.bench(pi, i), el))
    if not candidates:
        return state
    ref, el = state.rng.choice(candidates)
    return mutate_slot(state, ref, lambda s: _remove_one_energy(s, el))


@register_effect("discard_top_deck")
def discard_top_deck(ctx: EffectContext, count: int) -> GameState:
    """Discard the top N cards of your deck."""
    state = state_copy = ctx.state.copy()
    p = state_copy.players[ctx.acting_player]
    to_discard = min(count, len(p.deck))
    discarded = p.deck[:to_discard]
    p.deck = p.deck[to_discard:]
    p.discard.extend(discarded)
    return state_copy


@register_effect("move_all_typed_energy_bench_to_active")
def move_all_typed_energy_bench_to_active(
    ctx: EffectContext, energy_type: str, element_filter: str = ""
) -> GameState:
    """Move all energy of a type from 1 benched Pokemon (of matching type) to Active."""
    from ptcgp.cards.database import get_card as _get_card
    state = ctx.state
    pi = ctx.acting_player
    player = state.players[pi]
    if player.active is None:
        return state
    try:
        energy_el = Element.from_str(energy_type)
    except ValueError:
        return state

    # Find a benched Pokemon with matching element that has that energy
    source_idx = None
    for i, s in enumerate(player.bench):
        if s is None:
            continue
        if element_filter:
            try:
                if _get_card(s.card_id).element != Element.from_str(element_filter):
                    continue
            except (KeyError, ValueError):
                continue
        if s.attached_energy.get(energy_el, 0) > 0:
            source_idx = i
            break
    if source_idx is None:
        return state

    bench_slot = player.bench[source_idx]
    amount = bench_slot.attached_energy.get(energy_el, 0)
    if amount == 0:
        return state

    state = mutate_slot(state, SlotRef.bench(pi, source_idx),
                        lambda s: s.attached_energy.pop(energy_el, None))
    state = mutate_slot(state, SlotRef.active(pi),
                        lambda s: _add_energy(s, energy_el, amount))
    return state


@register_effect("move_water_bench_to_active")
def move_water_bench_to_active(ctx: EffectContext) -> GameState:
    """Move a Water Energy from a Benched Water Pokemon to Active Water Pokemon."""
    from ptcgp.cards.database import get_card as _get_card
    state = ctx.state
    pi = ctx.acting_player
    player = state.players[pi]
    if player.active is None:
        return state

    # Find first benched Water Pokemon with Water energy
    source_idx = None
    for i, s in enumerate(player.bench):
        if s is None:
            continue
        try:
            if _get_card(s.card_id).element != Element.WATER:
                continue
        except KeyError:
            continue
        if s.attached_energy.get(Element.WATER, 0) > 0:
            source_idx = i
            break
    if source_idx is None:
        return state

    state = mutate_slot(state, SlotRef.bench(pi, source_idx),
                        lambda s: _remove_one_energy(s, Element.WATER))
    state = mutate_slot(state, SlotRef.active(pi),
                        lambda s: _add_energy(s, Element.WATER, 1))
    return state


@register_effect("multi_coin_attach_bench")
def multi_coin_attach_bench(
    ctx: EffectContext, count: int, energy_type: str, element_filter: str = ""
) -> GameState:
    """Moltres EX-style: flip N coins, attach #heads energy among your benched Fire.

    For simplicity the energies are distributed round-robin across benched
    Pokemon matching ``element_filter``.
    """
    from ptcgp.cards.database import get_card as _get_card
    state = ctx.state
    pi = ctx.acting_player
    player = state.players[pi]
    element = Element.from_str(energy_type)
    try:
        filter_el = Element.from_str(element_filter) if element_filter else None
    except ValueError:
        filter_el = None

    # Find eligible bench slots
    eligible: list[int] = []
    for i, s in enumerate(player.bench):
        if s is None:
            continue
        if filter_el is not None:
            try:
                if _get_card(s.card_id).element != filter_el:
                    continue
            except KeyError:
                continue
        eligible.append(i)
    if not eligible:
        return state

    heads = sum(1 for _ in range(count) if state.rng.random() < 0.5)
    if heads == 0:
        return state

    # Distribute round-robin
    for k in range(heads):
        idx = eligible[k % len(eligible)]
        state = mutate_slot(
            state, SlotRef.bench(pi, idx), lambda s: _add_energy(s, element, 1)
        )
    return state
