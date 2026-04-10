"""Tests for the game runner (Phase 4 Group F)."""
from __future__ import annotations

import random as stdlib_random

import pytest

from ptcgp.engine import GameState
from ptcgp.cards.types import Element
from ptcgp.runner.game_runner import run_game


# ---------------------------------------------------------------------------
# Ensure the card database is loaded before any test runs
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def _load_card_db():
    """Load the default card database once for all tests in this module."""
    from ptcgp.cards.database import load_defaults, is_loaded
    if not is_loaded():
        load_defaults()


# ---------------------------------------------------------------------------
# Inline random agent (avoids dependency on ptcgp.agents which may not exist)
# ---------------------------------------------------------------------------

class InlineRandomAgent:
    """Minimal agent that makes random legal moves."""

    def __init__(self, seed=None):
        self._rng = stdlib_random.Random(seed)

    def choose_action(self, state, legal_actions):
        return self._rng.choice(legal_actions)

    def choose_promotion(self, state, player_index, legal_promotions):
        return self._rng.choice(legal_promotions)

    def on_game_start(self, state, player_index):
        pass

    def on_game_end(self, state, winner):
        pass


# ---------------------------------------------------------------------------
# Sample decks (inline — no dependency on sample_decks module)
# ---------------------------------------------------------------------------

GRASS_DECK = (
    ["a1-001"] * 2
    + ["a1-002"] * 2
    + ["a1-004"] * 2
    + ["a1-008"] * 2
    + ["a1-009"] * 2
    + ["a1-010"] * 2
    + ["a1-029"] * 2
    + ["a1-030"] * 2
    + ["pa-001"] * 2
    + ["pa-007"] * 2
)

FIRE_DECK = (
    ["a1-230"] * 2
    + ["a2b-010"] * 2
    + ["a1-037"] * 2
    + ["a1-038"] * 2
    + ["a1-008"] * 2
    + ["a1-009"] * 2
    + ["a1-010"] * 2
    + ["pa-005"] * 2
    + ["pa-001"] * 2
    + ["a2-147"] * 2
)

GRASS_ENERGY = [Element.GRASS]
FIRE_ENERGY = [Element.FIRE]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def random_agents():
    return InlineRandomAgent(seed=42), InlineRandomAgent(seed=99)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_single_game_completes(random_agents):
    """A game should finish and produce a valid winner."""
    agent1, agent2 = random_agents
    state, winner = run_game(
        agent1, agent2,
        GRASS_DECK, GRASS_DECK,
        GRASS_ENERGY, GRASS_ENERGY,
        seed=0,
    )
    assert winner in {0, 1, -1}, f"Unexpected winner value: {winner}"


def test_winner_is_valid(random_agents):
    """Winner must be 0, 1, or -1 (never None for a completed game)."""
    agent1, agent2 = random_agents
    state, winner = run_game(
        agent1, agent2,
        GRASS_DECK, FIRE_DECK,
        GRASS_ENERGY, FIRE_ENERGY,
        seed=1,
    )
    assert winner in {0, 1, -1}


def test_100_games_all_complete():
    """100 seeded games should all complete without exception."""
    valid_winners = {0, 1, -1}
    for seed in range(100):
        agent1 = InlineRandomAgent(seed=seed)
        agent2 = InlineRandomAgent(seed=seed + 1000)
        state, winner = run_game(
            agent1, agent2,
            GRASS_DECK, FIRE_DECK,
            GRASS_ENERGY, FIRE_ENERGY,
            seed=seed,
        )
        assert winner in valid_winners, (
            f"Seed {seed}: got winner={winner!r}, expected one of {valid_winners}"
        )


def test_game_returns_final_state(random_agents):
    """run_game should return a GameState as its first element."""
    agent1, agent2 = random_agents
    state, winner = run_game(
        agent1, agent2,
        GRASS_DECK, GRASS_DECK,
        GRASS_ENERGY, GRASS_ENERGY,
        seed=2,
    )
    assert isinstance(state, GameState)


def test_seeded_reproducible():
    """The same seed should produce the same winner deterministically."""
    results = []
    for _ in range(2):
        agent1 = InlineRandomAgent(seed=7)
        agent2 = InlineRandomAgent(seed=8)
        state, winner = run_game(
            agent1, agent2,
            GRASS_DECK, FIRE_DECK,
            GRASS_ENERGY, FIRE_ENERGY,
            seed=42,
        )
        results.append(winner)
    assert results[0] == results[1], (
        f"Same seed produced different winners: {results}"
    )


def test_both_decks_work():
    """Grass vs Fire deck game should complete successfully."""
    agent1 = InlineRandomAgent(seed=10)
    agent2 = InlineRandomAgent(seed=20)
    state, winner = run_game(
        agent1, agent2,
        GRASS_DECK, FIRE_DECK,
        GRASS_ENERGY, FIRE_ENERGY,
        seed=5,
    )
    assert isinstance(state, GameState)
    assert winner in {0, 1, -1}


def test_agent_callbacks_called():
    """on_game_start and on_game_end callbacks should be invoked."""
    calls = []

    class TrackingAgent(InlineRandomAgent):
        def __init__(self, name, seed=None):
            super().__init__(seed=seed)
            self._name = name

        def on_game_start(self, state, player_index):
            calls.append(("start", self._name, player_index))

        def on_game_end(self, state, winner):
            calls.append(("end", self._name, winner))

    agent1 = TrackingAgent("p0", seed=1)
    agent2 = TrackingAgent("p1", seed=2)
    state, winner = run_game(
        agent1, agent2,
        GRASS_DECK, GRASS_DECK,
        GRASS_ENERGY, GRASS_ENERGY,
        seed=3,
    )

    # Both agents should have on_game_start called
    start_calls = [c for c in calls if c[0] == "start"]
    assert len(start_calls) == 2
    assert ("start", "p0", 0) in start_calls
    assert ("start", "p1", 1) in start_calls

    # Both agents should have on_game_end called
    end_calls = [c for c in calls if c[0] == "end"]
    assert len(end_calls) == 2


def test_grass_vs_grass():
    """Mirror match: grass vs grass should complete."""
    agent1 = InlineRandomAgent(seed=30)
    agent2 = InlineRandomAgent(seed=31)
    state, winner = run_game(
        agent1, agent2,
        GRASS_DECK, GRASS_DECK,
        GRASS_ENERGY, GRASS_ENERGY,
        seed=15,
    )
    assert winner in {0, 1, -1}
