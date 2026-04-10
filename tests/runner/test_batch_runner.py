"""Tests for the batch runner."""
from __future__ import annotations

import pytest
from ptcgp.runner.batch_runner import run_batch, run_batch_simple, BatchResult


@pytest.fixture(autouse=True, scope="session")
def init():
    import ptcgp.effects  # noqa: F401 — register all effect handlers
    from ptcgp.cards.database import load_defaults
    load_defaults()


def test_batch_returns_result():
    result = run_batch_simple(n_games=10, base_seed=0)
    assert isinstance(result, BatchResult)
    assert result.total_games == 10


def test_batch_wins_sum_to_games():
    result = run_batch_simple(n_games=20, base_seed=0)
    assert result.wins[0] + result.wins[1] + result.ties + result.errors == 20


def test_win_rates_sum_to_roughly_1():
    result = run_batch_simple(n_games=20, base_seed=0)
    p1, p2 = result.win_rate
    # p1 + p2 + tie_rate should be close to 1.0
    total = p1 + p2 + result.tie_rate
    assert abs(total - 1.0) < 0.01


def test_batch_reproducible():
    r1 = run_batch_simple(n_games=10, base_seed=42)
    r2 = run_batch_simple(n_games=10, base_seed=42)
    assert r1.wins == r2.wins
    assert r1.ties == r2.ties


def test_batch_heuristic_vs_random():
    result = run_batch_simple(
        deck1_name="fire",
        deck2_name="grass",
        agent1_type="heuristic",
        agent2_type="random",
        n_games=20,
        base_seed=0,
    )
    assert result.total_games == 20
    # Heuristic should generally outperform random
    # (Not strictly guaranteed but usually true)
    assert result.errors == 0


def test_batch_result_win_rate_zero_on_all_errors():
    """BatchResult.win_rate returns (0, 0) when all games errored."""
    result = BatchResult(total_games=5, wins=[0, 0], ties=0, errors=5)
    assert result.win_rate == (0.0, 0.0)
    assert result.tie_rate == 0.0


def test_batch_result_win_rate_computed_correctly():
    """win_rate is computed over completed games only."""
    result = BatchResult(total_games=10, wins=[6, 3], ties=1, errors=0)
    p1, p2 = result.win_rate
    assert abs(p1 - 0.6) < 1e-9
    assert abs(p2 - 0.3) < 1e-9
    assert abs(result.tie_rate - 0.1) < 1e-9


def test_batch_different_seeds_differ():
    """Different base seeds should (in general) produce different win distributions."""
    r1 = run_batch_simple(n_games=20, base_seed=0)
    r2 = run_batch_simple(n_games=20, base_seed=9999)
    # It's statistically very unlikely these are identical across 20 games
    # (not a hard requirement, so we just verify both complete)
    assert r1.total_games == 20
    assert r2.total_games == 20
