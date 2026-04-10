"""Tests for ptcgp.effects.heal — heal_self, heal_all_own, heal_target, heal_grass_target."""
import pytest

from ptcgp.cards.database import load_defaults
from ptcgp.engine.state import GameState, PlayerState, PokemonSlot
from ptcgp.engine.actions import SlotRef
from ptcgp.effects.registry import EffectContext, resolve_effect
from ptcgp.effects.base import Effect
import ptcgp.effects  # trigger registration


@pytest.fixture(autouse=True, scope="session")
def init_db():
    load_defaults()


def _make_slot(card_id="a1-001", current_hp=60, max_hp=70) -> PokemonSlot:
    return PokemonSlot(card_id=card_id, current_hp=current_hp, max_hp=max_hp)


def _make_state_with_active(slot: PokemonSlot, player_idx: int = 0) -> GameState:
    state = GameState()
    state.players[player_idx].active = slot
    return state


def _make_ctx(state, acting=0, source=None, target=None, extra=None) -> EffectContext:
    return EffectContext(
        state=state,
        acting_player=acting,
        source_ref=source,
        target_ref=target,
        extra=extra or {},
    )


# ---------------------------------------------------------------------------
# heal_self
# ---------------------------------------------------------------------------

def test_heal_self_increases_hp():
    slot = _make_slot(current_hp=40, max_hp=70)
    state = _make_state_with_active(slot)
    source = SlotRef.active(0)
    ctx = _make_ctx(state, source=source)
    effect = Effect(name="heal_self", params={"amount": 20})
    new_state = resolve_effect(ctx, effect)
    assert new_state.players[0].active.current_hp == 60


def test_heal_self_caps_at_max_hp():
    slot = _make_slot(current_hp=65, max_hp=70)
    state = _make_state_with_active(slot)
    source = SlotRef.active(0)
    ctx = _make_ctx(state, source=source)
    effect = Effect(name="heal_self", params={"amount": 30})
    new_state = resolve_effect(ctx, effect)
    assert new_state.players[0].active.current_hp == 70


def test_heal_self_no_source():
    """heal_self with source_ref=None does nothing."""
    slot = _make_slot(current_hp=40, max_hp=70)
    state = _make_state_with_active(slot)
    ctx = _make_ctx(state, source=None)
    effect = Effect(name="heal_self", params={"amount": 20})
    new_state = resolve_effect(ctx, effect)
    # State is unchanged
    assert new_state.players[0].active.current_hp == 40


def test_heal_self_already_at_max():
    """heal_self when already at max HP stays at max."""
    slot = _make_slot(current_hp=70, max_hp=70)
    state = _make_state_with_active(slot)
    source = SlotRef.active(0)
    ctx = _make_ctx(state, source=source)
    effect = Effect(name="heal_self", params={"amount": 10})
    new_state = resolve_effect(ctx, effect)
    assert new_state.players[0].active.current_hp == 70


# ---------------------------------------------------------------------------
# heal_all_own
# ---------------------------------------------------------------------------

def test_heal_all_own_heals_active_and_bench():
    """heal_all_own heals both active and bench Pokemon."""
    active = _make_slot(card_id="a1-001", current_hp=40, max_hp=70)
    bench0 = _make_slot(card_id="a1-005", current_hp=30, max_hp=50)
    bench1 = _make_slot(card_id="a1-029", current_hp=20, max_hp=60)

    state = GameState()
    state.players[0].active = active
    state.players[0].bench[0] = bench0
    state.players[0].bench[1] = bench1

    ctx = _make_ctx(state, acting=0)
    effect = Effect(name="heal_all_own", params={"amount": 20})
    new_state = resolve_effect(ctx, effect)

    assert new_state.players[0].active.current_hp == 60       # 40 + 20
    assert new_state.players[0].bench[0].current_hp == 50     # 30 + 20, capped at 50
    assert new_state.players[0].bench[1].current_hp == 40     # 20 + 20
    # Bench slot 2 is still None
    assert new_state.players[0].bench[2] is None


def test_heal_all_own_skips_empty_bench_slots():
    """heal_all_own skips None bench slots without error."""
    active = _make_slot(current_hp=40, max_hp=70)
    state = GameState()
    state.players[0].active = active
    # bench slots all None

    ctx = _make_ctx(state, acting=0)
    effect = Effect(name="heal_all_own", params={"amount": 10})
    new_state = resolve_effect(ctx, effect)

    assert new_state.players[0].active.current_hp == 50
    assert all(s is None for s in new_state.players[0].bench)


def test_heal_all_own_caps_bench_at_max():
    """heal_all_own won't exceed max_hp on bench Pokemon."""
    bench = _make_slot(current_hp=48, max_hp=50)
    state = GameState()
    state.players[0].bench[0] = bench

    ctx = _make_ctx(state, acting=0)
    effect = Effect(name="heal_all_own", params={"amount": 20})
    new_state = resolve_effect(ctx, effect)

    assert new_state.players[0].bench[0].current_hp == 50


# ---------------------------------------------------------------------------
# heal_target
# ---------------------------------------------------------------------------

def test_heal_target_heals_target():
    """heal_target heals the Pokemon referenced by ctx.target_ref."""
    slot = _make_slot(current_hp=30, max_hp=70)
    state = _make_state_with_active(slot)
    target = SlotRef.active(0)
    ctx = _make_ctx(state, target=target)
    effect = Effect(name="heal_target", params={"amount": 20})
    new_state = resolve_effect(ctx, effect)
    assert new_state.players[0].active.current_hp == 50


def test_heal_target_heals_bench_slot():
    """heal_target heals a bench Pokemon."""
    bench_slot = _make_slot(card_id="a1-005", current_hp=20, max_hp=50)
    state = GameState()
    state.players[0].bench[1] = bench_slot
    target = SlotRef.bench(0, 1)
    ctx = _make_ctx(state, target=target)
    effect = Effect(name="heal_target", params={"amount": 15})
    new_state = resolve_effect(ctx, effect)
    assert new_state.players[0].bench[1].current_hp == 35


def test_heal_target_caps_at_max():
    slot = _make_slot(current_hp=65, max_hp=70)
    state = _make_state_with_active(slot)
    target = SlotRef.active(0)
    ctx = _make_ctx(state, target=target)
    effect = Effect(name="heal_target", params={"amount": 50})
    new_state = resolve_effect(ctx, effect)
    assert new_state.players[0].active.current_hp == 70


def test_heal_target_auto_picks_most_damaged():
    """heal_target with no explicit target auto-picks the most-damaged own Pokemon."""
    slot = _make_slot(current_hp=30, max_hp=70)
    state = _make_state_with_active(slot)
    ctx = _make_ctx(state, target=None)
    effect = Effect(name="heal_target", params={"amount": 20})
    new_state = resolve_effect(ctx, effect)
    assert new_state.players[0].active.current_hp == 50


def test_heal_target_no_damaged_pokemon_noop():
    """heal_target with no target and no damaged Pokemon leaves state unchanged."""
    slot = _make_slot(current_hp=70, max_hp=70)
    state = _make_state_with_active(slot)
    ctx = _make_ctx(state, target=None)
    effect = Effect(name="heal_target", params={"amount": 20})
    new_state = resolve_effect(ctx, effect)
    assert new_state.players[0].active.current_hp == 70


# ---------------------------------------------------------------------------
# heal_grass_target
# ---------------------------------------------------------------------------

def test_heal_grass_target_heals():
    """heal_grass_target heals the target (same logic as heal_target)."""
    slot = _make_slot(card_id="a1-001", current_hp=30, max_hp=70)
    state = _make_state_with_active(slot)
    target = SlotRef.active(0)
    ctx = _make_ctx(state, target=target)
    effect = Effect(name="heal_grass_target", params={"amount": 50})
    new_state = resolve_effect(ctx, effect)
    assert new_state.players[0].active.current_hp == 70


def test_heal_grass_target_caps_at_max():
    """heal_grass_target caps at max_hp."""
    slot = _make_slot(card_id="a1-001", current_hp=60, max_hp=70)
    state = _make_state_with_active(slot)
    target = SlotRef.active(0)
    ctx = _make_ctx(state, target=target)
    effect = Effect(name="heal_grass_target", params={"amount": 50})
    new_state = resolve_effect(ctx, effect)
    assert new_state.players[0].active.current_hp == 70
