"""Attack execution logic for the battle engine."""
from __future__ import annotations

from typing import Optional

from ptcgp.cards.database import get_card
from ptcgp.cards.types import CostSymbol
from ptcgp.engine.actions import SlotRef
from ptcgp.engine.constants import WEAKNESS_BONUS
from ptcgp.engine.state import GameState, PokemonSlot, StatusEffect


def can_pay_cost(slot: PokemonSlot, cost: tuple[CostSymbol, ...]) -> bool:
    """Return True if the slot has enough energy to pay the attack cost."""
    remaining = dict(slot.attached_energy)  # Element -> count
    colorless_needed = 0
    for symbol in cost:
        if symbol == CostSymbol.COLORLESS:
            colorless_needed += 1
        else:
            element = symbol.to_element()
            if remaining.get(element, 0) > 0:
                remaining[element] -= 1
            else:
                return False  # can't pay typed requirement
    total_remaining = sum(remaining.values())
    return total_remaining >= colorless_needed


def _retaliate_damage(defender_slot: PokemonSlot, defender_card) -> int:
    """Return the retaliate damage the defender deals back to the attacker.

    Reads both (a) the defender's passive ability text (e.g. Druddigon's
    "If this Pokémon is in the Active Spot and is damaged by an attack...")
    and (b) the attached tool card's effect text (e.g. Rocky Helmet). The
    retaliate only fires when the defender is currently in the Active Spot.
    """
    import re as _re
    pattern = _re.compile(
        r"is damaged by an attack.*do (\d+) damage to the attacking", _re.IGNORECASE
    )
    total = 0
    # Ability retaliate — only fires from the Active Spot per the card text.
    if defender_card.ability and defender_card.ability.effect_text:
        m = pattern.search(defender_card.ability.effect_text)
        if m:
            total += int(m.group(1))
    # Tool retaliate (Rocky Helmet).
    if defender_slot.tool_card_id:
        try:
            tool_card = get_card(defender_slot.tool_card_id)
        except KeyError:
            tool_card = None
        if tool_card and tool_card.trainer_effect_text:
            m = pattern.search(tool_card.trainer_effect_text)
            if m:
                total += int(m.group(1))
    return total


def execute_attack(
    state: GameState,
    attack_index: int,
    sub_target: Optional[SlotRef] = None,
) -> GameState:
    """Execute the current player's Active Pokemon's attack at ``attack_index``.

    Pipeline:
    1. Validate and pay cost
    2. Confusion check (may short-circuit)
    3. Compute final damage (base + weakness + parsed damage modifiers)
    4. Apply damage to defender (respecting "prevent damage" flags)
    5. Resolve side-effect handlers via the effect registry
    """
    state = state.copy()

    attacker_slot = state.players[state.current_player].active
    if attacker_slot is None:
        raise ValueError("Current player has no active Pokemon")

    attacker_card = get_card(attacker_slot.card_id)
    if attack_index < 0 or attack_index >= len(attacker_card.attacks):
        raise ValueError(f"Invalid attack_index {attack_index} for {attacker_card.name}")

    attack = attacker_card.attacks[attack_index]

    if not can_pay_cost(attacker_slot, attack.cost):
        raise ValueError(
            f"{attacker_card.name} cannot pay cost {attack.cost}: "
            f"has {attacker_slot.attached_energy}"
        )

    # Confusion check — tails means the attack fails entirely.
    if StatusEffect.CONFUSED in attacker_slot.status_effects:
        if state.rng.random() >= 0.5:
            return state

    defender_player = state.players[state.opponent_index]
    if defender_player.active is None:
        raise ValueError("Opponent has no active Pokemon")

    defender_slot = defender_player.active
    defender_card = get_card(defender_slot.card_id)

    # -- Phase 1: compute damage --------------------------------------- #
    base_damage = attack.damage
    if attacker_card.element is not None and defender_card.weakness == attacker_card.element:
        base_damage += WEAKNESS_BONUS

    final_damage = base_damage
    mod_skip = False
    modifier_result: dict = {}
    if attack.effect_text or attack.handler:
        from ptcgp.effects.damage_modifiers import compute_damage_modifier
        final_damage, mod_skip, modifier_result = compute_damage_modifier(
            state=state,
            base_damage=base_damage,
            raw_damage=attack.damage,
            attack_effect_text=attack.effect_text,
            attacker_slot=attacker_slot,
            attacker_card=attacker_card,
            defender_slot=defender_slot,
            defender_card=defender_card,
            handler_str=attack.handler,
            cached_effects=attack.cached_effects,
        )

    # -- Phase 2: apply damage ----------------------------------------- #
    # "Prevent all damage" flags set by previous-turn effects (e.g. coin-flip
    # damage block) take precedence and zero the hit.
    if defender_slot.prevent_damage_next_turn:
        final_damage = 0
        mod_skip = True

    damage_dealt = 0
    if not mod_skip and final_damage > 0:
        damage_dealt = min(final_damage, defender_slot.current_hp)
        defender_slot.current_hp = max(0, defender_slot.current_hp - final_damage)

    # -- Phase 2b: retaliate (Rocky Helmet / Druddigon-style passives) -- #
    if damage_dealt > 0:
        retaliate = _retaliate_damage(defender_slot, defender_card)
        if retaliate > 0:
            attacker_slot.current_hp = max(0, attacker_slot.current_hp - retaliate)

    # -- Phase 3: side-effect handlers --------------------------------- #
    if attack.effect_text or attack.handler:
        from ptcgp.effects.apply import apply_effects
        attacker_ref = SlotRef.active(state.current_player)
        target_ref = sub_target if sub_target is not None else SlotRef.active(state.opponent_index)
        extra = {"damage_dealt": damage_dealt, **modifier_result}
        state = apply_effects(
            state,
            attack.effect_text,
            acting_player=state.current_player,
            source_ref=attacker_ref,
            target_ref=target_ref,
            extra=extra,
            handler_str=attack.handler,
            cached_effects=attack.cached_effects,
        )

    return state
