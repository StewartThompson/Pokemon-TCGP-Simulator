"""Evolution logic for Pokemon in play."""
from __future__ import annotations

from ptcgp.cards.database import get_card
from ptcgp.cards.types import Stage
from ptcgp.engine.actions import SlotRef
from ptcgp.engine.slot_utils import get_slot
from ptcgp.engine.state import GameState, PokemonSlot


def evolve_pokemon(state: GameState, hand_index: int, target: SlotRef) -> GameState:
    """Evolve a Pokemon in play with a card from hand."""
    player = state.players[state.current_player]

    if hand_index < 0 or hand_index >= len(player.hand):
        raise ValueError(f"Invalid hand_index {hand_index}: hand has {len(player.hand)} cards")

    evo_card_id = player.hand[hand_index]
    evo_card = get_card(evo_card_id)

    # Validation 1: Must be Stage 1 or Stage 2
    if evo_card.stage not in (Stage.STAGE_1, Stage.STAGE_2):
        raise ValueError(
            f"Card {evo_card.name!r} is not a Stage 1 or Stage 2 Pokemon (stage: {evo_card.stage})"
        )

    # Validation 2: evolves_from must match target slot's card name
    old_slot = get_slot(state, target)
    if old_slot is None:
        raise ValueError(f"No Pokemon in target slot {target}")

    old_card = get_card(old_slot.card_id)
    if evo_card.evolves_from != old_card.name:
        raise ValueError(
            f"{evo_card.name!r} evolves from {evo_card.evolves_from!r}, "
            f"but target is {old_card.name!r}"
        )

    # Validation 3: Must have been in play before this turn
    if old_slot.turns_in_play < 1:
        raise ValueError(
            f"{old_card.name!r} was just placed; it must be in play for at least 1 turn to evolve"
        )

    # Validation 4: Cannot evolve twice in one turn
    if old_slot.evolved_this_turn:
        raise ValueError(f"{old_card.name!r} has already evolved this turn")

    # Validation 5: Cannot evolve on the very first turn
    if state.turn_number == 0 or (state.turn_number == 1 and state.current_player != state.first_player):
        raise ValueError("Cannot evolve on the first turn of the game")

    # All validations passed — apply copy-on-write
    state = state.copy()
    player = state.players[state.current_player]

    # Remove evo card from hand
    player.hand.pop(hand_index)

    # Re-resolve old slot from new state
    old_slot = get_slot(state, target)
    old_card = get_card(old_slot.card_id)

    # Calculate HP: carry over damage taken
    damage_taken = old_slot.max_hp - old_slot.current_hp
    new_current_hp = max(0, evo_card.hp - damage_taken)

    # Build new PokemonSlot
    new_slot = PokemonSlot(
        card_id=evo_card.id,
        current_hp=new_current_hp,
        max_hp=evo_card.hp,
        attached_energy=dict(old_slot.attached_energy),
        status_effects=set(),        # evolving clears all status
        turns_in_play=old_slot.turns_in_play,
        tool_card_id=old_slot.tool_card_id,
        evolved_this_turn=True,
        ability_used_this_turn=False,
        cant_attack_next_turn=False,
    )

    # Replace target slot
    if target.slot == -1:
        player.active = new_slot
    else:
        player.bench[target.slot] = new_slot

    return state
