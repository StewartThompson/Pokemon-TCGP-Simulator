"""Tests for ptcgp/engine/ko.py — KO handling, bench promotion, win conditions."""
from __future__ import annotations

import pytest

from ptcgp.cards.card import Card
from ptcgp.cards.attack import Attack
from ptcgp.cards.database import clear_db, register_card
from ptcgp.cards.types import CardKind, CostSymbol, Element, Stage
from ptcgp.engine.actions import SlotRef
from ptcgp.engine.constants import POINTS_TO_WIN, MAX_TURNS
from ptcgp.engine.ko import check_winner, handle_ko, promote_bench
from ptcgp.engine.state import GamePhase, GameState, PlayerState, PokemonSlot


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_pokemon(
    cid: str,
    hp: int = 70,
    is_ex: bool = False,
    is_mega_ex: bool = False,
) -> Card:
    return Card(
        id=cid,
        name=f"TestMon-{cid}",
        kind=CardKind.POKEMON,
        stage=Stage.BASIC,
        element=Element.FIRE,
        hp=hp,
        is_ex=is_ex,
        is_mega_ex=is_mega_ex,
        attacks=(Attack("Scratch", 30, (CostSymbol.COLORLESS,)),),
    )


def _make_state(
    p0_active_id: str = "p0-active",
    p1_active_id: str = "p1-active",
    p0_bench: list[str | None] | None = None,
    p0_points: int = 0,
    p1_points: int = 0,
    phase: GamePhase = GamePhase.MAIN,
    turn_number: int = 0,
) -> GameState:
    """Build a minimal two-player GameState."""
    p0_bench_slots = [None, None, None]
    if p0_bench:
        for i, cid in enumerate(p0_bench):
            if cid is not None:
                p0_bench_slots[i] = PokemonSlot(card_id=cid, current_hp=70, max_hp=70)

    p0 = PlayerState(
        active=PokemonSlot(card_id=p0_active_id, current_hp=70, max_hp=70),
        bench=p0_bench_slots,
        points=p0_points,
    )
    p1 = PlayerState(
        active=PokemonSlot(card_id=p1_active_id, current_hp=70, max_hp=70),
        points=p1_points,
    )

    return GameState(
        players=[p0, p1],
        current_player=0,
        phase=phase,
        turn_number=turn_number,
    )


@pytest.fixture(autouse=True)
def fresh_db():
    clear_db()
    yield
    clear_db()


# ---------------------------------------------------------------------------
# handle_ko tests
# ---------------------------------------------------------------------------

def test_ko_awards_1_point():
    """KO a regular (non-ex) Pokemon: attacking player gets 1 point."""
    register_card(_make_pokemon("p0-active"))
    register_card(_make_pokemon("p1-active"))

    state = _make_state()
    ko_ref = SlotRef.active(1)  # player 1's active is KO'd

    result = handle_ko(state, ko_ref)

    # Player 0 (1 - 1) should get 1 point
    assert result.players[0].points == 1
    assert result.players[1].points == 0


def test_ko_awards_2_points_ex():
    """KO an EX Pokemon: attacking player gets 2 points."""
    register_card(_make_pokemon("p0-active"))
    register_card(_make_pokemon("p1-active", is_ex=True))

    state = _make_state()
    ko_ref = SlotRef.active(1)

    result = handle_ko(state, ko_ref)

    assert result.players[0].points == 2


def test_ko_removes_from_play():
    """KO'd Pokemon slot becomes None."""
    register_card(_make_pokemon("p0-active"))
    register_card(_make_pokemon("p1-active"))

    state = _make_state()
    ko_ref = SlotRef.active(1)

    result = handle_ko(state, ko_ref)

    assert result.players[1].active is None


def test_ko_adds_to_discard():
    """KO'd Pokemon card_id is added to the losing player's discard pile."""
    register_card(_make_pokemon("p0-active"))
    register_card(_make_pokemon("p1-active"))

    state = _make_state()
    ko_ref = SlotRef.active(1)

    result = handle_ko(state, ko_ref)

    assert "p1-active" in result.players[1].discard


def test_ko_active_triggers_bench_promotion_phase():
    """KO'ing the Active with bench available → phase becomes AWAITING_BENCH_PROMOTION."""
    register_card(_make_pokemon("p0-active"))
    register_card(_make_pokemon("p1-active"))
    register_card(_make_pokemon("p0-bench1"))

    state = _make_state(p0_bench=["p0-bench1"])
    ko_ref = SlotRef.active(0)  # player 0's active is KO'd

    result = handle_ko(state, ko_ref)

    assert result.phase == GamePhase.AWAITING_BENCH_PROMOTION


def test_ko_no_bench_triggers_game_over():
    """KO'ing Active with no bench → winner is set immediately (no promotion needed)."""
    register_card(_make_pokemon("p0-active"))
    register_card(_make_pokemon("p1-active"))

    # Player 0 has no bench
    state = _make_state()
    assert all(s is None for s in state.players[0].bench)

    ko_ref = SlotRef.active(0)  # player 0's active is KO'd, no bench

    result = handle_ko(state, ko_ref)

    assert result.winner == 1  # player 1 wins
    assert result.phase == GamePhase.GAME_OVER


def test_ko_win_by_points():
    """When awarding player reaches POINTS_TO_WIN, state.winner is set."""
    register_card(_make_pokemon("p0-active"))
    register_card(_make_pokemon("p1-active"))

    # Player 0 already at 2 points, KO'ing p1's regular Pokemon gives 1 more → win
    state = _make_state(p0_points=POINTS_TO_WIN - 1)
    ko_ref = SlotRef.active(1)

    result = handle_ko(state, ko_ref)

    assert result.winner == 0
    assert result.phase == GamePhase.GAME_OVER


def test_ko_mega_ex_instant_win():
    """KO'ing a Mega EX (3 points) is an instant win regardless of prior points."""
    register_card(_make_pokemon("p0-active"))
    register_card(_make_pokemon("p1-mega", is_mega_ex=True))

    state = _make_state(p1_active_id="p1-mega")
    ko_ref = SlotRef.active(1)

    result = handle_ko(state, ko_ref)

    assert result.winner == 0
    assert result.phase == GamePhase.GAME_OVER


def test_ko_tool_added_to_discard():
    """KO'd Pokemon with a tool card: both Pokemon and tool go to discard."""
    register_card(_make_pokemon("p0-active"))
    register_card(_make_pokemon("p1-active"))
    register_card(Card(
        id="tool-001",
        name="Tool Card",
        kind=CardKind.TOOL,
        trainer_effect_text="Boost ATK.",
    ))

    state = _make_state()
    state.players[1].active.tool_card_id = "tool-001"

    ko_ref = SlotRef.active(1)
    result = handle_ko(state, ko_ref)

    assert "p1-active" in result.players[1].discard
    assert "tool-001" in result.players[1].discard


# ---------------------------------------------------------------------------
# promote_bench tests
# ---------------------------------------------------------------------------

def test_promote_bench_restores_main_phase():
    """promote_bench moves bench Pokemon to active and sets phase back to MAIN."""
    register_card(_make_pokemon("p0-active"))
    register_card(_make_pokemon("p1-active"))
    register_card(_make_pokemon("p0-bench1"))

    state = _make_state(p0_bench=["p0-bench1"])
    # Simulate an active KO: set active to None and phase to AWAITING
    state.players[0].active = None
    state.phase = GamePhase.AWAITING_BENCH_PROMOTION

    result = promote_bench(state, promoting_player=0, bench_slot=0)

    assert result.phase == GamePhase.MAIN
    assert result.players[0].active is not None
    assert result.players[0].active.card_id == "p0-bench1"
    assert result.players[0].bench[0] is None


def test_promote_bench_wrong_phase_raises():
    """promote_bench raises ValueError if not in AWAITING_BENCH_PROMOTION phase."""
    register_card(_make_pokemon("p0-active"))
    register_card(_make_pokemon("p1-active"))
    register_card(_make_pokemon("p0-bench1"))

    state = _make_state(p0_bench=["p0-bench1"])
    # Phase is MAIN, not AWAITING_BENCH_PROMOTION
    assert state.phase == GamePhase.MAIN

    with pytest.raises(ValueError, match="AWAITING_BENCH_PROMOTION"):
        promote_bench(state, promoting_player=0, bench_slot=0)


def test_promote_bench_empty_slot_raises():
    """promote_bench raises ValueError if the bench slot is empty."""
    register_card(_make_pokemon("p0-active"))
    register_card(_make_pokemon("p1-active"))

    state = _make_state()
    state.players[0].active = None
    state.phase = GamePhase.AWAITING_BENCH_PROMOTION

    with pytest.raises(ValueError):
        promote_bench(state, promoting_player=0, bench_slot=0)


# ---------------------------------------------------------------------------
# check_winner tests
# ---------------------------------------------------------------------------

def test_check_winner_at_points():
    """Player at POINTS_TO_WIN → check_winner returns their index."""
    register_card(_make_pokemon("p0-active"))
    register_card(_make_pokemon("p1-active"))

    state = _make_state(p0_points=POINTS_TO_WIN)

    result = check_winner(state)

    assert result == 0


def test_check_winner_no_winner_yet():
    """Neither player at threshold → check_winner returns None."""
    register_card(_make_pokemon("p0-active"))
    register_card(_make_pokemon("p1-active"))

    state = _make_state(p0_points=0, p1_points=1)

    result = check_winner(state)

    assert result is None


def test_check_winner_turn_limit():
    """turn_number >= MAX_TURNS → check_winner returns -1 (tie)."""
    register_card(_make_pokemon("p0-active"))
    register_card(_make_pokemon("p1-active"))

    state = _make_state(turn_number=MAX_TURNS)

    result = check_winner(state)

    assert result == -1


def test_check_winner_already_set():
    """If state.winner is already set, check_winner returns it directly."""
    register_card(_make_pokemon("p0-active"))
    register_card(_make_pokemon("p1-active"))

    state = _make_state()
    state.winner = 1

    result = check_winner(state)

    assert result == 1


def test_check_winner_no_pokemon_in_play():
    """If a player has no Pokemon in play, their opponent wins."""
    register_card(_make_pokemon("p1-active"))
    register_card(_make_pokemon("p0-active"))

    state = _make_state()
    # Remove all of player 0's Pokemon
    state.players[0].active = None

    result = check_winner(state)

    assert result == 1  # player 1 wins since player 0 has no Pokemon
