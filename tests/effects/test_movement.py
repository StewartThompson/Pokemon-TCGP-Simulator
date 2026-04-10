"""Tests for ptcgp.effects.movement — switch_opponent_active."""
import pytest
import random

from ptcgp.cards.database import load_defaults
from ptcgp.engine.state import GameState, PokemonSlot
from ptcgp.engine.actions import SlotRef
from ptcgp.effects.registry import EffectContext, resolve_effect
from ptcgp.effects.base import Effect
import ptcgp.effects  # trigger registration


@pytest.fixture(autouse=True, scope="session")
def init_db():
    load_defaults()


def _make_slot(card_id="a1-001", current_hp=70, max_hp=70) -> PokemonSlot:
    return PokemonSlot(card_id=card_id, current_hp=current_hp, max_hp=max_hp)


def _make_ctx(state, acting=0) -> EffectContext:
    return EffectContext(
        state=state,
        acting_player=acting,
        source_ref=None,
        target_ref=None,
    )


# ---------------------------------------------------------------------------
# switch_opponent_active
# ---------------------------------------------------------------------------

def test_switch_opponent_active():
    """Opponent's active is swapped with a bench Pokemon."""
    state = GameState()
    state.rng = random.Random(0)

    active_slot = _make_slot(card_id="a1-001")   # Bulbasaur as opponent active
    bench_slot = _make_slot(card_id="a1-005")    # Caterpie on bench

    # Player 1 is the opponent (acting player is 0)
    state.players[1].active = active_slot
    state.players[1].bench[0] = bench_slot

    ctx = _make_ctx(state, acting=0)
    effect = Effect(name="switch_opponent_active", params={})
    new_state = resolve_effect(ctx, effect)

    opp = new_state.players[1]
    # Active and bench should have swapped
    # The bench had 1 non-None slot (index 0), so that's where the swap happens
    assert opp.active.card_id == "a1-005"       # bench slot now active
    assert opp.bench[0].card_id == "a1-001"     # old active now on bench


def test_switch_no_bench_noop():
    """switch_opponent_active is a no-op when opponent has no bench Pokemon."""
    state = GameState()
    state.rng = random.Random(0)

    active_slot = _make_slot(card_id="a1-001")
    state.players[1].active = active_slot
    # bench all None

    ctx = _make_ctx(state, acting=0)
    effect = Effect(name="switch_opponent_active", params={})
    new_state = resolve_effect(ctx, effect)

    # Active unchanged
    assert new_state.players[1].active.card_id == "a1-001"
    assert all(s is None for s in new_state.players[1].bench)


def test_switch_opponent_active_multiple_bench():
    """With multiple bench Pokemon, one is picked to become active."""
    state = GameState()
    state.rng = random.Random(0)

    active_slot = _make_slot(card_id="a1-001")   # Bulbasaur active
    bench0 = _make_slot(card_id="a1-005")         # Caterpie bench[0]
    bench1 = _make_slot(card_id="a1-029")         # Petilil bench[1]

    state.players[1].active = active_slot
    state.players[1].bench[0] = bench0
    state.players[1].bench[1] = bench1

    ctx = _make_ctx(state, acting=0)
    effect = Effect(name="switch_opponent_active", params={})
    new_state = resolve_effect(ctx, effect)

    opp = new_state.players[1]
    # The new active should be one of the bench Pokemon
    bench_ids = {"a1-005", "a1-029"}
    assert opp.active.card_id in bench_ids

    # Old active should be on the bench somewhere
    all_bench_ids = {s.card_id for s in opp.bench if s is not None}
    assert "a1-001" in all_bench_ids

    # Total Pokemon count is preserved (3 = 1 active + 2 bench)
    total = (1 if opp.active else 0) + sum(1 for s in opp.bench if s is not None)
    assert total == 3


def test_switch_opponent_active_acting_player_unchanged():
    """The acting player's board is not modified by switch_opponent_active."""
    state = GameState()
    state.rng = random.Random(0)

    # Player 0 (acting) has a Pokemon
    state.players[0].active = _make_slot(card_id="a1-037")  # Vulpix
    # Player 1 (opponent) has an active + bench
    state.players[1].active = _make_slot(card_id="a1-001")
    state.players[1].bench[0] = _make_slot(card_id="a1-005")

    ctx = _make_ctx(state, acting=0)
    effect = Effect(name="switch_opponent_active", params={})
    new_state = resolve_effect(ctx, effect)

    # Player 0's board unchanged
    assert new_state.players[0].active.card_id == "a1-037"
