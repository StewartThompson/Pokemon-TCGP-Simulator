"""Tests for ptcgp.effects.coin_flip — cant_attack_next_turn."""
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


def _make_slot(card_id="a1-037", current_hp=60, max_hp=60) -> PokemonSlot:
    """Make a Vulpix slot by default."""
    return PokemonSlot(card_id=card_id, current_hp=current_hp, max_hp=max_hp)


def _make_ctx_with_rng(seed, acting=0) -> tuple[EffectContext, GameState]:
    """Build a GameState with a seeded RNG and return (ctx, state)."""
    state = GameState()
    state.rng = random.Random(seed)
    # Player 0 is acting, player 1 has an active Pokemon
    state.players[1].active = _make_slot(card_id="a1-001")  # Bulbasaur

    ctx = EffectContext(
        state=state,
        acting_player=acting,
        source_ref=SlotRef.active(acting),
        target_ref=None,
    )
    return ctx, state


def _find_seed_for_result(target_heads: bool) -> int:
    """Find a seed where random.Random(seed).random() < 0.5 == target_heads."""
    for seed in range(1000):
        r = random.Random(seed)
        got_heads = r.random() < 0.5
        if got_heads == target_heads:
            return seed
    raise RuntimeError("Could not find appropriate seed")


# ---------------------------------------------------------------------------
# cant_attack_next_turn
# ---------------------------------------------------------------------------

def test_cant_attack_next_turn_on_heads():
    """When coin flip lands heads, opponent's active gets cant_attack_next_turn=True."""
    seed = _find_seed_for_result(target_heads=True)
    ctx, _ = _make_ctx_with_rng(seed)
    effect = Effect(name="cant_attack_next_turn", params={})
    new_state = resolve_effect(ctx, effect)
    assert new_state.players[1].active.cant_attack_next_turn is True


def test_cant_attack_next_turn_on_tails():
    """When coin flip lands tails, opponent's active is NOT affected."""
    seed = _find_seed_for_result(target_heads=False)
    ctx, _ = _make_ctx_with_rng(seed)
    effect = Effect(name="cant_attack_next_turn", params={})
    new_state = resolve_effect(ctx, effect)
    assert new_state.players[1].active.cant_attack_next_turn is False


def test_cant_attack_next_turn_no_opponent_active():
    """If opponent has no active Pokemon, effect is a no-op (no crash)."""
    state = GameState()
    state.rng = random.Random(_find_seed_for_result(target_heads=True))
    # Player 1 has no active
    state.players[1].active = None

    ctx = EffectContext(
        state=state,
        acting_player=0,
        source_ref=None,
        target_ref=None,
    )
    effect = Effect(name="cant_attack_next_turn", params={})
    new_state = resolve_effect(ctx, effect)
    assert new_state.players[1].active is None


def test_cant_attack_next_turn_does_not_affect_acting_player():
    """cant_attack_next_turn only affects the opponent, not the acting player."""
    seed = _find_seed_for_result(target_heads=True)
    ctx, state = _make_ctx_with_rng(seed, acting=0)
    state.players[0].active = _make_slot(card_id="a1-037")  # Vulpix

    effect = Effect(name="cant_attack_next_turn", params={})
    new_state = resolve_effect(ctx, effect)

    # Acting player (0) should NOT have cant_attack_next_turn set
    assert new_state.players[0].active.cant_attack_next_turn is False
    # Opponent (1) should have it set
    assert new_state.players[1].active.cant_attack_next_turn is True
