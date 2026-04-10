"""Tests for RandomAgent and HeuristicAgent."""
from __future__ import annotations

import pytest

from ptcgp.engine.actions import Action, ActionKind, SlotRef
from ptcgp.engine.state import GamePhase, GameState, PlayerState, PokemonSlot
from ptcgp.agents.random_agent import RandomAgent
from ptcgp.agents.heuristic import HeuristicAgent


# ---------------------------------------------------------------------------
# Module-level setup: load cards once (needed by HeuristicAgent scoring)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module", autouse=True)
def _load_cards():
    from ptcgp.cards.database import load_defaults
    load_defaults()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _minimal_state(phase: GamePhase = GamePhase.MAIN) -> GameState:
    """Build a minimal GameState sufficient for basic agent tests."""
    state = GameState(phase=phase)
    state.players[0].active = PokemonSlot(card_id="a1-001", current_hp=70, max_hp=70)
    state.players[1].active = PokemonSlot(card_id="a1-010", current_hp=60, max_hp=60)
    return state


def _legal_actions_basic() -> list[Action]:
    """A minimal set of legal actions for testing."""
    return [
        Action(kind=ActionKind.END_TURN),
        Action(kind=ActionKind.ATTACK, attack_index=0),
    ]


# ---------------------------------------------------------------------------
# RandomAgent tests
# ---------------------------------------------------------------------------

def test_random_agent_chooses_from_legal():
    """RandomAgent always returns an action from the legal list."""
    agent = RandomAgent(seed=42)
    state = _minimal_state()
    legal = _legal_actions_basic()
    for _ in range(20):
        action = agent.choose_action(state, legal)
        assert action in legal


def test_random_agent_seeded():
    """Same seed → same sequence of choices."""
    legal = _legal_actions_basic()
    state = _minimal_state()

    agent1 = RandomAgent(seed=123)
    agent2 = RandomAgent(seed=123)

    choices1 = [agent1.choose_action(state, legal) for _ in range(10)]
    choices2 = [agent2.choose_action(state, legal) for _ in range(10)]

    assert choices1 == choices2


def test_random_agent_never_returns_none():
    """RandomAgent.choose_action never returns None."""
    agent = RandomAgent(seed=0)
    state = _minimal_state()
    legal = _legal_actions_basic()
    for _ in range(50):
        result = agent.choose_action(state, legal)
        assert result is not None


def test_random_agent_single_action():
    """With a single action, RandomAgent always returns it."""
    agent = RandomAgent(seed=7)
    state = _minimal_state()
    only_action = Action(kind=ActionKind.END_TURN)
    for _ in range(10):
        assert agent.choose_action(state, [only_action]) == only_action


def test_random_agent_choose_promotion():
    """RandomAgent.choose_promotion returns from the legal promotions list."""
    agent = RandomAgent(seed=42)
    state = _minimal_state()
    promotions = [
        Action(kind=ActionKind.PROMOTE, target=SlotRef.bench(0, 0)),
        Action(kind=ActionKind.PROMOTE, target=SlotRef.bench(0, 1)),
    ]
    for _ in range(10):
        result = agent.choose_promotion(state, 0, promotions)
        assert result in promotions


def test_random_agent_on_game_start_end_noop():
    """on_game_start and on_game_end don't raise."""
    agent = RandomAgent(seed=1)
    state = _minimal_state()
    agent.on_game_start(state, 0)
    agent.on_game_end(state, 0)
    agent.on_game_end(state, None)


# ---------------------------------------------------------------------------
# HeuristicAgent tests
# ---------------------------------------------------------------------------

def test_heuristic_agent_chooses_from_legal():
    """HeuristicAgent always returns an action from the legal list."""
    agent = HeuristicAgent(seed=42)
    state = _minimal_state()
    legal = _legal_actions_basic()
    action = agent.choose_action(state, legal)
    assert action in legal


def test_heuristic_prefers_attack_over_end_turn():
    """When ATTACK is legal, HeuristicAgent picks ATTACK over END_TURN."""
    agent = HeuristicAgent(seed=0)
    # Build a state where the active Pokemon has enough energy to attack
    state = GameState(phase=GamePhase.MAIN, turn_number=2)
    from ptcgp.cards.types import Element
    attacker = PokemonSlot(
        card_id="a1-001",
        current_hp=70,
        max_hp=70,
        attached_energy={Element.GRASS: 2},
    )
    state.players[0].active = attacker
    state.players[1].active = PokemonSlot(card_id="a1-010", current_hp=60, max_hp=60)

    legal = [
        Action(kind=ActionKind.END_TURN),
        Action(kind=ActionKind.ATTACK, attack_index=0),
    ]
    choice = agent.choose_action(state, legal)
    assert choice.kind == ActionKind.ATTACK


def test_heuristic_prefers_ko_attack():
    """HeuristicAgent prefers an attack that KOs the opponent."""
    agent = HeuristicAgent(seed=0)
    state = GameState(phase=GamePhase.MAIN, turn_number=2)
    from ptcgp.cards.types import Element
    # Use Charizard (a1-006) which has high-damage attacks and Charmander as opponent
    state.players[0].active = PokemonSlot(
        card_id="a1-006",
        current_hp=180,
        max_hp=180,
        attached_energy={Element.FIRE: 4},
    )
    # Charmander with very low HP — should be KO'd by the attack
    state.players[1].active = PokemonSlot(card_id="a1-004", current_hp=10, max_hp=60)

    legal = [
        Action(kind=ActionKind.END_TURN),
        Action(kind=ActionKind.ATTACK, attack_index=0),
        Action(kind=ActionKind.ATTACK, attack_index=1),
    ]
    choice = agent.choose_action(state, legal)
    assert choice.kind == ActionKind.ATTACK


def test_heuristic_never_returns_none():
    """HeuristicAgent never returns None."""
    agent = HeuristicAgent(seed=5)
    state = _minimal_state()
    legal = [Action(kind=ActionKind.END_TURN)]
    result = agent.choose_action(state, legal)
    assert result is not None


def test_heuristic_end_turn_only():
    """HeuristicAgent can handle a list containing only END_TURN."""
    agent = HeuristicAgent(seed=0)
    state = _minimal_state()
    legal = [Action(kind=ActionKind.END_TURN)]
    choice = agent.choose_action(state, legal)
    assert choice.kind == ActionKind.END_TURN


def test_heuristic_prefers_evolve_over_end_turn():
    """HeuristicAgent prefers EVOLVE over END_TURN."""
    agent = HeuristicAgent(seed=0)
    state = _minimal_state()
    legal = [
        Action(kind=ActionKind.END_TURN),
        Action(kind=ActionKind.EVOLVE, hand_index=0, target=SlotRef.active(0)),
    ]
    # Seed hand with an evolution card (Ivysaur evolves from Bulbasaur)
    state.players[0].hand = ["a1-002"]
    choice = agent.choose_action(state, legal)
    assert choice.kind == ActionKind.EVOLVE


def test_heuristic_prefers_bench_fill_over_end_turn():
    """HeuristicAgent prefers PLAY_CARD (basic to bench) over END_TURN."""
    agent = HeuristicAgent(seed=0)
    state = _minimal_state()
    state.players[0].hand = ["a1-001"]
    legal = [
        Action(kind=ActionKind.END_TURN),
        Action(kind=ActionKind.PLAY_CARD, hand_index=0, target=SlotRef.bench(0, 0)),
    ]
    choice = agent.choose_action(state, legal)
    assert choice.kind == ActionKind.PLAY_CARD


def test_heuristic_choose_promotion_picks_highest_hp():
    """HeuristicAgent.choose_promotion picks the bench slot with highest HP."""
    agent = HeuristicAgent(seed=0)
    state = GameState(phase=GamePhase.AWAITING_BENCH_PROMOTION)
    state.players[0].bench[0] = PokemonSlot(card_id="a1-001", current_hp=20, max_hp=70)
    state.players[0].bench[1] = PokemonSlot(card_id="a1-004", current_hp=50, max_hp=60)

    promotions = [
        Action(kind=ActionKind.PROMOTE, target=SlotRef.bench(0, 0)),
        Action(kind=ActionKind.PROMOTE, target=SlotRef.bench(0, 1)),
    ]
    choice = agent.choose_promotion(state, 0, promotions)
    # bench[1] has 50 HP vs bench[0]'s 20 HP
    assert choice.target == SlotRef.bench(0, 1)


def test_heuristic_on_game_start_end_noop():
    """on_game_start and on_game_end don't raise for HeuristicAgent."""
    agent = HeuristicAgent(seed=1)
    state = _minimal_state()
    agent.on_game_start(state, 0)
    agent.on_game_end(state, 1)
    agent.on_game_end(state, None)
