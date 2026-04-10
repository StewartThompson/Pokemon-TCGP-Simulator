"""Damage-modifier engine for attack effects.

This module walks parsed effect tokens and computes the final damage for an
attack before it's applied. It handles:

- coin-flip bonus damage ("If heads, this attack does 40 more damage.")
- coin-flip multi-damage ("Flip 4 coins. This attack does 50 damage for each heads.")
- "Flip a coin. If tails, this attack does nothing."
- bench count damage ("30 damage for each of your Benched Lightning Pokémon")
- energy-count damage ("30 more damage for each Energy attached to opponent's active")
- "extra energy" conditional damage (Water Pokemon with N+ extras)
- "if opponent damaged / poisoned" conditional bonus
- "If this Pokémon has damage on it, +60 more damage"
- flat damage buffs from Giovanni-style supporter auras

The result is a tuple ``(final_damage, skip_damage, scratch)`` where ``scratch``
is a dict that downstream effect handlers can read (e.g. self-damage amount,
whether the damage-dealing coin came up heads).

Every damage-modifier effect name is also registered as a (mostly) no-op in
the effect registry so that the post-damage ``apply_effects`` pass does not
emit "no handler registered" warnings for them. The sole exception is
``coin_flip_bonus_or_self_damage``, which still needs to read the scratch dict
to apply the scheduled self-damage.
"""
from __future__ import annotations

from typing import Any

from ptcgp.cards.card import Card
from ptcgp.cards.database import get_card
from ptcgp.cards.types import Element
from ptcgp.effects.parser import parse_effect_text
from ptcgp.effects.registry import EffectContext, register_effect
from ptcgp.engine.actions import SlotRef
from ptcgp.engine.slot_utils import mutate_slot
from ptcgp.engine.state import GameState, PokemonSlot, StatusEffect


def compute_damage_modifier(
    state: GameState,
    base_damage: int,
    raw_damage: int,
    attack_effect_text: str,
    attacker_slot: PokemonSlot,
    attacker_card: Card,
    defender_slot: PokemonSlot,
    defender_card: Card,
    handler_str: str = "",
    cached_effects: tuple = (),
) -> tuple[int, bool, dict[str, Any]]:
    """Return ``(final_damage, skip_damage, scratch)``.

    ``skip_damage=True`` means the attack does nothing this turn (e.g. coin
    flipped tails). ``scratch`` is merged into the effect context's ``extra``
    dict so post-damage handlers can read what happened during the modifier
    phase.
    """
    scratch: dict[str, Any] = {}
    damage = base_damage
    skip = False

    if cached_effects:
        effects = cached_effects
    elif handler_str:
        from ptcgp.effects.apply import parse_handler_string
        effects = parse_handler_string(handler_str)
    else:
        effects = parse_effect_text(attack_effect_text)
    player = state.players[state.current_player]

    # Apply flat attack damage bonus from Giovanni-style auras first.
    aura = _supporter_aura_bonus(player, attacker_card)
    if aura:
        damage += aura

    # Apply Defending Pokemon's own damage-nerf debuff (-20 from previous turn)
    if attacker_slot.attack_bonus_next_turn_self:
        damage = max(0, damage + attacker_slot.attack_bonus_next_turn_self)

    # Apply defender's damage reduction (from "takes -10/-20 from attacks").
    if defender_slot.incoming_damage_reduction:
        if damage > 0:
            damage = max(0, damage - defender_slot.incoming_damage_reduction)

    # Apply defender's passive ability damage reduction (e.g. "This Pokemon
    # takes -10/-20 damage from attacks").
    passive_reduction = _passive_damage_reduction(defender_card)
    if passive_reduction and damage > 0:
        damage = max(0, damage - passive_reduction)

    for effect in effects:
        name = effect.name
        params = effect.params

        if name == "coin_flip_bonus_damage":
            if _flip(state):
                damage += params.get("amount", 0)
                scratch["coin_heads"] = True
            else:
                scratch["coin_heads"] = False

        elif name == "coin_flip_nothing":
            if not _flip(state):
                skip = True
                damage = 0
                scratch["coin_heads"] = False
            else:
                scratch["coin_heads"] = True

        elif name == "both_coins_bonus":
            n_heads = sum(1 for _ in range(2) if _flip(state))
            scratch["heads_count"] = n_heads
            if n_heads == 2:
                damage += params.get("amount", 0)

        elif name == "multi_coin_damage":
            # "Flip N coins. This attack does D damage for each heads." —
            # This REPLACES base damage with D * heads (attacks like this
            # typically have base damage 0 in the card data).
            n = params.get("count", 1)
            per = params.get("per", 0)
            n_heads = sum(1 for _ in range(n) if _flip(state))
            scratch["heads_count"] = n_heads
            damage = base_damage + per * n_heads

        elif name == "flip_until_tails_damage":
            per = params.get("per", 0)
            n_heads = 0
            while _flip(state):
                n_heads += 1
            scratch["heads_count"] = n_heads
            damage = base_damage + per * n_heads

        elif name == "coin_flip_bonus_or_self_damage":
            heads = _flip(state)
            scratch["coin_heads"] = heads
            if heads:
                damage += params.get("bonus", 0)
            else:
                scratch["self_damage_on_tails"] = params.get("self_damage", 0)

        elif name == "bonus_per_bench":
            per = params.get("per", 0)
            count = sum(1 for s in player.bench if s is not None)
            damage += per * count

        elif name == "bonus_per_bench_element":
            per = params.get("per", 0)
            element_name = params.get("element", "")
            try:
                element = Element.from_str(element_name)
            except ValueError:
                element = None
            count = 0
            if element is not None:
                for s in player.bench:
                    if s is None:
                        continue
                    try:
                        card = get_card(s.card_id)
                    except KeyError:
                        continue
                    if card.element == element:
                        count += 1
            damage += per * count

        elif name == "bonus_per_bench_named":
            per = params.get("per", 0)
            name_filter = params.get("name", "").lower()
            count = 0
            for s in player.bench:
                if s is None:
                    continue
                try:
                    card = get_card(s.card_id)
                except KeyError:
                    continue
                if card.name.lower() == name_filter:
                    count += 1
            damage += per * count

        elif name == "bonus_per_opponent_energy":
            per = params.get("per", 0)
            count = sum(defender_slot.attached_energy.values())
            damage += per * count

        elif name == "bonus_if_extra_water_energy":
            threshold = params.get("threshold", 2)
            bonus = params.get("bonus", 0)
            # "Extra" water energy beyond the base Water cost of the attack.
            # We don't know the base cost here but can use "attached Water - 1"
            # as an approximation for "at least 2 extra" style checks.
            water_attached = attacker_slot.attached_energy.get(Element.WATER, 0)
            if water_attached >= threshold + 1:  # +1 because at least 1 is paid
                damage += bonus

        elif name == "bonus_if_opponent_damaged":
            bonus = params.get("bonus", 0)
            if defender_slot.current_hp < defender_slot.max_hp:
                damage += bonus

        elif name == "bonus_if_self_damaged":
            bonus = params.get("bonus", 0)
            if attacker_slot.current_hp < attacker_slot.max_hp:
                damage += bonus

        elif name == "bonus_if_opponent_poisoned":
            bonus = params.get("bonus", 0)
            if StatusEffect.POISONED in defender_slot.status_effects:
                damage += bonus

        elif name == "multi_coin_per_energy_damage":
            per = params.get("per", 0)
            total_energy = sum(attacker_slot.attached_energy.values())
            n_heads = sum(1 for _ in range(total_energy) if _flip(state))
            scratch["heads_count"] = n_heads
            damage = base_damage + per * n_heads

        elif name == "multi_coin_per_typed_energy_damage":
            per = params.get("per", 0)
            etype = params.get("energy_type", "")
            try:
                el = Element.from_str(etype)
            except ValueError:
                el = None
            count_energy = attacker_slot.attached_energy.get(el, 0) if el else 0
            n_heads = sum(1 for _ in range(count_energy) if _flip(state))
            scratch["heads_count"] = n_heads
            damage = base_damage + per * n_heads

        elif name == "multi_coin_per_pokemon_damage":
            per = params.get("per", 0)
            count_poke = 1 if player.active is not None else 0
            count_poke += sum(1 for s in player.bench if s is not None)
            n_heads = sum(1 for _ in range(count_poke) if _flip(state))
            scratch["heads_count"] = n_heads
            damage = base_damage + per * n_heads

        elif name == "flip_until_tails_bonus":
            per = params.get("per", 0)
            n_heads = 0
            while _flip(state):
                n_heads += 1
            scratch["heads_count"] = n_heads
            damage += per * n_heads

        elif name == "multi_coin_bonus":
            n = params.get("count", 1)
            per = params.get("per", 0)
            n_heads = sum(1 for _ in range(n) if _flip(state))
            scratch["heads_count"] = n_heads
            damage += per * n_heads

        elif name == "bonus_per_opponent_bench":
            per = params.get("per", 0)
            opp = state.players[1 - state.current_player]
            count = sum(1 for s in opp.bench if s is not None)
            damage += per * count

        elif name == "bonus_if_tool_attached":
            bonus = params.get("bonus", 0)
            if attacker_slot.tool_card_id is not None:
                damage += bonus

        elif name == "bonus_if_opponent_has_tool":
            bonus = params.get("bonus", 0)
            if defender_slot.tool_card_id is not None:
                damage += bonus

        elif name == "bonus_if_opponent_ex":
            bonus = params.get("bonus", 0)
            if "ex" in defender_card.name.lower():
                damage += bonus

        elif name == "bonus_if_opponent_basic":
            bonus = params.get("bonus", 0)
            from ptcgp.cards.types import Stage as _Stage
            if defender_card.stage == _Stage.BASIC:
                damage += bonus

        elif name == "bonus_if_opponent_element":
            bonus = params.get("bonus", 0)
            el_name = params.get("element", "")
            try:
                el = Element.from_str(el_name)
            except ValueError:
                el = None
            if el is not None and defender_card.element == el:
                damage += bonus

        elif name == "bonus_if_opponent_has_ability":
            bonus = params.get("bonus", 0)
            if defender_card.ability is not None:
                damage += bonus

        elif name == "bonus_if_bench_damaged":
            bonus = params.get("bonus", 0)
            if any(s is not None and s.current_hp < s.max_hp for s in player.bench):
                damage += bonus

        elif name == "bonus_if_ko_last_turn":
            bonus = params.get("bonus", 0)
            if getattr(player, "had_ko_last_turn", False):
                damage += bonus

        elif name == "bonus_if_played_supporter":
            bonus = params.get("bonus", 0)
            if getattr(player, "played_supporter_this_turn", False):
                damage += bonus

        elif name == "bonus_if_just_promoted":
            bonus = params.get("bonus", 0)
            if getattr(attacker_slot, "promoted_this_turn", False):
                damage += bonus

        elif name == "bonus_if_opponent_more_hp":
            bonus = params.get("bonus", 0)
            if defender_slot.current_hp > attacker_slot.current_hp:
                damage += bonus

        elif name == "bonus_if_opponent_has_status":
            bonus = params.get("bonus", 0)
            if defender_slot.status_effects:
                damage += bonus

        elif name == "bonus_equal_to_damage_taken":
            damage_taken = attacker_slot.max_hp - attacker_slot.current_hp
            damage += damage_taken

        elif name == "bonus_if_extra_energy":
            threshold = params.get("threshold", 2)
            bonus = params.get("bonus", 0)
            etype = params.get("energy_type", "Water")
            try:
                el = Element.from_str(etype)
            except ValueError:
                el = Element.WATER
            attached = attacker_slot.attached_energy.get(el, 0)
            if attached >= threshold + 1:
                damage += bonus

        elif name == "bonus_if_named_in_play":
            bonus = params.get("bonus", 0)
            names_tup = params.get("names", ())
            name_set = {n.lower() for n in names_tup}
            found = False
            for slot_check in [player.active] + list(player.bench):
                if slot_check is None:
                    continue
                try:
                    c = get_card(slot_check.card_id)
                    if c.name.lower() in name_set:
                        found = True
                        break
                except KeyError:
                    pass
            if found:
                damage += bonus

        elif name == "halve_opponent_hp":
            # This replaces normal damage with halving
            halved = defender_slot.current_hp // 2
            scratch["halve_hp"] = halved
            # We set damage to 0 and handle in post-damage
            damage = 0

        elif name == "double_heads_instant_ko":
            n_heads = sum(1 for _ in range(2) if _flip(state))
            scratch["heads_count"] = n_heads
            if n_heads == 2:
                scratch["instant_ko"] = True

    if damage < 0:
        damage = 0

    return damage, skip, scratch


def _flip(state: GameState) -> bool:
    """Return True for heads."""
    return state.rng.random() < 0.5


def _supporter_aura_bonus(player, attacker_card: Card) -> int:
    """Return the flat supporter-aura damage bonus applicable to this attack."""
    bonus = player.attack_damage_bonus
    if not bonus:
        return 0
    names = player.attack_damage_bonus_names
    if not names:
        return bonus  # applies to all attackers (Giovanni)
    if attacker_card.name.lower() in {n.lower() for n in names}:
        return bonus
    return 0


def _passive_damage_reduction(defender_card: Card) -> int:
    """Return the flat damage reduction from the defender's passive ability."""
    ab = defender_card.ability
    if ab is None or not ab.effect_text:
        return 0
    import re as _re
    m = _re.search(r"takes -(\d+) damage from attacks", ab.effect_text.lower())
    if m:
        return int(m.group(1))
    return 0


# ---------------------------------------------------------------------------
# Post-damage no-op handlers for damage-modifier effect names
# ---------------------------------------------------------------------------
# These effects are consumed entirely in phase 1 (compute_damage_modifier).
# They still appear in the parsed effect list that ``apply_effects`` walks in
# phase 3, so we register trivial no-op handlers to avoid "no handler" warnings.

_DAMAGE_MODIFIER_NAMES = (
    "coin_flip_bonus_damage",
    "coin_flip_nothing",
    "both_coins_bonus",
    "multi_coin_damage",
    "flip_until_tails_damage",
    "bonus_per_bench",
    "bonus_per_bench_element",
    "bonus_per_bench_named",
    "bonus_per_opponent_energy",
    "bonus_if_extra_water_energy",
    "bonus_if_opponent_damaged",
    "bonus_if_self_damaged",
    "bonus_if_opponent_poisoned",
    # --- new damage modifier names ---
    "multi_coin_per_energy_damage",
    "multi_coin_per_typed_energy_damage",
    "multi_coin_per_pokemon_damage",
    "flip_until_tails_bonus",
    "multi_coin_bonus",
    "bonus_per_opponent_bench",
    "bonus_if_tool_attached",
    "bonus_if_opponent_has_tool",
    "bonus_if_opponent_ex",
    "bonus_if_opponent_basic",
    "bonus_if_opponent_element",
    "bonus_if_opponent_has_ability",
    "bonus_if_bench_damaged",
    "bonus_if_ko_last_turn",
    "bonus_if_played_supporter",
    "bonus_if_just_promoted",
    "bonus_if_opponent_more_hp",
    "bonus_if_opponent_has_status",
    "bonus_equal_to_damage_taken",
    "bonus_if_extra_energy",
    "bonus_if_named_in_play",
    "halve_opponent_hp",
    "double_heads_instant_ko",
)


def _noop_handler(ctx: EffectContext, **kwargs) -> GameState:
    return ctx.state


for _name in _DAMAGE_MODIFIER_NAMES:
    register_effect(_name)(_noop_handler)


@register_effect("coin_flip_bonus_or_self_damage")
def coin_flip_bonus_or_self_damage_post(
    ctx: EffectContext, bonus: int = 0, self_damage: int = 0
) -> GameState:
    """Apply self-damage scheduled by the paired damage-modifier phase.

    The damage-modifier phase flips a single coin for this effect. On heads it
    added ``bonus`` to the attack; on tails it wrote ``self_damage_on_tails``
    into the scratch dict so we can apply it here without flipping a second
    coin.
    """
    amount = ctx.extra.get("self_damage_on_tails", 0)
    if amount <= 0 or ctx.source_ref is None:
        return ctx.state
    return mutate_slot(
        ctx.state,
        ctx.source_ref,
        lambda s: setattr(s, "current_hp", max(0, s.current_hp - amount)),
    )
