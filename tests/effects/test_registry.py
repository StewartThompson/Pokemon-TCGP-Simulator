"""Tests for ptcgp.effects.registry — effect registration and dispatch."""
import warnings
import pytest

from ptcgp.effects.base import Effect, UnknownEffect
from ptcgp.effects.registry import (
    EffectContext,
    register_effect,
    resolve_effect,
    is_effect_implemented,
    list_registered_effects,
    _REGISTRY,
)
from ptcgp.engine.state import GameState


def _make_ctx(state: GameState = None) -> EffectContext:
    """Build a minimal EffectContext for testing."""
    if state is None:
        state = GameState()
    return EffectContext(
        state=state,
        acting_player=0,
        source_ref=None,
        target_ref=None,
    )


def test_register_and_resolve():
    """Registering a handler and calling resolve_effect dispatches to it."""
    called_with = {}

    @register_effect("_test_handler_xyz")
    def _test_handler(ctx, **kwargs):
        called_with["ctx"] = ctx
        called_with["kwargs"] = kwargs
        return ctx.state

    state = GameState()
    ctx = _make_ctx(state)
    effect = Effect(name="_test_handler_xyz", params={"amount": 42})

    result = resolve_effect(ctx, effect)

    assert result is state
    assert called_with["ctx"] is ctx
    assert called_with["kwargs"] == {"amount": 42}

    # Cleanup to avoid polluting other tests
    _REGISTRY.pop("_test_handler_xyz", None)


def test_unknown_effect_returns_state():
    """UnknownEffect should return the original state unchanged, with a warning."""
    state = GameState()
    ctx = _make_ctx(state)
    effect = UnknownEffect(name="unknown", raw_text="some unrecognized text")

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = resolve_effect(ctx, effect)

    assert result is state
    assert len(w) == 1
    assert "some unrecognized text" in str(w[0].message)


def test_unregistered_name_returns_state():
    """Effect with an unregistered name returns state unchanged, with a warning."""
    state = GameState()
    ctx = _make_ctx(state)
    effect = Effect(name="nonexistent_effect_zzz", params={})

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = resolve_effect(ctx, effect)

    assert result is state
    assert len(w) == 1
    assert "nonexistent_effect_zzz" in str(w[0].message)


def test_is_effect_implemented_registered():
    """is_effect_implemented returns True for a registered effect."""
    @register_effect("_test_implemented_check")
    def _handler(ctx):
        return ctx.state

    assert is_effect_implemented("_test_implemented_check") is True

    # Cleanup
    _REGISTRY.pop("_test_implemented_check", None)


def test_is_effect_implemented_unknown():
    """is_effect_implemented returns False for an unknown effect name."""
    assert is_effect_implemented("totally_nonexistent_effect_abc") is False


def test_list_registered():
    """list_registered_effects returns a list of registered effect names."""
    @register_effect("_test_list_check")
    def _handler(ctx):
        return ctx.state

    names = list_registered_effects()
    assert isinstance(names, list)
    assert "_test_list_check" in names

    # Cleanup
    _REGISTRY.pop("_test_list_check", None)


def test_effect_context_defaults():
    """EffectContext has expected default values."""
    state = GameState()
    ctx = EffectContext(
        state=state,
        acting_player=1,
        source_ref=None,
        target_ref=None,
    )
    assert ctx.amount == 0
    assert ctx.extra == {}
    assert ctx.acting_player == 1
