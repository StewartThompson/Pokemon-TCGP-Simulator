"""Tests for the card loader."""
import pytest
from pathlib import Path
from ptcgp.cards.loader import load_cards_from_json, load_card_from_dict
from ptcgp.cards.types import CardKind, Element, Stage, CostSymbol

ASSETS = Path(__file__).parent.parent.parent / "assets" / "cards"
A1_JSON = ASSETS / "a1-genetic-apex.json"


@pytest.fixture(scope="module")
def a1_cards():
    return load_cards_from_json(A1_JSON)


@pytest.fixture(scope="module")
def a1_by_id(a1_cards):
    return {c.id: c for c in a1_cards}


def test_load_count(a1_cards):
    # a1-genetic-apex.json contains the full Genetic Apex set.
    assert len(a1_cards) >= 200


def test_bulbasaur_fields(a1_by_id):
    bulb = a1_by_id["a1-001"]
    assert bulb.name == "Bulbasaur"
    assert bulb.kind == CardKind.POKEMON
    assert bulb.stage == Stage.BASIC
    assert bulb.element == Element.GRASS
    assert bulb.hp == 70
    assert bulb.weakness == Element.FIRE
    assert bulb.retreat_cost == 1
    assert not bulb.is_ex
    assert not bulb.is_mega_ex
    assert bulb.ko_points == 1
    assert bulb.evolves_from is None


def test_bulbasaur_attack(a1_by_id):
    bulb = a1_by_id["a1-001"]
    assert len(bulb.attacks) == 1
    atk = bulb.attacks[0]
    assert atk.name == "Vine Whip"
    assert atk.damage == 40
    assert CostSymbol.GRASS in atk.cost
    assert CostSymbol.COLORLESS in atk.cost
    assert atk.effect_text == ""


def test_venusaur_ex(a1_by_id):
    vex = a1_by_id["a1-004"]
    assert vex.is_ex
    assert not vex.is_mega_ex
    assert vex.ko_points == 2
    assert vex.stage == Stage.STAGE_2


def test_butterfree_ability(a1_by_id):
    b = a1_by_id["a1-007"]
    assert b.ability is not None
    assert "Powder Heal" in b.ability.name
    assert "heal 20" in b.ability.effect_text.lower()


def test_erika_is_supporter(a1_by_id):
    erika = a1_by_id["a1-219"]
    assert erika.kind == CardKind.SUPPORTER
    assert "grass" in erika.trainer_effect_text.lower()


def test_ivysaur_evolves_from(a1_by_id):
    ivy = a1_by_id["a1-002"]
    assert ivy.stage == Stage.STAGE_1
    assert ivy.evolves_from == "Bulbasaur"


def test_most_pokemon_have_element(a1_cards):
    # Dragon-type Pokemon in PTCGP have no element in the raw JSON, so we
    # only assert that most do — not every single one.
    pokemon = [c for c in a1_cards if c.is_pokemon]
    with_element = [c for c in pokemon if c.element is not None]
    assert len(with_element) >= 0.7 * len(pokemon)


def test_all_pokemon_have_positive_hp(a1_cards):
    for card in a1_cards:
        if card.is_pokemon:
            assert card.hp > 0, f"{card.name} has non-positive HP"
