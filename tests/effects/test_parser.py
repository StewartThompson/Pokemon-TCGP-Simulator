"""Tests for ptcgp.effects.parser — pattern-based card effect text parsing."""
import pytest
from ptcgp.effects.base import Effect, UnknownEffect
from ptcgp.effects.parser import parse_effect_text, get_effect_names, is_effect_text_known


def test_parse_heal_self():
    effects = parse_effect_text("Heal 30 damage from this Pokémon")
    assert len(effects) == 1
    e = effects[0]
    assert e.name == "heal_self"
    assert e.params == {"amount": 30}


def test_parse_heal_10():
    effects = parse_effect_text("Heal 10 damage from this Pokémon")
    assert len(effects) == 1
    e = effects[0]
    assert e.name == "heal_self"
    assert e.params == {"amount": 10}


def test_parse_draw_cards():
    effects = parse_effect_text("Draw 2 cards")
    assert len(effects) == 1
    e = effects[0]
    assert e.name == "draw_cards"
    assert e.params == {"count": 2}


def test_parse_heal_target():
    effects = parse_effect_text("Heal 20 damage from 1 of your Pokémon")
    assert len(effects) == 1
    e = effects[0]
    assert e.name == "heal_target"
    assert e.params == {"amount": 20}


def test_parse_discard_energy():
    effects = parse_effect_text("Discard a Fire Energy from this Pokémon")
    assert len(effects) == 1
    e = effects[0]
    assert e.name == "discard_energy_self"
    assert e.params == {"energy_type": "Fire"}


def test_parse_cant_attack():
    effects = parse_effect_text(
        "Defending Pokémon can't attack during your opponent's next turn"
    )
    assert len(effects) == 1
    e = effects[0]
    assert e.name == "cant_attack_next_turn"


def test_parse_attach_zone_self():
    effects = parse_effect_text(
        "Take 3 Fire Energy from your Energy Zone and attach it to this Pokémon"
    )
    assert len(effects) == 1
    e = effects[0]
    assert e.name == "attach_energy_zone_self"
    assert e.params == {"count": 3, "energy_type": "Fire"}


def test_parse_attach_zone_bench():
    effects = parse_effect_text(
        "Take a Grass Energy from your Energy Zone and attach it to 1 of your Benched Grass Pokémon"
    )
    assert len(effects) == 1
    e = effects[0]
    assert e.name == "attach_energy_zone_bench"
    assert e.params == {"energy_type": "Grass", "target_type": "Grass"}


def test_parse_unknown():
    effects = parse_effect_text("Zap the moon with cheese and win the game")
    assert len(effects) == 1
    e = effects[0]
    assert isinstance(e, UnknownEffect)
    assert e.name == "unknown"
    assert "Zap the moon" in e.raw_text


def test_parse_empty():
    assert parse_effect_text("") == []
    assert parse_effect_text(None) == []
    assert parse_effect_text("   ") == []


def test_parse_draw_basic():
    effects = parse_effect_text("Draw 1 basic Pokémon card")
    assert len(effects) == 1
    e = effects[0]
    assert e.name == "draw_basic_pokemon"
    assert e.params == {"count": 1}


def test_parse_rare_candy():
    effects = parse_effect_text(
        "You may evolve a Basic Pokemon directly to a Stage 2 Pokemon this turn"
    )
    assert len(effects) == 1
    e = effects[0]
    assert e.name == "rare_candy_evolve"


def test_parse_switch_opponent():
    effects = parse_effect_text(
        "Switch out your opponent's Active Pokemon to the Bench"
    )
    assert len(effects) == 1
    e = effects[0]
    assert e.name == "switch_opponent_active"


def test_parse_hp_bonus():
    effects = parse_effect_text(
        "The Pokémon this card is attached to has +20 HP"
    )
    assert len(effects) == 1
    e = effects[0]
    assert e.name == "hp_bonus"
    assert e.params == {"amount": 20}


def test_get_effect_names_known():
    names = get_effect_names("Draw 2 cards")
    assert names == ["draw_cards"]


def test_get_effect_names_unknown():
    names = get_effect_names("Do something weird")
    assert names == ["unknown"]


def test_is_effect_text_known_empty():
    assert is_effect_text_known("") is True
    assert is_effect_text_known(None) is True


def test_is_effect_text_known_recognized():
    assert is_effect_text_known("Heal 30 damage from this Pokémon") is True


def test_is_effect_text_known_unrecognized():
    assert is_effect_text_known("Do something completely unrecognized xyz") is False
