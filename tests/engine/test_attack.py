"""Tests for ptcgp/engine/attack.py — attack execution and energy cost logic."""
from __future__ import annotations

import random
import pytest

from ptcgp.cards.card import Card
from ptcgp.cards.attack import Attack
from ptcgp.cards.database import clear_db, register_card
from ptcgp.cards.types import CardKind, CostSymbol, Element, Stage
from ptcgp.engine.attack import can_pay_cost, execute_attack
from ptcgp.engine.state import GameState, GamePhase, PlayerState, PokemonSlot, StatusEffect


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_pokemon(
    cid: str,
    name: str = "TestMon",
    hp: int = 70,
    element: Element = Element.FIRE,
    weakness: Element | None = None,
    attacks: tuple[Attack, ...] = (),
    is_ex: bool = False,
) -> Card:
    if not attacks:
        attacks = (Attack(name="Scratch", damage=30, cost=(CostSymbol.COLORLESS,)),)
    return Card(
        id=cid,
        name=name,
        kind=CardKind.POKEMON,
        stage=Stage.BASIC,
        element=element,
        hp=hp,
        weakness=weakness,
        retreat_cost=1,
        is_ex=is_ex,
        attacks=attacks,
    )


def _make_state(
    attacker_card: Card,
    defender_card: Card,
    attacker_energy: dict[Element, int] | None = None,
    current_player: int = 0,
) -> GameState:
    """Build a minimal two-player GameState with one active Pokemon per player."""
    attacker_slot = PokemonSlot(
        card_id=attacker_card.id,
        current_hp=attacker_card.hp,
        max_hp=attacker_card.hp,
        attached_energy=attacker_energy or {},
    )
    defender_slot = PokemonSlot(
        card_id=defender_card.id,
        current_hp=defender_card.hp,
        max_hp=defender_card.hp,
    )

    p0 = PlayerState(active=attacker_slot)
    p1 = PlayerState(active=defender_slot)

    state = GameState(
        players=[p0, p1],
        current_player=current_player,
        phase=GamePhase.MAIN,
        rng=random.Random(42),
    )
    return state


@pytest.fixture(autouse=True)
def fresh_db():
    clear_db()
    yield
    clear_db()


# ---------------------------------------------------------------------------
# can_pay_cost tests
# ---------------------------------------------------------------------------

def test_energy_check_colorless():
    """Colorless cost can be paid with any energy type."""
    card = _make_pokemon("t001", attacks=(
        Attack("Scratch", 30, (CostSymbol.COLORLESS,)),
    ))
    register_card(card)

    slot = PokemonSlot(
        card_id="t001",
        current_hp=70,
        max_hp=70,
        attached_energy={Element.FIRE: 1},
    )
    assert can_pay_cost(slot, (CostSymbol.COLORLESS,)) is True


def test_energy_check_colorless_with_water():
    """Colorless can be satisfied by WATER energy."""
    slot = PokemonSlot(
        card_id="dummy",
        current_hp=70,
        max_hp=70,
        attached_energy={Element.WATER: 2},
    )
    assert can_pay_cost(slot, (CostSymbol.COLORLESS, CostSymbol.COLORLESS)) is True


def test_energy_check_fails_insufficient():
    """can_pay_cost returns False when not enough energy."""
    card = _make_pokemon("t002", attacks=(
        Attack("Big Hit", 60, (CostSymbol.FIRE, CostSymbol.FIRE)),
    ))
    register_card(card)

    slot = PokemonSlot(
        card_id="t002",
        current_hp=70,
        max_hp=70,
        attached_energy={Element.FIRE: 1},  # only 1, need 2
    )
    assert can_pay_cost(slot, (CostSymbol.FIRE, CostSymbol.FIRE)) is False


def test_energy_check_typed_not_satisfied_by_colorless():
    """A typed cost (FIRE) cannot be satisfied by a different type (WATER)."""
    slot = PokemonSlot(
        card_id="dummy",
        current_hp=70,
        max_hp=70,
        attached_energy={Element.WATER: 2},
    )
    assert can_pay_cost(slot, (CostSymbol.FIRE,)) is False


def test_energy_check_mixed_cost():
    """Mixed cost: one typed + one colorless satisfied by 2 fire energy."""
    slot = PokemonSlot(
        card_id="dummy",
        current_hp=70,
        max_hp=70,
        attached_energy={Element.FIRE: 2},
    )
    assert can_pay_cost(slot, (CostSymbol.FIRE, CostSymbol.COLORLESS)) is True


def test_energy_check_empty_cost():
    """Zero-cost attack can always be used."""
    slot = PokemonSlot(
        card_id="dummy",
        current_hp=70,
        max_hp=70,
        attached_energy={},
    )
    assert can_pay_cost(slot, ()) is True


# ---------------------------------------------------------------------------
# execute_attack tests
# ---------------------------------------------------------------------------

def test_basic_attack_deals_damage():
    """Attacker deals damage to defender's active Pokemon."""
    attacker = _make_pokemon(
        "a001",
        element=Element.FIRE,
        attacks=(Attack("Ember", 30, (CostSymbol.FIRE,)),),
    )
    defender = _make_pokemon(
        "d001",
        element=Element.GRASS,
        weakness=None,
        hp=70,
    )
    register_card(attacker)
    register_card(defender)

    state = _make_state(attacker, defender, attacker_energy={Element.FIRE: 1})
    result = execute_attack(state, 0)

    assert result.players[1].active.current_hp == 70 - 30


def test_weakness_bonus():
    """Fire type attacking Grass (weak to Fire) adds +20 damage."""
    attacker = _make_pokemon(
        "a002",
        element=Element.FIRE,
        attacks=(Attack("Ember", 30, (CostSymbol.COLORLESS,)),),
    )
    defender = _make_pokemon(
        "d002",
        element=Element.GRASS,
        weakness=Element.FIRE,
        hp=70,
    )
    register_card(attacker)
    register_card(defender)

    state = _make_state(attacker, defender, attacker_energy={Element.FIRE: 1})
    result = execute_attack(state, 0)

    assert result.players[1].active.current_hp == 70 - (30 + 20)


def test_no_weakness_no_bonus():
    """Non-matching weakness type does not add bonus damage."""
    attacker = _make_pokemon(
        "a003",
        element=Element.WATER,
        attacks=(Attack("Splash", 30, (CostSymbol.COLORLESS,)),),
    )
    defender = _make_pokemon(
        "d003",
        element=Element.GRASS,
        weakness=Element.FIRE,  # weak to FIRE not WATER
        hp=70,
    )
    register_card(attacker)
    register_card(defender)

    state = _make_state(attacker, defender, attacker_energy={Element.WATER: 1})
    result = execute_attack(state, 0)

    assert result.players[1].active.current_hp == 70 - 30


def test_confusion_tails_no_damage():
    """Seeded RNG that gives tails: attack fails, defender takes no damage."""
    attacker = _make_pokemon(
        "a004",
        element=Element.FIRE,
        attacks=(Attack("Ember", 30, (CostSymbol.COLORLESS,)),),
    )
    defender = _make_pokemon(
        "d004",
        element=Element.GRASS,
        hp=70,
    )
    register_card(attacker)
    register_card(defender)

    state = _make_state(attacker, defender, attacker_energy={Element.FIRE: 1})

    # Find a seed where the first rng.random() call gives tails (>= 0.5)
    # i.e. the coin flip returns False (tails)
    import random as _random
    seed = 1  # empirically: seed=1 gives random() > 0.5 first call
    rng = _random.Random(seed)
    first_val = rng.random()
    while first_val < 0.5:
        seed += 1
        rng = _random.Random(seed)
        first_val = rng.random()

    # Apply confusion to attacker
    state.players[0].active.status_effects.add(StatusEffect.CONFUSED)
    state.rng = _random.Random(seed)

    result = execute_attack(state, 0)

    # Defender should take no damage (attack failed due to tails)
    assert result.players[1].active.current_hp == 70


def test_confusion_heads_deals_damage():
    """Seeded RNG that gives heads: attack proceeds and deals damage."""
    attacker = _make_pokemon(
        "a005",
        element=Element.FIRE,
        attacks=(Attack("Ember", 30, (CostSymbol.COLORLESS,)),),
    )
    defender = _make_pokemon(
        "d005",
        element=Element.GRASS,
        hp=70,
    )
    register_card(attacker)
    register_card(defender)

    state = _make_state(attacker, defender, attacker_energy={Element.FIRE: 1})

    # Find a seed where the first rng.random() call gives heads (< 0.5)
    import random as _random
    seed = 0
    rng = _random.Random(seed)
    first_val = rng.random()
    while first_val >= 0.5:
        seed += 1
        rng = _random.Random(seed)
        first_val = rng.random()

    # Apply confusion to attacker
    state.players[0].active.status_effects.add(StatusEffect.CONFUSED)
    state.rng = _random.Random(seed)

    result = execute_attack(state, 0)

    # Defender should take damage (attack succeeded)
    assert result.players[1].active.current_hp == 70 - 30


def test_energy_not_consumed():
    """After attacking, attached energy is unchanged (energy is not consumed)."""
    attacker = _make_pokemon(
        "a006",
        element=Element.FIRE,
        attacks=(Attack("Ember", 30, (CostSymbol.FIRE,)),),
    )
    defender = _make_pokemon(
        "d006",
        element=Element.GRASS,
        hp=70,
    )
    register_card(attacker)
    register_card(defender)

    state = _make_state(attacker, defender, attacker_energy={Element.FIRE: 2})
    result = execute_attack(state, 0)

    assert result.players[0].active.attached_energy == {Element.FIRE: 2}


def test_insufficient_energy_raises():
    """execute_attack raises ValueError if attacker can't pay the cost."""
    attacker = _make_pokemon(
        "a007",
        element=Element.FIRE,
        attacks=(Attack("Big Hit", 60, (CostSymbol.FIRE, CostSymbol.FIRE)),),
    )
    defender = _make_pokemon(
        "d007",
        element=Element.GRASS,
        hp=70,
    )
    register_card(attacker)
    register_card(defender)

    # Only 1 FIRE energy attached, need 2
    state = _make_state(attacker, defender, attacker_energy={Element.FIRE: 1})

    with pytest.raises(ValueError, match="cannot pay cost"):
        execute_attack(state, 0)


def test_damage_clamped_to_zero():
    """Damage cannot reduce HP below 0."""
    attacker = _make_pokemon(
        "a008",
        element=Element.FIRE,
        attacks=(Attack("Huge Hit", 200, (CostSymbol.COLORLESS,)),),
    )
    defender = _make_pokemon(
        "d008",
        element=Element.GRASS,
        hp=50,
    )
    register_card(attacker)
    register_card(defender)

    state = _make_state(attacker, defender, attacker_energy={Element.FIRE: 1})
    result = execute_attack(state, 0)

    assert result.players[1].active.current_hp == 0
