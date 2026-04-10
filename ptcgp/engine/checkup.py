"""Between-turns checkup — applies status effects to the current player's active."""
from __future__ import annotations

from ptcgp.engine.constants import BURN_DAMAGE, POISON_DAMAGE
from ptcgp.engine.state import GameState, StatusEffect


def resolve_between_turns(state: GameState) -> GameState:
    """Apply status-effect damage/cures to the current player's Active Pokemon.

    Called BEFORE end_turn so ``state.current`` refers to the player who just
    finished their turn.

    Order of operations:
    1. POISONED  — deal POISON_DAMAGE
    2. BURNED    — deal BURN_DAMAGE; then coin-flip to possibly cure
    3. PARALYZED — auto-cure (no damage)
    4. ASLEEP    — coin-flip to possibly cure (no damage)
    5. CONFUSED  — no checkup effect (only affects attacks)

    HP is clamped to 0 if status damage would take it below. Any resulting
    KO is handled one level up (``resolve_status_kos``) because this function
    must stay usable with minimal test fixtures that have no real card data.
    """
    state = state.copy()

    player = state.current
    active = player.active
    if active is None:
        return state

    effects = active.status_effects

    if StatusEffect.POISONED in effects:
        active.current_hp -= POISON_DAMAGE

    if StatusEffect.BURNED in effects:
        active.current_hp -= BURN_DAMAGE
        if state.rng.random() < 0.5:  # heads → cure
            effects.discard(StatusEffect.BURNED)

    if StatusEffect.PARALYZED in effects:
        effects.discard(StatusEffect.PARALYZED)

    if StatusEffect.ASLEEP in effects:
        if state.rng.random() < 0.5:  # heads → cure
            effects.discard(StatusEffect.ASLEEP)

    if active.current_hp <= 0:
        active.current_hp = 0

    return state
