"""Retreat logic: swap active Pokemon with a bench Pokemon."""
from __future__ import annotations

from ptcgp.cards.database import get_card
from ptcgp.engine.state import GameState, StatusEffect


def retreat(state: GameState, bench_slot: int) -> GameState:
    """Swap Active Pokemon with a Bench Pokemon."""
    player = state.players[state.current_player]

    if player.has_retreated:
        raise ValueError("Already retreated this turn")
    if player.active is None:
        raise ValueError("No active Pokemon to retreat")

    # Cannot retreat if Paralyzed or Asleep
    if StatusEffect.PARALYZED in player.active.status_effects:
        raise ValueError("Active Pokemon is Paralyzed and cannot retreat")
    if StatusEffect.ASLEEP in player.active.status_effects:
        raise ValueError("Active Pokemon is Asleep and cannot retreat")

    if bench_slot < 0 or bench_slot >= len(player.bench):
        raise ValueError(f"Invalid bench_slot {bench_slot}")
    if player.bench[bench_slot] is None:
        raise ValueError(f"No Pokemon in bench slot {bench_slot}")

    active_card = get_card(player.active.card_id)
    retreat_cost = max(0, active_card.retreat_cost + player.retreat_cost_modifier)

    # Cannot retreat if the active Pokemon was temporarily blocked from retreating.
    if player.active.cant_retreat_next_turn:
        raise ValueError("Active Pokemon cannot retreat this turn")

    # Check enough total energy to pay retreat cost
    total_energy = player.active.total_energy()
    if total_energy < retreat_cost:
        raise ValueError(
            f"Not enough energy to retreat: need {retreat_cost}, have {total_energy}"
        )

    # Apply copy-on-write
    state = state.copy()
    player = state.players[state.current_player]

    # Randomly discard 'retreat_cost' energy tokens from active
    if retreat_cost > 0:
        # Build flat list of energy tokens
        energy_list = []
        for element, count in player.active.attached_energy.items():
            energy_list.extend([element] * count)

        # Use state RNG to sample which tokens to discard
        discarded = state.rng.sample(energy_list, retreat_cost)

        # Update attached_energy
        new_energy: dict = dict(player.active.attached_energy)
        for token in discarded:
            new_energy[token] -= 1
            if new_energy[token] == 0:
                del new_energy[token]
        player.active.attached_energy = new_energy

    # Clear status effects from retreating Pokemon
    player.active.status_effects = set()

    # Swap active <-> bench[bench_slot]
    old_active = player.active
    player.active = player.bench[bench_slot]
    player.bench[bench_slot] = old_active

    player.has_retreated = True

    return state
