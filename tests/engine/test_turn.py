"""Tests for ptcgp/engine/turn.py — start_turn and end_turn."""
from __future__ import annotations

import pytest

from ptcgp.cards.card import Card
from ptcgp.cards.database import clear_db, register_card
from ptcgp.cards.types import CardKind, Element, Stage
from ptcgp.engine.constants import BENCH_SIZE
from ptcgp.engine.state import GamePhase, GameState, PlayerState, PokemonSlot
from ptcgp.engine.turn import end_turn, start_turn


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_basic(cid: str, hp: int = 60) -> Card:
    return Card(id=cid, name=f"Mon-{cid}", kind=CardKind.POKEMON,
                stage=Stage.BASIC, element=Element.GRASS, hp=hp)


def _make_state(
    deck_size: int = 10,
    energy_types: list[Element] | None = None,
    player_index: int = 0,
    seed: int = 0,
) -> GameState:
    """Build a minimal GameState ready for start_turn testing."""
    if energy_types is None:
        energy_types = [Element.FIRE]

    cid = f"active-{player_index}"
    register_card(_make_basic(cid))

    state = GameState()
    state.rng.seed(seed)
    state.turn_number = -1  # start_turn will increment to 0 for first call
    state.current_player = player_index
    state.first_player = player_index

    player = state.players[player_index]
    player.active = PokemonSlot(card_id=cid, current_hp=60, max_hp=60)
    player.deck = [f"deck-card-{i}" for i in range(deck_size)]
    player.energy_types = list(energy_types)

    state.phase = GamePhase.MAIN
    return state


@pytest.fixture(autouse=True)
def fresh_db():
    clear_db()
    yield
    clear_db()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_first_player_no_draw():
    """turn_number==0: first player should NOT draw a card."""
    state = _make_state(deck_size=10)
    deck_before = list(state.players[0].deck)
    hand_before = list(state.players[0].hand)

    state = start_turn(state)

    assert state.turn_number == 0
    assert state.players[0].deck == deck_before
    assert state.players[0].hand == hand_before


def test_first_player_no_energy():
    """turn_number==0: first player should NOT receive energy."""
    state = _make_state(energy_types=[Element.FIRE])
    state = start_turn(state)

    assert state.turn_number == 0
    assert state.players[0].energy_available is None


def test_second_player_draws():
    """turn_number>=1: current player draws 1 card."""
    state = _make_state(deck_size=10)
    # Simulate it's turn 1 (second half-turn)
    state.turn_number = 0  # start_turn will increment to 1
    state.players[0].hand = []
    deck_before = list(state.players[0].deck)

    state = start_turn(state)

    assert state.turn_number == 1
    assert len(state.players[0].hand) == 1
    assert state.players[0].hand[0] == deck_before[0]
    assert len(state.players[0].deck) == len(deck_before) - 1


def test_second_player_gets_energy():
    """turn_number>=1: current player receives energy from their energy zone."""
    state = _make_state(energy_types=[Element.FIRE], seed=42)
    state.turn_number = 0  # will become 1

    state = start_turn(state)

    assert state.turn_number == 1
    assert state.players[0].energy_available is not None
    assert state.players[0].energy_available in [Element.FIRE]


def test_energy_chosen_from_types():
    """Energy is always one of the player's declared energy types."""
    energy_types = [Element.WATER, Element.LIGHTNING]
    state = _make_state(energy_types=energy_types, seed=7)
    state.turn_number = 0  # will become 1

    state = start_turn(state)

    assert state.players[0].energy_available in energy_types


def test_turns_in_play_increments():
    """Active Pokemon's turns_in_play should increment on start_turn."""
    state = _make_state()
    # Set up active with known turns_in_play
    state.players[0].active.turns_in_play = 3
    state.turn_number = 0  # will become 1

    state = start_turn(state)

    assert state.players[0].active.turns_in_play == 4


def test_bench_pokemon_turns_in_play_increments():
    """Bench Pokemon also get turns_in_play incremented."""
    cid_bench = "bench-mon-001"
    register_card(_make_basic(cid_bench))

    state = _make_state()
    bench_slot = PokemonSlot(card_id=cid_bench, current_hp=60, max_hp=60, turns_in_play=1)
    state.players[0].bench[0] = bench_slot
    state.turn_number = 0  # will become 1

    state = start_turn(state)

    assert state.players[0].bench[0].turns_in_play == 2


def test_per_turn_flags_reset():
    """has_attached_energy, has_played_supporter, has_retreated reset on start_turn."""
    state = _make_state()
    player = state.players[0]
    player.has_attached_energy = True
    player.has_played_supporter = True
    player.has_retreated = True
    state.turn_number = 0  # will become 1

    state = start_turn(state)

    assert not state.players[0].has_attached_energy
    assert not state.players[0].has_played_supporter
    assert not state.players[0].has_retreated


def test_evolved_this_turn_reset():
    """evolved_this_turn flag resets on start_turn."""
    state = _make_state()
    state.players[0].active.evolved_this_turn = True
    state.turn_number = 0  # will become 1

    state = start_turn(state)

    assert not state.players[0].active.evolved_this_turn


def test_ability_used_this_turn_reset():
    """ability_used_this_turn flag resets on start_turn."""
    state = _make_state()
    state.players[0].active.ability_used_this_turn = True
    state.turn_number = 0  # will become 1

    state = start_turn(state)

    assert not state.players[0].active.ability_used_this_turn


def test_empty_deck_no_error():
    """start_turn with an empty deck should not crash (no deck-out penalty)."""
    state = _make_state(deck_size=0)
    state.turn_number = 0  # will become 1
    hand_before = list(state.players[0].hand)

    state = start_turn(state)

    # No card drawn, no crash
    assert state.players[0].deck == []
    assert state.players[0].hand == hand_before


def test_end_turn_clears_energy():
    """end_turn clears energy_available for the current player."""
    state = _make_state()
    state.players[0].energy_available = Element.FIRE

    state = end_turn(state)

    assert state.players[0].energy_available is None


def test_end_turn_switches_player():
    """end_turn switches current_player to the other player."""
    state = _make_state(player_index=0)
    assert state.current_player == 0

    state = end_turn(state)

    assert state.current_player == 1


def test_turn_number_increments_each_start():
    """turn_number increments by 1 on each start_turn call."""
    state = _make_state(deck_size=20)
    assert state.turn_number == -1

    state = start_turn(state)
    assert state.turn_number == 0

    state = start_turn(state)
    assert state.turn_number == 1

    state = start_turn(state)
    assert state.turn_number == 2
