"""Tests for energy.py — attaching energy from the Energy Zone."""
import pytest
from ptcgp.cards.database import load_defaults
from ptcgp.cards.types import Element
from ptcgp.engine.actions import SlotRef
from ptcgp.engine.energy import attach_energy
from ptcgp.engine.state import GameState, PlayerState, PokemonSlot


def setup_module():
    load_defaults()


def make_state_with_active(
    card_id: str = "a1-001",
    energy_available: Element | None = Element.GRASS,
    has_attached_energy: bool = False,
) -> GameState:
    """Build a minimal state with an active Pokemon and optional energy available."""
    from ptcgp.cards.database import get_card
    card = get_card(card_id)
    slot = PokemonSlot(card_id=card_id, current_hp=card.hp, max_hp=card.hp)
    player = PlayerState(
        active=slot,
        energy_available=energy_available,
        has_attached_energy=has_attached_energy,
        energy_types=[Element.GRASS],
    )
    state = GameState(players=[player, PlayerState()])
    return state


def make_state_with_bench(
    card_id: str = "a1-001",
    bench_slot: int = 0,
    energy_available: Element | None = Element.GRASS,
) -> GameState:
    """Build a minimal state with a bench Pokemon."""
    from ptcgp.cards.database import get_card
    card = get_card(card_id)
    slot = PokemonSlot(card_id=card_id, current_hp=card.hp, max_hp=card.hp)
    bench = [None, None, None]
    bench[bench_slot] = slot
    player = PlayerState(
        bench=bench,
        energy_available=energy_available,
        energy_types=[Element.GRASS],
    )
    state = GameState(players=[player, PlayerState()])
    return state


# --- attach_energy to active ---

def test_attach_energy_adds_to_slot():
    """Energy is added to the target slot's attached_energy."""
    state = make_state_with_active(energy_available=Element.GRASS)
    target = SlotRef.active(player=0)
    new_state = attach_energy(state, target)
    slot = new_state.players[0].active
    assert slot.attached_energy.get(Element.GRASS, 0) == 1


def test_attach_energy_clears_available():
    """energy_available is set to None after attaching."""
    state = make_state_with_active(energy_available=Element.GRASS)
    target = SlotRef.active(player=0)
    new_state = attach_energy(state, target)
    assert new_state.players[0].energy_available is None


def test_attach_energy_sets_flag():
    """has_attached_energy is True after attaching."""
    state = make_state_with_active(energy_available=Element.GRASS)
    target = SlotRef.active(player=0)
    new_state = attach_energy(state, target)
    assert new_state.players[0].has_attached_energy is True


def test_attach_energy_to_bench():
    """Energy can be attached to a bench Pokemon."""
    state = make_state_with_bench(bench_slot=1, energy_available=Element.WATER)
    # Temporarily update energy type
    state.players[0].energy_available = Element.WATER
    target = SlotRef.bench(player=0, index=1)
    new_state = attach_energy(state, target)
    slot = new_state.players[0].bench[1]
    assert slot.attached_energy.get(Element.WATER, 0) == 1


def test_attach_energy_accumulates():
    """Multiple energy can accumulate across different turns."""
    state = make_state_with_active(energy_available=Element.GRASS)
    target = SlotRef.active(player=0)
    # First attach
    new_state = attach_energy(state, target)
    # Reset flag to simulate next turn
    new_state.players[0].has_attached_energy = False
    new_state.players[0].energy_available = Element.GRASS
    # Second attach
    new_state2 = attach_energy(new_state, target)
    assert new_state2.players[0].active.attached_energy.get(Element.GRASS, 0) == 2


def test_attach_energy_fails_if_none_available():
    """Raises ValueError if no energy is available."""
    state = make_state_with_active(energy_available=None)
    target = SlotRef.active(player=0)
    with pytest.raises(ValueError, match="No energy available"):
        attach_energy(state, target)


def test_attach_energy_fails_if_already_attached():
    """Raises ValueError if energy already attached this turn."""
    state = make_state_with_active(
        energy_available=Element.GRASS,
        has_attached_energy=True,
    )
    target = SlotRef.active(player=0)
    with pytest.raises(ValueError, match="Already attached energy"):
        attach_energy(state, target)


def test_attach_energy_does_not_mutate_original():
    """Original state is unchanged (copy-on-write)."""
    state = make_state_with_active(energy_available=Element.GRASS)
    target = SlotRef.active(player=0)
    new_state = attach_energy(state, target)
    # Original should still have energy available
    assert state.players[0].energy_available == Element.GRASS
    assert state.players[0].has_attached_energy is False
    assert state.players[0].active.attached_energy == {}
