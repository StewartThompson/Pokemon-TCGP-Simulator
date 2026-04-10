"""Game setup functions — create and initialize a GameState for play."""
from __future__ import annotations

import random
from typing import Optional

from ptcgp.cards.database import get_card
from ptcgp.cards.types import Element
from ptcgp.engine.constants import BENCH_SIZE, INITIAL_HAND_SIZE
from ptcgp.engine.state import GamePhase, GameState, PokemonSlot


def create_game(
    deck1: list[str],
    deck2: list[str],
    energy_types1: list[Element],
    energy_types2: list[Element],
    seed: Optional[int] = None,
) -> GameState:
    """Create a new GameState in SETUP phase.

    Does NOT shuffle decks or draw hands; call ``start_game`` or the interactive
    setup helpers for that.
    """
    state = GameState()
    state.rng = random.Random(seed)

    state.players[0].deck = list(deck1)
    state.players[0].energy_types = list(energy_types1)

    state.players[1].deck = list(deck2)
    state.players[1].energy_types = list(energy_types2)

    state.phase = GamePhase.SETUP
    return state


def draw_opening_hands(state: GameState) -> GameState:
    """Shuffle and draw opening hands for both players (with mulligan)."""
    state = state.copy()
    state = _draw_opening_hand(state, 0)
    state = _draw_opening_hand(state, 1)
    return state


def apply_setup_placement(
    state: GameState,
    player_index: int,
    active_id: str,
    bench_ids: list[str],
) -> GameState:
    """Place a player's chosen Active and bench Pokemon during setup.

    Removes the placed cards from the player's hand.
    """
    state = state.copy()
    player = state.players[player_index]

    card = get_card(active_id)
    player.active = PokemonSlot(card_id=active_id, current_hp=card.hp, max_hp=card.hp)
    player.hand.remove(active_id)

    for bench_idx, cid in enumerate(bench_ids[:BENCH_SIZE]):
        card = get_card(cid)
        player.bench[bench_idx] = PokemonSlot(
            card_id=cid, current_hp=card.hp, max_hp=card.hp
        )
        player.hand.remove(cid)

    return state


def finalize_setup(state: GameState) -> GameState:
    """Coin flip for first player, then start the first turn."""
    state = state.copy()
    state.first_player = 0 if state.rng.random() < 0.5 else 1
    state.current_player = state.first_player
    state.phase = GamePhase.MAIN
    state.turn_number = -1
    from ptcgp.engine.turn import start_turn
    return start_turn(state)


def start_game(state: GameState) -> GameState:
    """Non-interactive bootstrap: draw, auto-place, coin-flip, start turn 0.

    Used by tests and default test fixtures. Interactive runners should instead
    compose ``draw_opening_hands`` / ``apply_setup_placement`` / ``finalize_setup``
    so that each agent can choose its own placement.
    """
    state = draw_opening_hands(state)
    for pi in range(2):
        basics = [cid for cid in state.players[pi].hand if _is_basic_pokemon(cid)]
        if not basics:
            continue
        state = apply_setup_placement(state, pi, basics[0], basics[1 : BENCH_SIZE + 1])
    return finalize_setup(state)


def _draw_opening_hand(state: GameState, player_index: int) -> GameState:
    """Shuffle the player's deck and draw INITIAL_HAND_SIZE cards.

    If no Basic Pokemon is in hand, shuffle back and redraw until at least one
    Basic is found.
    """
    player = state.players[player_index]

    while True:
        state.rng.shuffle(player.deck)

        drawn = player.deck[:INITIAL_HAND_SIZE]
        player.deck = player.deck[INITIAL_HAND_SIZE:]
        player.hand = drawn

        if any(_is_basic_pokemon(cid) for cid in player.hand):
            break

        # No basic — return hand to deck and retry.
        player.deck = list(player.hand) + player.deck
        player.hand = []

    return state


def _is_basic_pokemon(card_id: str) -> bool:
    try:
        return get_card(card_id).is_basic_pokemon
    except KeyError:
        return False
