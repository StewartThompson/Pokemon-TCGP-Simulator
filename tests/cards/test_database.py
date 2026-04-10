"""Tests for the card database."""
import pytest
from ptcgp.cards.database import (
    clear_db, register_card, get_card, get_card_or_none,
    get_all_cards, load_defaults, is_loaded,
)
from ptcgp.cards.card import Card
from ptcgp.cards.types import CardKind


@pytest.fixture(autouse=True)
def fresh_db():
    clear_db()
    yield
    clear_db()


def _make_card(cid="test-001", name="TestMon") -> Card:
    from ptcgp.cards.types import Stage, Element
    from ptcgp.cards.attack import Attack
    return Card(
        id=cid, name=name, kind=CardKind.POKEMON,
        stage=Stage.BASIC, element=Element.GRASS, hp=60,
    )


def test_register_and_get():
    card = _make_card()
    register_card(card)
    assert get_card("test-001") is card


def test_get_missing_raises():
    with pytest.raises(KeyError):
        get_card("nonexistent-999")


def test_get_card_or_none_missing():
    assert get_card_or_none("nonexistent-999") is None


def test_clear_db():
    register_card(_make_card())
    clear_db()
    assert not is_loaded()
    assert get_card_or_none("test-001") is None


def test_get_all_cards_returns_copy():
    card = _make_card()
    register_card(card)
    snapshot = get_all_cards()
    assert "test-001" in snapshot
    snapshot["injected"] = card  # mutating snapshot should not affect DB
    assert get_card_or_none("injected") is None


def test_load_defaults():
    load_defaults()
    assert is_loaded()
    bulb = get_card("a1-001")
    assert bulb.name == "Bulbasaur"


def test_load_defaults_count():
    load_defaults()
    cards = get_all_cards()
    # a1-genetic-apex has 22 cards; other sets add more
    assert len(cards) >= 22
