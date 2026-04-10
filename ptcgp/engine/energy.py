"""Energy attachment logic."""
from __future__ import annotations

from ptcgp.engine.actions import SlotRef
from ptcgp.engine.slot_utils import get_slot, set_slot
from ptcgp.engine.state import GameState


def attach_energy(state: GameState, target: SlotRef) -> GameState:
    """Attach the current turn's energy from Energy Zone to a Pokemon."""
    player = state.players[state.current_player]

    if player.energy_available is None:
        raise ValueError("No energy available to attach this turn")
    if player.has_attached_energy:
        raise ValueError("Already attached energy this turn")

    slot = get_slot(state, target)
    if slot is None:
        raise ValueError(f"No Pokemon in target slot {target}")

    energy_type = player.energy_available

    # Apply copy-on-write: get fresh state copy, then update slot
    state = state.copy()
    player = state.players[state.current_player]

    # Re-resolve slot from new state
    slot = get_slot(state, target)

    # Add energy to slot
    slot.attached_energy[energy_type] = slot.attached_energy.get(energy_type, 0) + 1

    # Update player flags
    player.has_attached_energy = True
    player.energy_available = None

    return state
