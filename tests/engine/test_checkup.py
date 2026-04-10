"""Tests for ptcgp/engine/checkup.py — resolve_between_turns."""
from __future__ import annotations

import random

import pytest

from ptcgp.engine.checkup import resolve_between_turns
from ptcgp.engine.constants import BURN_DAMAGE, POISON_DAMAGE
from ptcgp.engine.state import GamePhase, GameState, PlayerState, PokemonSlot, StatusEffect


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_state_with_active(
    hp: int = 100,
    effects: set[StatusEffect] | None = None,
    seed: int | None = None,
) -> GameState:
    """Create a minimal GameState where player 0 is current with an Active Pokemon."""
    state = GameState()
    if seed is not None:
        state.rng.seed(seed)
    state.current_player = 0
    state.phase = GamePhase.MAIN

    slot = PokemonSlot(card_id="test-mon", current_hp=hp, max_hp=hp)
    if effects:
        slot.status_effects = set(effects)

    state.players[0].active = slot
    return state


def _seed_that_gives(target_bool: bool, n_flips: int = 1, attempts: int = 1000) -> int:
    """Find a seed where the first `n_flips` coin flips all equal `target_bool`.

    Returns a seed such that rng.random() < 0.5 == target_bool for each flip.
    """
    for seed in range(attempts):
        rng = random.Random(seed)
        results = [rng.random() < 0.5 for _ in range(n_flips)]
        if all(r == target_bool for r in results):
            return seed
    raise RuntimeError(f"Could not find seed giving {n_flips} {'heads' if target_bool else 'tails'}")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_poison_deals_damage():
    """Poisoned active loses POISON_DAMAGE HP."""
    state = _make_state_with_active(hp=100, effects={StatusEffect.POISONED})
    state = resolve_between_turns(state)
    assert state.players[0].active.current_hp == 100 - POISON_DAMAGE


def test_burn_deals_damage():
    """Burned active loses BURN_DAMAGE HP."""
    # Use a seed that gives tails so burn is NOT cured (we just check damage)
    tails_seed = _seed_that_gives(False)
    state = _make_state_with_active(hp=100, effects={StatusEffect.BURNED}, seed=tails_seed)
    state = resolve_between_turns(state)
    assert state.players[0].active.current_hp == 100 - BURN_DAMAGE
    # BURNED persists on tails
    assert StatusEffect.BURNED in state.players[0].active.status_effects


def test_burn_can_cure_on_heads():
    """With a seed giving heads, BURNED is removed after checkup."""
    heads_seed = _seed_that_gives(True)
    state = _make_state_with_active(hp=100, effects={StatusEffect.BURNED}, seed=heads_seed)
    state = resolve_between_turns(state)
    # Damage was dealt
    assert state.players[0].active.current_hp == 100 - BURN_DAMAGE
    # Status cured
    assert StatusEffect.BURNED not in state.players[0].active.status_effects


def test_paralysis_auto_cures():
    """PARALYZED is always removed during checkup (no coin flip)."""
    state = _make_state_with_active(hp=100, effects={StatusEffect.PARALYZED})
    state = resolve_between_turns(state)
    assert StatusEffect.PARALYZED not in state.players[0].active.status_effects
    # No damage from paralysis
    assert state.players[0].active.current_hp == 100


def test_sleep_cured_on_heads():
    """With a seed giving heads, ASLEEP is removed."""
    heads_seed = _seed_that_gives(True)
    state = _make_state_with_active(hp=100, effects={StatusEffect.ASLEEP}, seed=heads_seed)
    state = resolve_between_turns(state)
    assert StatusEffect.ASLEEP not in state.players[0].active.status_effects
    assert state.players[0].active.current_hp == 100  # no damage from sleep


def test_sleep_persists_on_tails():
    """With a seed giving tails, ASLEEP remains."""
    tails_seed = _seed_that_gives(False)
    state = _make_state_with_active(hp=100, effects={StatusEffect.ASLEEP}, seed=tails_seed)
    state = resolve_between_turns(state)
    assert StatusEffect.ASLEEP in state.players[0].active.status_effects
    assert state.players[0].active.current_hp == 100  # no damage from sleep


def test_poison_and_burn_both_apply():
    """Both POISONED and BURNED deal damage in same checkup."""
    # Use tails seed so BURNED stays (only one flip needed for burn)
    tails_seed = _seed_that_gives(False)
    state = _make_state_with_active(
        hp=100,
        effects={StatusEffect.POISONED, StatusEffect.BURNED},
        seed=tails_seed,
    )
    state = resolve_between_turns(state)
    assert state.players[0].active.current_hp == 100 - POISON_DAMAGE - BURN_DAMAGE


def test_confused_no_checkup_damage():
    """CONFUSED active takes no damage during checkup."""
    state = _make_state_with_active(hp=100, effects={StatusEffect.CONFUSED})
    state = resolve_between_turns(state)
    assert state.players[0].active.current_hp == 100
    # Status still present (confused doesn't auto-cure during checkup)
    assert StatusEffect.CONFUSED in state.players[0].active.status_effects


def test_no_active_no_crash():
    """resolve_between_turns should not crash when there is no active Pokemon."""
    state = GameState()
    state.current_player = 0
    state.players[0].active = None
    # Should just return without error
    result = resolve_between_turns(state)
    assert result.players[0].active is None


def test_status_hp_clamped_to_zero_on_ko():
    """If status damage would bring HP below 0, it is clamped to 0."""
    state = _make_state_with_active(hp=5, effects={StatusEffect.POISONED})
    state = resolve_between_turns(state)
    assert state.players[0].active.current_hp == 0


def test_poison_damage_exact():
    """POISON_DAMAGE is exactly 10."""
    state = _make_state_with_active(hp=50, effects={StatusEffect.POISONED})
    state = resolve_between_turns(state)
    assert state.players[0].active.current_hp == 40


def test_burn_damage_exact():
    """BURN_DAMAGE is exactly 20."""
    tails_seed = _seed_that_gives(False)
    state = _make_state_with_active(hp=50, effects={StatusEffect.BURNED}, seed=tails_seed)
    state = resolve_between_turns(state)
    assert state.players[0].active.current_hp == 30
