"""Utility functions for resolving and updating PokemonSlot references in GameState."""
from __future__ import annotations
from typing import Callable, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ptcgp.engine.state import GameState, PokemonSlot
    from ptcgp.engine.actions import SlotRef


def get_slot(state: "GameState", ref: "SlotRef") -> Optional["PokemonSlot"]:
    """Resolve a SlotRef to a PokemonSlot (or None if slot is empty)."""
    player = state.players[ref.player]
    if ref.slot == -1:
        return player.active
    return player.bench[ref.slot]


def set_slot(state: "GameState", ref: "SlotRef", new_slot: Optional["PokemonSlot"]) -> "GameState":
    """Return a new state copy with the given slot replaced by new_slot."""
    state = state.copy()
    player = state.players[ref.player]
    if ref.slot == -1:
        player.active = new_slot
    else:
        player.bench[ref.slot] = new_slot
    return state


def mutate_slot(
    state: "GameState",
    ref: "SlotRef",
    mutator: Callable[["PokemonSlot"], None],
) -> "GameState":
    """Return a new state with ``mutator`` applied to a copy of the slot at ``ref``.

    If the slot is empty, returns state unchanged. The mutator must edit the
    slot in place; its return value is ignored.
    """
    slot = get_slot(state, ref)
    if slot is None:
        return state
    new_slot = slot.copy()
    mutator(new_slot)
    return set_slot(state, ref, new_slot)
