"""Turn management functions — start and end player turns."""
from __future__ import annotations

from ptcgp.engine.actions import SlotRef
from ptcgp.engine.checkup import resolve_between_turns
from ptcgp.engine.ko import check_winner, handle_ko
from ptcgp.engine.state import GamePhase, GameState


def start_turn(state: GameState) -> GameState:
    """Prepare the current player's turn.

    - Increments turn_number (the very first call brings it from -1 to 0).
    - Increments ``turns_in_play`` on all current player's Pokemon.
    - Resets per-turn player flags and per-turn per-Pokemon flags.
    - Draws a card (skipped on turn 0).
    - Generates energy (skipped on turn 0).
    """
    state = state.copy()
    state.turn_number += 1

    player = state.current

    for slot in player.all_pokemon():
        slot.turns_in_play += 1
        slot.evolved_this_turn = False
        slot.ability_used_this_turn = False

    player.has_attached_energy = False
    player.has_played_supporter = False
    player.has_retreated = False

    # Turn-scoped buffs reset each turn
    player.attack_damage_bonus = 0
    player.attack_damage_bonus_names = ()
    player.retreat_cost_modifier = 0

    # Promote incoming flags to "this turn"
    player.cant_play_supporter_this_turn = player.cant_play_supporter_incoming
    player.cant_play_supporter_incoming = False

    # Turn 0 = first player's very first turn: skip draw and energy.
    if state.turn_number == 0:
        return state

    if player.deck:
        player.hand.append(player.deck.pop())

    if player.energy_types:
        player.energy_available = state.rng.choice(player.energy_types)

    return state


def resolve_status_kos(state: GameState) -> GameState:
    """Process any KO that occurred from status damage on the current player's active.

    ``resolve_between_turns`` only clamps HP to 0; this helper actually calls
    ``handle_ko`` so points are awarded and bench promotion is triggered.
    """
    active = state.current.active
    if active is None or active.current_hp > 0:
        return state
    return handle_ko(state, SlotRef.active(state.current_player))


def advance_turn(state: GameState) -> GameState:
    """Run the full between-turns sequence: checkup → status KOs → end → start.

    If a status KO leaves the current player without an active Pokemon and
    they have bench Pokemon, the state is returned in ``AWAITING_BENCH_PROMOTION``
    phase — the caller is responsible for prompting a promotion and then calling
    ``advance_turn`` again (or ``_after_promotion``) to continue.
    """
    state = resolve_between_turns(state)
    state = resolve_status_kos(state)

    if check_winner(state) is not None:
        return state
    if state.phase == GamePhase.AWAITING_BENCH_PROMOTION:
        return state

    state = end_turn(state)
    if check_winner(state) is None and state.phase == GamePhase.MAIN:
        state = start_turn(state)
    return state


def end_turn(state: GameState) -> GameState:
    """End the current player's turn and switch active player.

    Clears any ``cant_attack_next_turn`` and damage-prevention flags on the
    ending player's Pokemon — those covered exactly one turn and are now spent.
    """
    state = state.copy()
    for slot in state.current.all_pokemon():
        slot.cant_attack_next_turn = False
        slot.cant_retreat_next_turn = False
        slot.prevent_damage_next_turn = False
        slot.incoming_damage_reduction = 0
        slot.attack_bonus_next_turn_self = 0
    state.current.energy_available = None
    state.current.cant_play_supporter_this_turn = False
    state.current_player = 1 - state.current_player
    return state
