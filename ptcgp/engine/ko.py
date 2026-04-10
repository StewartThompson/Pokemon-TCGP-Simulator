"""KO handling, bench promotion, and win condition checking."""
from __future__ import annotations

from typing import Optional

from ptcgp.engine.state import GameState, GamePhase
from ptcgp.engine.actions import SlotRef
from ptcgp.engine.slot_utils import get_slot, set_slot
from ptcgp.engine.constants import POINTS_TO_WIN, MAX_TURNS
from ptcgp.cards.database import get_card


def handle_ko(state: GameState, ko_ref: SlotRef) -> GameState:
    """Handle a Pokemon being knocked out (hp reached 0).

    Awards points, removes Pokemon from play, handles win conditions.
    """
    state = state.copy()

    slot = get_slot(state, ko_ref)
    if slot is None:
        raise ValueError(f"No Pokemon at slot {ko_ref} to KO")

    card = get_card(slot.card_id)
    ko_points = card.ko_points

    # Award points to the opposing player (the one who caused the KO)
    # Simple rule: always award to 1 - ko_ref.player
    awarding_player = 1 - ko_ref.player
    state.players[awarding_player].points += ko_points

    # Add KO'd Pokemon (and its tool) to losing player's discard pile
    loser_discard = state.players[ko_ref.player].discard
    loser_discard.append(slot.card_id)
    if slot.tool_card_id is not None:
        loser_discard.append(slot.tool_card_id)

    # Remove slot from play
    state = set_slot(state, ko_ref, None)

    # Check win conditions
    awarding_points = state.players[awarding_player].points

    # Check for simultaneous KO tie: if both players are at >= POINTS_TO_WIN
    other_player = ko_ref.player
    other_points = state.players[other_player].points
    if awarding_points >= POINTS_TO_WIN and other_points >= POINTS_TO_WIN:
        state.winner = -1  # tie
        state.phase = GamePhase.GAME_OVER
        return state

    if awarding_points >= POINTS_TO_WIN or ko_points == 3:
        state.winner = awarding_player
        state.phase = GamePhase.GAME_OVER
        return state

    # If the KO'd Pokemon was the Active, handle bench promotion
    if ko_ref.is_active():
        losing_player = state.players[ko_ref.player]
        has_bench = any(s is not None for s in losing_player.bench)

        if not has_bench:
            # No Pokemon left — game over, losing player loses
            state.winner = awarding_player
            state.phase = GamePhase.GAME_OVER
        else:
            state.phase = GamePhase.AWAITING_BENCH_PROMOTION

    return state


def promote_bench(state: GameState, promoting_player: int, bench_slot: int) -> GameState:
    """Promote a bench Pokemon to Active after KO."""
    if state.phase != GamePhase.AWAITING_BENCH_PROMOTION:
        raise ValueError(
            f"Cannot promote bench: game phase is {state.phase}, expected AWAITING_BENCH_PROMOTION"
        )

    bench_ref = SlotRef.bench(promoting_player, bench_slot)
    slot = get_slot(state, bench_ref)

    if slot is None:
        raise ValueError(f"No Pokemon at bench slot {bench_slot} for player {promoting_player}")

    # Move bench[bench_slot] → active
    state = state.copy()
    state.players[promoting_player].active = slot
    state.players[promoting_player].bench[bench_slot] = None
    state.phase = GamePhase.MAIN

    return state


def check_winner(state: GameState) -> Optional[int]:
    """Return winner (0 or 1), -1 for tie, or None if game continues."""
    # If winner is already set, return it
    if state.winner is not None:
        return state.winner

    # Check if a player has reached the point threshold
    for i in range(2):
        if state.players[i].points >= POINTS_TO_WIN:
            return i

    # Check if either player has no Pokemon in play at all
    for i in range(2):
        player = state.players[i]
        if not player.has_any_pokemon():
            return 1 - i

    # Turn limit reached — always a draw per PTCGP rules.
    if state.turn_number >= MAX_TURNS:
        return -1

    return None
