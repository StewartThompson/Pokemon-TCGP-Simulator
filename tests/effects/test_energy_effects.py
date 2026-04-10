"""Tests for ptcgp.effects.energy_effects — attach_energy_zone_self, attach_energy_zone_bench, discard_energy_self."""
import pytest

from ptcgp.cards.database import load_defaults
from ptcgp.cards.types import Element
from ptcgp.engine.state import GameState, PokemonSlot
from ptcgp.engine.actions import SlotRef
from ptcgp.effects.registry import EffectContext, resolve_effect
from ptcgp.effects.base import Effect
import ptcgp.effects  # trigger registration


@pytest.fixture(autouse=True, scope="session")
def init_db():
    load_defaults()


def _make_slot(card_id="a1-001", current_hp=70, max_hp=70, energy=None) -> PokemonSlot:
    slot = PokemonSlot(card_id=card_id, current_hp=current_hp, max_hp=max_hp)
    if energy:
        slot.attached_energy = dict(energy)
    return slot


def _make_ctx(state, acting=0, source=None, target=None) -> EffectContext:
    return EffectContext(
        state=state,
        acting_player=acting,
        source_ref=source,
        target_ref=target,
    )


# ---------------------------------------------------------------------------
# attach_energy_zone_self
# ---------------------------------------------------------------------------

def test_attach_energy_zone_self():
    """attach_energy_zone_self attaches N Fire energy to the source Pokemon."""
    slot = _make_slot(card_id="a1-230")  # Charmander
    state = GameState()
    state.players[0].active = slot
    source = SlotRef.active(0)

    ctx = _make_ctx(state, source=source)
    effect = Effect(name="attach_energy_zone_self", params={"count": 3, "energy_type": "Fire"})
    new_state = resolve_effect(ctx, effect)

    attached = new_state.players[0].active.attached_energy
    assert attached.get(Element.FIRE, 0) == 3


def test_attach_energy_zone_self_stacks():
    """attach_energy_zone_self stacks on top of existing energy."""
    slot = _make_slot(card_id="a1-230", energy={Element.FIRE: 1})
    state = GameState()
    state.players[0].active = slot
    source = SlotRef.active(0)

    ctx = _make_ctx(state, source=source)
    effect = Effect(name="attach_energy_zone_self", params={"count": 2, "energy_type": "Fire"})
    new_state = resolve_effect(ctx, effect)

    assert new_state.players[0].active.attached_energy[Element.FIRE] == 3


def test_attach_energy_zone_self_no_source():
    """attach_energy_zone_self with source_ref=None is a no-op."""
    state = GameState()
    ctx = _make_ctx(state, source=None)
    effect = Effect(name="attach_energy_zone_self", params={"count": 3, "energy_type": "Fire"})
    new_state = resolve_effect(ctx, effect)
    # State unchanged
    assert new_state.players[0].active is None


# ---------------------------------------------------------------------------
# attach_energy_zone_bench
# ---------------------------------------------------------------------------

def test_attach_energy_zone_bench():
    """attach_energy_zone_bench attaches Grass energy to a bench target."""
    bench_slot = _make_slot(card_id="a1-001")  # Bulbasaur (Grass)
    state = GameState()
    state.players[0].bench[0] = bench_slot
    target = SlotRef.bench(0, 0)

    ctx = _make_ctx(state, target=target)
    effect = Effect(name="attach_energy_zone_bench", params={"energy_type": "Grass", "target_type": "Grass"})
    new_state = resolve_effect(ctx, effect)

    assert new_state.players[0].bench[0].attached_energy.get(Element.GRASS, 0) == 1


def test_attach_energy_zone_bench_stacks():
    """attach_energy_zone_bench stacks on existing energy."""
    bench_slot = _make_slot(card_id="a1-001", energy={Element.GRASS: 2})
    state = GameState()
    state.players[0].bench[1] = bench_slot
    target = SlotRef.bench(0, 1)

    ctx = _make_ctx(state, target=target)
    effect = Effect(name="attach_energy_zone_bench", params={"energy_type": "Grass", "target_type": "Grass"})
    new_state = resolve_effect(ctx, effect)

    assert new_state.players[0].bench[1].attached_energy[Element.GRASS] == 3


def test_attach_energy_zone_bench_no_target():
    """attach_energy_zone_bench with target_ref=None is a no-op."""
    state = GameState()
    ctx = _make_ctx(state, target=None)
    effect = Effect(name="attach_energy_zone_bench", params={"energy_type": "Grass", "target_type": "Grass"})
    new_state = resolve_effect(ctx, effect)
    assert new_state is ctx.state or new_state.players[0].bench == state.players[0].bench


# ---------------------------------------------------------------------------
# discard_energy_self
# ---------------------------------------------------------------------------

def test_discard_energy_self_removes_one():
    """discard_energy_self removes 1 fire energy from the source Pokemon."""
    slot = _make_slot(card_id="a1-230", energy={Element.FIRE: 2})
    state = GameState()
    state.players[0].active = slot
    source = SlotRef.active(0)

    ctx = _make_ctx(state, source=source)
    effect = Effect(name="discard_energy_self", params={"energy_type": "Fire"})
    new_state = resolve_effect(ctx, effect)

    assert new_state.players[0].active.attached_energy.get(Element.FIRE, 0) == 1


def test_discard_energy_self_removes_key_when_zero():
    """discard_energy_self removes the element key when count reaches 0."""
    slot = _make_slot(card_id="a1-230", energy={Element.FIRE: 1})
    state = GameState()
    state.players[0].active = slot
    source = SlotRef.active(0)

    ctx = _make_ctx(state, source=source)
    effect = Effect(name="discard_energy_self", params={"energy_type": "Fire"})
    new_state = resolve_effect(ctx, effect)

    # Key should be removed entirely
    assert Element.FIRE not in new_state.players[0].active.attached_energy


def test_discard_energy_self_not_present():
    """discard_energy_self is a no-op when the energy type is not attached."""
    slot = _make_slot(card_id="a1-230", energy={Element.GRASS: 1})
    state = GameState()
    state.players[0].active = slot
    source = SlotRef.active(0)

    ctx = _make_ctx(state, source=source)
    effect = Effect(name="discard_energy_self", params={"energy_type": "Fire"})
    new_state = resolve_effect(ctx, effect)

    # State unchanged — Grass still present, Fire never added
    assert new_state.players[0].active.attached_energy.get(Element.GRASS, 0) == 1
    assert Element.FIRE not in new_state.players[0].active.attached_energy


def test_discard_energy_self_no_source():
    """discard_energy_self with source_ref=None is a no-op."""
    state = GameState()
    ctx = _make_ctx(state, source=None)
    effect = Effect(name="discard_energy_self", params={"energy_type": "Fire"})
    new_state = resolve_effect(ctx, effect)
    assert new_state.players[0].active is None
