"""Tests for ptcgp/engine/status.py — status effect application."""
from __future__ import annotations

import pytest

from ptcgp.cards.card import Card
from ptcgp.cards.database import clear_db, register_card
from ptcgp.cards.types import CardKind, Element, Stage
from ptcgp.engine.actions import SlotRef
from ptcgp.engine.state import GameState, GamePhase, PlayerState, PokemonSlot, StatusEffect
from ptcgp.engine.status import apply_status


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_pokemon(cid: str, hp: int = 70) -> Card:
    return Card(
        id=cid,
        name=f"TestMon-{cid}",
        kind=CardKind.POKEMON,
        stage=Stage.BASIC,
        element=Element.FIRE,
        hp=hp,
    )


def _make_state_with_bench() -> GameState:
    """Build a state where player 0 has an active + one bench Pokemon."""
    active_slot = PokemonSlot(card_id="active-mon", current_hp=70, max_hp=70)
    bench_slot = PokemonSlot(card_id="bench-mon", current_hp=60, max_hp=60)

    p0 = PlayerState(
        active=active_slot,
        bench=[bench_slot, None, None],
    )
    p1 = PlayerState(
        active=PokemonSlot(card_id="opp-active", current_hp=70, max_hp=70),
    )

    return GameState(
        players=[p0, p1],
        current_player=0,
        phase=GamePhase.MAIN,
    )


@pytest.fixture(autouse=True)
def fresh_db():
    clear_db()
    register_card(_make_pokemon("active-mon"))
    register_card(_make_pokemon("bench-mon", hp=60))
    register_card(_make_pokemon("opp-active"))
    yield
    clear_db()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_apply_poisoned():
    """StatusEffect.POISONED should be in slot.status_effects after apply_status."""
    state = _make_state_with_bench()
    target = SlotRef.active(0)

    result = apply_status(state, target, StatusEffect.POISONED)

    assert StatusEffect.POISONED in result.players[0].active.status_effects


def test_apply_burned():
    """StatusEffect.BURNED should be in slot.status_effects after apply_status."""
    state = _make_state_with_bench()
    target = SlotRef.active(0)

    result = apply_status(state, target, StatusEffect.BURNED)

    assert StatusEffect.BURNED in result.players[0].active.status_effects


def test_apply_paralyzed():
    """StatusEffect.PARALYZED should be in slot.status_effects after apply_status."""
    state = _make_state_with_bench()
    target = SlotRef.active(0)

    result = apply_status(state, target, StatusEffect.PARALYZED)

    assert StatusEffect.PARALYZED in result.players[0].active.status_effects


def test_apply_asleep():
    """StatusEffect.ASLEEP should be in slot.status_effects after apply_status."""
    state = _make_state_with_bench()
    target = SlotRef.active(0)

    result = apply_status(state, target, StatusEffect.ASLEEP)

    assert StatusEffect.ASLEEP in result.players[0].active.status_effects


def test_apply_confused():
    """StatusEffect.CONFUSED should be in slot.status_effects after apply_status."""
    state = _make_state_with_bench()
    target = SlotRef.active(0)

    result = apply_status(state, target, StatusEffect.CONFUSED)

    assert StatusEffect.CONFUSED in result.players[0].active.status_effects


def test_statuses_stack():
    """All 5 statuses can coexist on the same Pokemon."""
    state = _make_state_with_bench()
    target = SlotRef.active(0)

    state = apply_status(state, target, StatusEffect.POISONED)
    state = apply_status(state, target, StatusEffect.BURNED)
    state = apply_status(state, target, StatusEffect.PARALYZED)
    state = apply_status(state, target, StatusEffect.ASLEEP)
    state = apply_status(state, target, StatusEffect.CONFUSED)

    slot = state.players[0].active
    assert StatusEffect.POISONED in slot.status_effects
    assert StatusEffect.BURNED in slot.status_effects
    assert StatusEffect.PARALYZED in slot.status_effects
    assert StatusEffect.ASLEEP in slot.status_effects
    assert StatusEffect.CONFUSED in slot.status_effects
    assert len(slot.status_effects) == 5


def test_status_only_on_active():
    """Applying a status to a bench slot raises ValueError."""
    state = _make_state_with_bench()
    bench_target = SlotRef.bench(0, 0)

    with pytest.raises(ValueError, match="Active Pokemon"):
        apply_status(state, bench_target, StatusEffect.POISONED)


def test_apply_paralyzed_blocks_attack_flag():
    """PARALYZED is in status_effects set (attack blocking tested in legal_actions)."""
    state = _make_state_with_bench()
    target = SlotRef.active(0)

    result = apply_status(state, target, StatusEffect.PARALYZED)

    assert StatusEffect.PARALYZED in result.players[0].active.status_effects


def test_apply_status_does_not_mutate_original():
    """apply_status is copy-on-write; original state is unchanged."""
    state = _make_state_with_bench()
    target = SlotRef.active(0)
    original_effects = set(state.players[0].active.status_effects)

    apply_status(state, target, StatusEffect.POISONED)

    assert state.players[0].active.status_effects == original_effects


def test_apply_status_opponent_active():
    """Status can be applied to opponent's active Pokemon."""
    state = _make_state_with_bench()
    opp_active = SlotRef.active(1)

    result = apply_status(state, opp_active, StatusEffect.POISONED)

    assert StatusEffect.POISONED in result.players[1].active.status_effects
