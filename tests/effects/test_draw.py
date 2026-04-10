"""Tests for ptcgp.effects.draw — draw_cards, draw_basic_pokemon."""
import pytest

from ptcgp.cards.database import load_defaults
from ptcgp.engine.state import GameState, PlayerState, PokemonSlot
from ptcgp.effects.registry import EffectContext, resolve_effect
from ptcgp.effects.base import Effect
import ptcgp.effects  # trigger registration


@pytest.fixture(autouse=True, scope="session")
def init_db():
    load_defaults()


def _make_ctx(state, acting=0) -> EffectContext:
    return EffectContext(
        state=state,
        acting_player=acting,
        source_ref=None,
        target_ref=None,
    )


# ---------------------------------------------------------------------------
# draw_cards
# ---------------------------------------------------------------------------

def test_draw_cards_adds_to_hand():
    """draw_cards(count=2) adds 2 cards from deck to hand."""
    state = GameState()
    state.players[0].deck = ["a1-001", "a1-005", "a1-029"]
    state.players[0].hand = []

    ctx = _make_ctx(state)
    effect = Effect(name="draw_cards", params={"count": 2})
    new_state = resolve_effect(ctx, effect)

    assert len(new_state.players[0].hand) == 2
    assert new_state.players[0].hand == ["a1-001", "a1-005"]
    assert new_state.players[0].deck == ["a1-029"]


def test_draw_cards_partial():
    """If deck has fewer cards than count, draw only what's available — no error."""
    state = GameState()
    state.players[0].deck = ["a1-001"]
    state.players[0].hand = []

    ctx = _make_ctx(state)
    effect = Effect(name="draw_cards", params={"count": 5})
    new_state = resolve_effect(ctx, effect)

    assert new_state.players[0].hand == ["a1-001"]
    assert new_state.players[0].deck == []


def test_draw_cards_empty_deck():
    """draw_cards with an empty deck is a no-op."""
    state = GameState()
    state.players[0].deck = []
    state.players[0].hand = ["a1-001"]

    ctx = _make_ctx(state)
    effect = Effect(name="draw_cards", params={"count": 2})
    new_state = resolve_effect(ctx, effect)

    assert new_state.players[0].hand == ["a1-001"]
    assert new_state.players[0].deck == []


def test_draw_cards_exact_count():
    """draw_cards draws exactly the requested number when deck is large enough."""
    state = GameState()
    state.players[0].deck = ["a1-001", "a1-002", "a1-005", "a1-029"]
    state.players[0].hand = []

    ctx = _make_ctx(state)
    effect = Effect(name="draw_cards", params={"count": 3})
    new_state = resolve_effect(ctx, effect)

    assert len(new_state.players[0].hand) == 3
    assert len(new_state.players[0].deck) == 1


# ---------------------------------------------------------------------------
# draw_basic_pokemon
# ---------------------------------------------------------------------------

def test_draw_basic_pokemon_draws_basic():
    """draw_basic_pokemon draws a Basic Pokemon from the deck into hand."""
    state = GameState()
    # a1-001 = Bulbasaur (Basic Grass), a1-002 = Ivysaur (Stage 1)
    state.players[0].deck = ["a1-002", "a1-001", "a1-005"]  # Ivysaur (S1), Bulbasaur (B), Caterpie (B)
    state.players[0].hand = []
    state.rng.seed(42)

    ctx = _make_ctx(state)
    effect = Effect(name="draw_basic_pokemon", params={"count": 1})
    new_state = resolve_effect(ctx, effect)

    # Should have drawn exactly 1 Basic Pokemon
    assert len(new_state.players[0].hand) == 1
    drawn_id = new_state.players[0].hand[0]
    # The drawn card must be a Basic Pokemon
    from ptcgp.cards.database import get_card
    from ptcgp.cards.types import Stage
    drawn_card = get_card(drawn_id)
    assert drawn_card.is_pokemon
    assert drawn_card.stage == Stage.BASIC

    # Deck should have one fewer card
    assert len(new_state.players[0].deck) == 2


def test_draw_basic_pokemon_empty_deck():
    """draw_basic_pokemon with no basics in deck leaves hand unchanged."""
    state = GameState()
    # Only non-basic cards in deck
    state.players[0].deck = ["a1-002", "a1-004"]  # Ivysaur (S1), Venusaur ex (S2)
    state.players[0].hand = ["a1-001"]

    ctx = _make_ctx(state)
    effect = Effect(name="draw_basic_pokemon", params={"count": 1})
    new_state = resolve_effect(ctx, effect)

    assert new_state.players[0].hand == ["a1-001"]
    assert len(new_state.players[0].deck) == 2


def test_draw_basic_pokemon_no_deck():
    """draw_basic_pokemon with an empty deck is a no-op."""
    state = GameState()
    state.players[0].deck = []
    state.players[0].hand = ["a1-001"]

    ctx = _make_ctx(state)
    effect = Effect(name="draw_basic_pokemon", params={"count": 1})
    new_state = resolve_effect(ctx, effect)

    assert new_state.players[0].hand == ["a1-001"]


def test_draw_basic_pokemon_draws_multiple():
    """draw_basic_pokemon can draw more than one Basic Pokemon."""
    state = GameState()
    state.players[0].deck = ["a1-001", "a1-005", "a1-029"]  # all basics
    state.players[0].hand = []
    state.rng.seed(0)

    ctx = _make_ctx(state)
    effect = Effect(name="draw_basic_pokemon", params={"count": 2})
    new_state = resolve_effect(ctx, effect)

    assert len(new_state.players[0].hand) == 2
    assert len(new_state.players[0].deck) == 1
