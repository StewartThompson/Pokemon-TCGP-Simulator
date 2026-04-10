"""Helpers that determine which effects need an explicit target.

When a card's effect text names "1 of your Pokémon" (or a constrained variant
like "1 of your Grass Pokémon"), the player is supposed to pick which Pokemon
to affect. ``get_play_targets`` returns the list of legal target slots so the
legal-action generator can emit one ``PLAY_CARD`` action per valid choice.
"""
from __future__ import annotations

from typing import Callable, Optional

from ptcgp.cards.card import Card
from ptcgp.cards.database import get_card
from ptcgp.cards.types import Element
from ptcgp.effects.parser import parse_effect_text
from ptcgp.engine.actions import SlotRef
from ptcgp.engine.state import PlayerState, PokemonSlot


def _is_damaged(slot: PokemonSlot) -> bool:
    return slot.current_hp < slot.max_hp


def _has_any_energy(slot: PokemonSlot) -> bool:
    return bool(slot.attached_energy)


def _is_damaged_grass(slot: PokemonSlot) -> bool:
    if slot.current_hp >= slot.max_hp:
        return False
    try:
        return get_card(slot.card_id).element == Element.GRASS
    except KeyError:
        return False


def _is_grass(slot: PokemonSlot) -> bool:
    try:
        return get_card(slot.card_id).element == Element.GRASS
    except KeyError:
        return False


# Effects whose target is "one of your Pokémon (filter)". The dict value is a
# predicate on the candidate PokemonSlot. Heal effects only target damaged
# Pokemon — no point offering Potion on a full-HP Pokemon.
_OWN_POKEMON_TARGETS: dict[str, Callable[[PokemonSlot], bool]] = {
    "heal_target": _is_damaged,
    "heal_grass_target": _is_damaged_grass,
}

# Bench-only variants (e.g. Lilligant Leaf Supply — attach to a benched Grass,
# Dawn — move an Energy from a benched Pokemon that has any).
_OWN_BENCH_TARGETS: dict[str, Callable[[PokemonSlot], bool]] = {
    "attach_energy_zone_bench": _is_grass,
    "move_bench_energy_to_active": _has_any_energy,
}


def _collect_own_targets(
    player_index: int,
    player: PlayerState,
    predicate: Callable[[PokemonSlot], bool],
    bench_only: bool = False,
) -> list[SlotRef]:
    refs: list[SlotRef] = []
    if not bench_only and player.active is not None and predicate(player.active):
        refs.append(SlotRef.active(player_index))
    for i, slot in enumerate(player.bench):
        if slot is not None and predicate(slot):
            refs.append(SlotRef.bench(player_index, i))
    return refs


def get_play_targets(
    card: Card, player_index: int, player: PlayerState
) -> list[Optional[SlotRef]]:
    """Return the list of legal target slots for playing ``card`` as item/supporter.

    Returns ``[None]`` when the card does not require a target (callers should
    emit a single untargeted ``PLAY_CARD`` action). Returns an empty list when
    the card needs a target but no legal target exists (caller should suppress
    the action entirely).
    """
    return _get_targets_for_effect_text(card.trainer_effect_text, player_index, player)


def get_attack_sub_targets(
    attack_effect_text: str, player_index: int, player: PlayerState
) -> list[Optional[SlotRef]]:
    """Return legal sub-targets for an attack's side-effect.

    Unlike items, attacks are always legal even when the side-effect target set
    is empty (the attack still does its damage). So an attack whose side-effect
    needs a target returns ``[None]`` when no valid target exists — the effect
    will silently no-op — rather than suppressing the attack altogether.
    """
    if not attack_effect_text:
        return [None]

    effects = parse_effect_text(attack_effect_text)
    for effect in effects:
        if effect.name in _OWN_POKEMON_TARGETS:
            refs = _collect_own_targets(
                player_index, player, _OWN_POKEMON_TARGETS[effect.name]
            )
            return list(refs) if refs else [None]
        if effect.name in _OWN_BENCH_TARGETS:
            refs = _collect_own_targets(
                player_index, player, _OWN_BENCH_TARGETS[effect.name], bench_only=True
            )
            return list(refs) if refs else [None]
    return [None]


def _get_targets_for_effect_text(
    effect_text: str, player_index: int, player: PlayerState
) -> list[Optional[SlotRef]]:
    effects = parse_effect_text(effect_text)
    if not effects:
        return [None]

    for effect in effects:
        if effect.name in _OWN_POKEMON_TARGETS:
            refs = _collect_own_targets(
                player_index, player, _OWN_POKEMON_TARGETS[effect.name]
            )
            return list(refs) if refs else []
        if effect.name in _OWN_BENCH_TARGETS:
            refs = _collect_own_targets(
                player_index, player, _OWN_BENCH_TARGETS[effect.name], bench_only=True
            )
            return list(refs) if refs else []

    return [None]
