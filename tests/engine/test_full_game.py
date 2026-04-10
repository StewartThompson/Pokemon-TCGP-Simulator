"""End-to-end smoke test: Random vs Random full games."""
from __future__ import annotations

import pytest

from ptcgp.cards.database import load_defaults
from ptcgp.cards.types import Element


# ---------------------------------------------------------------------------
# Module-level setup: load cards once
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module", autouse=True)
def _load_cards():
    load_defaults()


# ---------------------------------------------------------------------------
# Inline game runner
# ---------------------------------------------------------------------------

def _make_deck() -> tuple[list[str], list[Element]]:
    """Build a 20-card deck with a grass energy zone.

    Deck composition (max 2 of each name, at least 1 basic):
    - Bulbasaur x2      (a1-001)   Basic Grass
    - Caterpie x2       (a1-005)   Basic Grass
    - Metapod x2        (a1-006)   Stage 1
    - Weedle x2         (a1-008)   Basic Grass
    - Kakuna x2         (a1-009)   Stage 1
    - Beedrill x2       (a1-010)   Stage 2
    - Petilil x2        (a1-029)   Basic Grass
    - Ivysaur x2        (a1-002)   Stage 1
    - Charmander x2     (a1-230)   Basic Fire
    - Vulpix x2         (a1-037)   Basic Fire
    Total = 20 cards (8 basics, 5+5 evolutions, mixed elements)
    """
    deck = (
        ["a1-001"] * 2   # Bulbasaur
        + ["a1-005"] * 2  # Caterpie
        + ["a1-006"] * 2  # Metapod
        + ["a1-008"] * 2  # Weedle
        + ["a1-009"] * 2  # Kakuna
        + ["a1-010"] * 2  # Beedrill
        + ["a1-029"] * 2  # Petilil
        + ["a1-002"] * 2  # Ivysaur
        + ["a1-230"] * 2  # Charmander
        + ["a1-037"] * 2  # Vulpix
    )
    assert len(deck) == 20
    energy = [Element.GRASS, Element.FIRE]
    return deck, energy


MAX_STEPS = 10000


def run_one_game(seed: int) -> int | None:
    """Run a full game of Random vs Random. Return winner (0, 1, or -1 for tie)."""
    from ptcgp.engine.state import GamePhase
    from ptcgp.engine.actions import ActionKind
    from ptcgp.engine.setup import create_game, start_game
    from ptcgp.engine.legal_actions import get_legal_actions, get_legal_promotions
    from ptcgp.engine.mutations import apply_action
    from ptcgp.engine.ko import check_winner
    from ptcgp.engine.turn import start_turn, end_turn
    from ptcgp.engine.checkup import resolve_between_turns

    deck1, energy1 = _make_deck()
    deck2, energy2 = _make_deck()

    state = create_game(deck1, deck2, energy1, energy2, seed=seed)
    state = start_game(state)

    steps = 0
    while state.winner is None and steps < MAX_STEPS:
        steps += 1

        if state.phase == GamePhase.AWAITING_BENCH_PROMOTION:
            # Find who needs to promote (player with no active)
            promoting = 0 if state.players[0].active is None else 1
            promotions = get_legal_promotions(state, promoting)
            if not promotions:
                break  # no bench Pokemon left — handle_ko should have caught this
            action = state.rng.choice(promotions)
            state = apply_action(state, action)
            # After promotion, transition back to game flow
            state = resolve_between_turns(state)
            state = end_turn(state)
            if check_winner(state) is None and state.phase == GamePhase.MAIN:
                state = start_turn(state)
            continue

        legal = get_legal_actions(state)
        if not legal:
            break

        action = state.rng.choice(legal)
        state = apply_action(state, action)

        if action.kind in (ActionKind.ATTACK, ActionKind.END_TURN):
            if state.phase == GamePhase.AWAITING_BENCH_PROMOTION:
                continue  # handle promotion next iteration
            state = resolve_between_turns(state)
            state = end_turn(state)
            if check_winner(state) is None and state.phase == GamePhase.MAIN:
                state = start_turn(state)

    return state.winner if state.winner is not None else -1


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_single_game_completes():
    """A single game with seed=42 finishes without error."""
    result = run_one_game(seed=42)
    assert result in (0, 1, -1), f"Unexpected result: {result}"


def test_winner_is_valid():
    """Winner is always 0, 1, or -1 (tie)."""
    result = run_one_game(seed=42)
    assert result in (0, 1, -1)


def test_ten_games_all_complete():
    """Seeds 0-9 all finish without exception."""
    results = []
    for seed in range(10):
        result = run_one_game(seed=seed)
        assert result in (0, 1, -1), f"Seed {seed} gave invalid result: {result}"
        results.append(result)
    # At least some games should have a definitive winner (not all ties)
    winners = [r for r in results if r in (0, 1)]
    assert len(winners) >= 1, "Expected at least one game to have a definitive winner"


def test_game_not_too_long():
    """Game finishes within MAX_STEPS steps."""
    from ptcgp.engine.state import GamePhase
    from ptcgp.engine.actions import ActionKind
    from ptcgp.engine.setup import create_game, start_game
    from ptcgp.engine.legal_actions import get_legal_actions, get_legal_promotions
    from ptcgp.engine.mutations import apply_action
    from ptcgp.engine.ko import check_winner
    from ptcgp.engine.turn import start_turn, end_turn
    from ptcgp.engine.checkup import resolve_between_turns

    deck1, energy1 = _make_deck()
    deck2, energy2 = _make_deck()

    state = create_game(deck1, deck2, energy1, energy2, seed=7)
    state = start_game(state)

    steps = 0
    while state.winner is None and steps < MAX_STEPS:
        steps += 1

        if state.phase == GamePhase.AWAITING_BENCH_PROMOTION:
            promoting = 0 if state.players[0].active is None else 1
            promotions = get_legal_promotions(state, promoting)
            if not promotions:
                break
            action = state.rng.choice(promotions)
            state = apply_action(state, action)
            state = resolve_between_turns(state)
            state = end_turn(state)
            if check_winner(state) is None and state.phase == GamePhase.MAIN:
                state = start_turn(state)
            continue

        legal = get_legal_actions(state)
        if not legal:
            break

        action = state.rng.choice(legal)
        state = apply_action(state, action)

        if action.kind in (ActionKind.ATTACK, ActionKind.END_TURN):
            if state.phase == GamePhase.AWAITING_BENCH_PROMOTION:
                continue
            state = resolve_between_turns(state)
            state = end_turn(state)
            if check_winner(state) is None and state.phase == GamePhase.MAIN:
                state = start_turn(state)

    assert steps < MAX_STEPS, f"Game took too many steps ({steps} >= {MAX_STEPS})"


def test_multiple_seeds_no_exception():
    """Run seeds 10-19 to check for unexpected exceptions."""
    for seed in range(10, 20):
        result = run_one_game(seed=seed)
        assert result in (0, 1, -1), f"Seed {seed} gave invalid result: {result}"
