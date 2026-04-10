"""Tests for ptcgp/engine/setup.py — game creation and start_game."""
from __future__ import annotations

import pytest

from ptcgp.cards.card import Card
from ptcgp.cards.database import clear_db, register_card
from ptcgp.cards.types import CardKind, Element, Stage
from ptcgp.engine.constants import BENCH_SIZE, INITIAL_HAND_SIZE
from ptcgp.engine.setup import create_game, start_game
from ptcgp.engine.state import GamePhase


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_basic(cid: str, name: str = "TestMon", hp: int = 60) -> Card:
    return Card(id=cid, name=name, kind=CardKind.POKEMON, stage=Stage.BASIC,
                element=Element.GRASS, hp=hp)


def _make_item(cid: str, name: str = "Potion") -> Card:
    return Card(id=cid, name=name, kind=CardKind.ITEM,
                trainer_effect_text="Heal 20 HP.")


def _register_test_deck(prefix: str, n_basics: int = 10, n_items: int = 10) -> list[str]:
    """Register n_basics Basic Pokemon + n_items Item cards, return IDs."""
    ids = []
    for i in range(n_basics):
        cid = f"{prefix}-b{i:03d}"
        register_card(_make_basic(cid, name=f"Basic-{prefix}-{i}"))
        ids.append(cid)
    for i in range(n_items):
        cid = f"{prefix}-i{i:03d}"
        register_card(_make_item(cid, name=f"Item-{prefix}-{i}"))
        ids.append(cid)
    return ids


@pytest.fixture(autouse=True)
def fresh_db():
    clear_db()
    yield
    clear_db()


@pytest.fixture
def two_decks():
    deck1 = _register_test_deck("p1")
    deck2 = _register_test_deck("p2")
    return deck1, deck2


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_create_game_basic(two_decks):
    deck1, deck2 = two_decks
    state = create_game(deck1, deck2, [Element.GRASS], [Element.FIRE])
    assert state.phase == GamePhase.SETUP
    assert state.players[0].deck == deck1
    assert state.players[1].deck == deck2
    assert state.players[0].energy_types == [Element.GRASS]
    assert state.players[1].energy_types == [Element.FIRE]


def test_create_game_decks_not_shuffled(two_decks):
    """create_game should NOT shuffle — order preserved until start_game."""
    deck1, deck2 = two_decks
    state = create_game(deck1, deck2, [Element.GRASS], [Element.FIRE])
    assert state.players[0].deck == deck1
    assert state.players[1].deck == deck2


def test_start_game_draws_hands(two_decks):
    deck1, deck2 = two_decks
    state = create_game(deck1, deck2, [Element.GRASS], [Element.FIRE])
    state = start_game(state)
    # Each player's hand + placed Pokemon + remaining deck should account for all cards
    # (some basics were moved to active/bench, not hand)
    p0_in_play = len(state.players[0].all_pokemon())
    p1_in_play = len(state.players[1].all_pokemon())
    # Players drew INITIAL_HAND_SIZE then placed Pokemon out of hand
    # hand + deck + active/bench = INITIAL_HAND_SIZE + original_deck_size - INITIAL_HAND_SIZE
    assert len(state.players[0].hand) >= 0
    assert len(state.players[1].hand) >= 0
    # Total accounted cards per player = hand + deck + in_play
    p0_total = len(state.players[0].hand) + len(state.players[0].deck) + p0_in_play
    p1_total = len(state.players[1].hand) + len(state.players[1].deck) + p1_in_play
    assert p0_total == len(deck1)
    assert p1_total == len(deck2)


def test_start_game_has_active(two_decks):
    deck1, deck2 = two_decks
    state = create_game(deck1, deck2, [Element.GRASS], [Element.FIRE])
    state = start_game(state)
    assert state.players[0].active is not None
    assert state.players[1].active is not None


def test_start_game_active_is_basic(two_decks):
    deck1, deck2 = two_decks
    state = create_game(deck1, deck2, [Element.GRASS], [Element.FIRE])
    state = start_game(state)
    from ptcgp.cards.database import get_card
    for pi in range(2):
        active_card = get_card(state.players[pi].active.card_id)
        assert active_card.stage == Stage.BASIC


def test_start_game_active_hp_set(two_decks):
    deck1, deck2 = two_decks
    state = create_game(deck1, deck2, [Element.GRASS], [Element.FIRE])
    state = start_game(state)
    for pi in range(2):
        slot = state.players[pi].active
        assert slot.current_hp == slot.max_hp
        assert slot.max_hp == 60  # our test basics have hp=60


def test_opening_hand_reshuffled_if_no_basic():
    """When the first 5 cards are all non-basics the hand must be redrawn."""
    # Build a deck: 10 items first, then 10 basics
    # With seed=0, shuffle should eventually produce a hand with a basic
    item_ids = []
    basic_ids = []
    for i in range(10):
        cid = f"reshuffle-item-{i:03d}"
        register_card(_make_item(cid))
        item_ids.append(cid)
    for i in range(10):
        cid = f"reshuffle-basic-{i:03d}"
        register_card(_make_basic(cid))
        basic_ids.append(cid)

    # Construct deck so unshuffled order is all items first
    deck = item_ids + basic_ids

    state = create_game(deck, deck, [Element.GRASS], [Element.GRASS], seed=42)
    state = start_game(state)
    # After start_game both players must have an active Pokemon (proving basics were drawn)
    assert state.players[0].active is not None
    assert state.players[1].active is not None


def test_coin_flip_sets_first_player(two_decks):
    deck1, deck2 = two_decks
    state = create_game(deck1, deck2, [Element.GRASS], [Element.FIRE])
    state = start_game(state)
    assert state.first_player in (0, 1)
    assert state.current_player == state.first_player


def test_seed_reproducible(two_decks):
    deck1, deck2 = two_decks
    state_a = create_game(list(deck1), list(deck2), [Element.GRASS], [Element.FIRE], seed=99)
    state_a = start_game(state_a)

    state_b = create_game(list(deck1), list(deck2), [Element.GRASS], [Element.FIRE], seed=99)
    state_b = start_game(state_b)

    assert state_a.first_player == state_b.first_player
    assert state_a.players[0].active.card_id == state_b.players[0].active.card_id
    assert state_a.players[1].active.card_id == state_b.players[1].active.card_id
    assert state_a.players[0].hand == state_b.players[0].hand
    assert state_a.players[1].hand == state_b.players[1].hand


def test_start_game_phase_is_main(two_decks):
    deck1, deck2 = two_decks
    state = create_game(deck1, deck2, [Element.GRASS], [Element.FIRE])
    state = start_game(state)
    assert state.phase == GamePhase.MAIN


def test_start_game_bench_populated_when_multiple_basics(two_decks):
    """If more than one basic is in the opening hand, extras go to bench."""
    # Deck with 5 basics at the top to guarantee they're all drawn
    basic_ids = []
    for i in range(5):
        cid = f"bench-test-basic-{i}"
        register_card(_make_basic(cid))
        basic_ids.append(cid)
    item_ids = []
    for i in range(15):
        cid = f"bench-test-item-{i}"
        register_card(_make_item(cid))
        item_ids.append(cid)
    deck = basic_ids + item_ids  # basics at front; with seed they may all be drawn

    # Use a fixed seed that keeps basics at front after shuffle — try multiple seeds
    for seed in range(200):
        import random
        rng = random.Random(seed)
        test_deck = list(deck)
        rng.shuffle(test_deck)
        first_five = test_deck[:5]
        from ptcgp.cards.database import get_card
        n_basics_in_hand = sum(
            1 for cid in first_five
            if get_card(cid).stage == Stage.BASIC
        )
        if n_basics_in_hand >= 2:
            state = create_game(deck, deck, [Element.GRASS], [Element.GRASS], seed=seed)
            state = start_game(state)
            # At least one bench slot should be occupied for player 0
            bench_count = state.players[0].bench_count()
            assert bench_count >= 1
            break
