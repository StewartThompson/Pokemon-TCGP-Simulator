"""Tests for ptcgp/engine/legal_actions.py."""
from __future__ import annotations

import random

import pytest

from ptcgp.cards.database import load_defaults
from ptcgp.cards.types import Element
from ptcgp.engine.actions import Action, ActionKind, SlotRef
from ptcgp.engine.legal_actions import get_legal_actions, get_legal_promotions
from ptcgp.engine.state import GamePhase, GameState, PlayerState, PokemonSlot, StatusEffect


# ---------------------------------------------------------------------------
# Module-level setup: load cards once
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module", autouse=True)
def _load_cards():
    load_defaults()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _minimal_state(
    *,
    turn_number: int = 2,
    current_player: int = 0,
    first_player: int = 0,
    active0: PokemonSlot | None = None,
    active1: PokemonSlot | None = None,
    bench0: list[PokemonSlot | None] | None = None,
    bench1: list[PokemonSlot | None] | None = None,
    hand0: list[str] | None = None,
    energy_available: Element | None = None,
    has_attached_energy: bool = False,
    has_played_supporter: bool = False,
    has_retreated: bool = False,
    phase: GamePhase = GamePhase.MAIN,
    winner: int | None = None,
) -> GameState:
    """Build a minimal GameState for unit testing."""
    if active0 is None:
        # Default active for player 0: Bulbasaur
        active0 = PokemonSlot(card_id="a1-001", current_hp=70, max_hp=70)
    if active1 is None:
        # Default active for player 1: Charmander
        active1 = PokemonSlot(card_id="a1-230", current_hp=60, max_hp=60)

    p0 = PlayerState(
        active=active0,
        bench=bench0 if bench0 is not None else [None, None, None],
        hand=hand0 if hand0 is not None else [],
        energy_available=energy_available,
        has_attached_energy=has_attached_energy,
        has_played_supporter=has_played_supporter,
        has_retreated=has_retreated,
    )
    p1 = PlayerState(
        active=active1,
        bench=bench1 if bench1 is not None else [None, None, None],
    )

    state = GameState(
        players=[p0, p1],
        turn_number=turn_number,
        current_player=current_player,
        first_player=first_player,
        phase=phase,
        winner=winner,
        rng=random.Random(42),
    )
    return state


def _has_kind(actions: list[Action], kind: ActionKind) -> bool:
    return any(a.kind == kind for a in actions)


def _actions_of(actions: list[Action], kind: ActionKind) -> list[Action]:
    return [a for a in actions if a.kind == kind]


# ---------------------------------------------------------------------------
# Tests: phase guards
# ---------------------------------------------------------------------------

def test_returns_empty_when_not_main_phase():
    state = _minimal_state(phase=GamePhase.SETUP)
    assert get_legal_actions(state) == []


def test_returns_empty_when_awaiting_bench_promotion():
    state = _minimal_state(phase=GamePhase.AWAITING_BENCH_PROMOTION)
    assert get_legal_actions(state) == []


def test_returns_empty_when_game_over():
    state = _minimal_state(phase=GamePhase.GAME_OVER)
    assert get_legal_actions(state) == []


def test_returns_empty_when_winner_set():
    state = _minimal_state(winner=0)
    assert get_legal_actions(state) == []


# ---------------------------------------------------------------------------
# Tests: END_TURN
# ---------------------------------------------------------------------------

def test_end_turn_always_present():
    state = _minimal_state()
    actions = get_legal_actions(state)
    assert _has_kind(actions, ActionKind.END_TURN)


def test_empty_hand_minimal_actions():
    """With empty hand and no energy, only END_TURN (and possibly ATTACK) are legal."""
    state = _minimal_state(hand0=[])
    actions = get_legal_actions(state)
    kinds = {a.kind for a in actions}
    # Cannot have PLAY_CARD, EVOLVE with empty hand
    assert ActionKind.PLAY_CARD not in kinds
    assert ActionKind.EVOLVE not in kinds
    assert ActionKind.ATTACH_ENERGY not in kinds
    assert ActionKind.END_TURN in kinds


# ---------------------------------------------------------------------------
# Tests: PLAY_CARD — Basic Pokemon
# ---------------------------------------------------------------------------

def test_play_basic_to_bench():
    """Basic Pokemon in hand + empty bench slot => PLAY_CARD action."""
    state = _minimal_state(hand0=["a1-001"])  # Bulbasaur
    actions = get_legal_actions(state)
    play_card_actions = _actions_of(actions, ActionKind.PLAY_CARD)
    assert len(play_card_actions) >= 1
    # Should target a bench slot
    bench_targets = [a for a in play_card_actions if a.target is not None and a.target.is_bench()]
    assert len(bench_targets) >= 1


def test_no_play_basic_full_bench():
    """Bench completely full => no PLAY_CARD for basic Pokemon."""
    full_bench = [
        PokemonSlot(card_id="a1-001", current_hp=70, max_hp=70),
        PokemonSlot(card_id="a1-001", current_hp=70, max_hp=70),
        PokemonSlot(card_id="a1-001", current_hp=70, max_hp=70),
    ]
    state = _minimal_state(
        hand0=["a1-001"],  # Bulbasaur
        bench0=full_bench,
    )
    actions = get_legal_actions(state)
    play_card_actions = _actions_of(actions, ActionKind.PLAY_CARD)
    # None of them should be targeting bench slots (since all full)
    bench_targets = [a for a in play_card_actions if a.target is not None and a.target.is_bench()]
    assert len(bench_targets) == 0


def test_play_basic_to_multiple_empty_bench_slots():
    """Multiple empty bench slots => multiple PLAY_CARD actions per basic."""
    state = _minimal_state(hand0=["a1-005"])  # Caterpie
    actions = get_legal_actions(state)
    play_card_actions = [
        a for a in actions
        if a.kind == ActionKind.PLAY_CARD
        and a.hand_index == 0
        and a.target is not None
        and a.target.is_bench()
    ]
    # 3 empty bench slots => 3 PLAY_CARD actions
    assert len(play_card_actions) == 3


# ---------------------------------------------------------------------------
# Tests: PLAY_CARD — Item
# ---------------------------------------------------------------------------

def test_play_item_legal():
    """Item card in hand => PLAY_CARD action with no target."""
    # a1a-063 = Old Amber (Item)
    state = _minimal_state(hand0=["a1a-063"])
    actions = get_legal_actions(state)
    play_card_actions = _actions_of(actions, ActionKind.PLAY_CARD)
    item_actions = [a for a in play_card_actions if a.target is None]
    assert len(item_actions) >= 1


# ---------------------------------------------------------------------------
# Tests: PLAY_CARD — Supporter
# ---------------------------------------------------------------------------

def test_supporter_legal():
    """Supporter card in hand, not yet played => PLAY_CARD.

    Erika ('Heal 50 damage from 1 of your Grass Pokémon') needs a *damaged*
    Grass target, so we only see an action when a Grass Pokemon has missing HP.
    """
    # a1-219 = Erika (Supporter). Give the Bulbasaur active some damage so
    # Erika has a legal heal target.
    damaged_active = PokemonSlot(card_id="a1-001", current_hp=40, max_hp=70)
    state = _minimal_state(
        hand0=["a1-219"], active0=damaged_active, has_played_supporter=False
    )
    actions = get_legal_actions(state)
    play_card_actions = _actions_of(actions, ActionKind.PLAY_CARD)
    assert len(play_card_actions) >= 1
    assert all(a.target is not None for a in play_card_actions)


def test_supporter_no_damaged_target_is_absent():
    """Erika is NOT offered when every Grass Pokemon is at full HP."""
    state = _minimal_state(hand0=["a1-219"], has_played_supporter=False)
    actions = get_legal_actions(state)
    play_card_actions = _actions_of(actions, ActionKind.PLAY_CARD)
    assert play_card_actions == []


def test_no_second_supporter():
    """has_played_supporter=True => no PLAY_CARD for supporter."""
    state = _minimal_state(hand0=["a1-219"], has_played_supporter=True)
    actions = get_legal_actions(state)
    # The only card in hand is a supporter; bench-targeting play_card would be 0
    # No non-targeted PLAY_CARD should exist (no items in hand)
    play_card_actions = _actions_of(actions, ActionKind.PLAY_CARD)
    assert len(play_card_actions) == 0


# ---------------------------------------------------------------------------
# Tests: ATTACH_ENERGY
# ---------------------------------------------------------------------------

def test_attach_energy_to_active():
    """Energy available, not yet attached => ATTACH_ENERGY for active."""
    state = _minimal_state(energy_available=Element.GRASS, has_attached_energy=False)
    actions = get_legal_actions(state)
    energy_actions = _actions_of(actions, ActionKind.ATTACH_ENERGY)
    active_targets = [a for a in energy_actions if a.target is not None and a.target.is_active()]
    assert len(active_targets) == 1


def test_attach_energy_to_bench_pokemon():
    """Energy available + bench Pokemon => ATTACH_ENERGY targets bench too."""
    bench = [
        PokemonSlot(card_id="a1-001", current_hp=70, max_hp=70),
        None,
        None,
    ]
    state = _minimal_state(
        bench0=bench,
        energy_available=Element.GRASS,
        has_attached_energy=False,
    )
    actions = get_legal_actions(state)
    energy_actions = _actions_of(actions, ActionKind.ATTACH_ENERGY)
    assert len(energy_actions) == 2  # 1 active + 1 bench


def test_no_attach_if_already_attached():
    """has_attached_energy=True => no ATTACH_ENERGY."""
    state = _minimal_state(energy_available=Element.GRASS, has_attached_energy=True)
    actions = get_legal_actions(state)
    assert not _has_kind(actions, ActionKind.ATTACH_ENERGY)


def test_no_attach_if_no_energy_available():
    """energy_available=None => no ATTACH_ENERGY."""
    state = _minimal_state(energy_available=None, has_attached_energy=False)
    actions = get_legal_actions(state)
    assert not _has_kind(actions, ActionKind.ATTACH_ENERGY)


# ---------------------------------------------------------------------------
# Tests: EVOLVE
# ---------------------------------------------------------------------------

def test_evolve_legal_turn_2():
    """Evolution card + valid target with turns_in_play>=1 + turn_number=2 => EVOLVE."""
    # Bulbasaur in active, Ivysaur in hand
    active = PokemonSlot(card_id="a1-001", current_hp=70, max_hp=70, turns_in_play=2)
    state = _minimal_state(
        active0=active,
        hand0=["a1-002"],  # Ivysaur
        turn_number=2,
    )
    actions = get_legal_actions(state)
    assert _has_kind(actions, ActionKind.EVOLVE)


def test_evolve_illegal_turn_0():
    """turn_number=0 => no EVOLVE."""
    active = PokemonSlot(card_id="a1-001", current_hp=70, max_hp=70, turns_in_play=1)
    state = _minimal_state(
        active0=active,
        hand0=["a1-002"],  # Ivysaur
        turn_number=0,
    )
    actions = get_legal_actions(state)
    assert not _has_kind(actions, ActionKind.EVOLVE)


def test_evolve_illegal_turn_1():
    """turn_number=1 => no EVOLVE."""
    active = PokemonSlot(card_id="a1-001", current_hp=70, max_hp=70, turns_in_play=1)
    state = _minimal_state(
        active0=active,
        hand0=["a1-002"],  # Ivysaur
        turn_number=1,
    )
    actions = get_legal_actions(state)
    assert not _has_kind(actions, ActionKind.EVOLVE)


def test_evolve_requires_turns_in_play():
    """turns_in_play=0 => no EVOLVE even on turn 2+."""
    active = PokemonSlot(card_id="a1-001", current_hp=70, max_hp=70, turns_in_play=0)
    state = _minimal_state(
        active0=active,
        hand0=["a1-002"],  # Ivysaur
        turn_number=3,
    )
    actions = get_legal_actions(state)
    assert not _has_kind(actions, ActionKind.EVOLVE)


def test_evolve_blocked_if_evolved_this_turn():
    """evolved_this_turn=True => no EVOLVE."""
    active = PokemonSlot(
        card_id="a1-001", current_hp=70, max_hp=70,
        turns_in_play=2, evolved_this_turn=True,
    )
    state = _minimal_state(
        active0=active,
        hand0=["a1-002"],  # Ivysaur
        turn_number=3,
    )
    actions = get_legal_actions(state)
    assert not _has_kind(actions, ActionKind.EVOLVE)


# ---------------------------------------------------------------------------
# Tests: ATTACK
# ---------------------------------------------------------------------------

def test_attack_illegal_turn_0():
    """turn_number=0 => no ATTACK."""
    # Caterpie has 1-colorless attack; give it energy
    active = PokemonSlot(
        card_id="a1-005", current_hp=50, max_hp=50,
        attached_energy={Element.GRASS: 1},
    )
    state = _minimal_state(active0=active, turn_number=0)
    actions = get_legal_actions(state)
    assert not _has_kind(actions, ActionKind.ATTACK)


def test_attack_illegal_turn_1():
    """turn_number=1 => no ATTACK."""
    active = PokemonSlot(
        card_id="a1-005", current_hp=50, max_hp=50,
        attached_energy={Element.GRASS: 1},
    )
    state = _minimal_state(active0=active, turn_number=1)
    actions = get_legal_actions(state)
    assert not _has_kind(actions, ActionKind.ATTACK)


def test_attack_legal_turn_2():
    """turn_number=2, sufficient energy => ATTACK."""
    # Caterpie: Find a Friend (COLORLESS cost, 0 damage) — costs 1 colorless
    active = PokemonSlot(
        card_id="a1-005", current_hp=50, max_hp=50,
        attached_energy={Element.GRASS: 1},
    )
    state = _minimal_state(active0=active, turn_number=2)
    actions = get_legal_actions(state)
    assert _has_kind(actions, ActionKind.ATTACK)


def test_attack_blocked_insufficient_energy():
    """Not enough energy => no ATTACK."""
    # Bulbasaur needs GRASS + COLORLESS
    active = PokemonSlot(
        card_id="a1-001", current_hp=70, max_hp=70,
        attached_energy={},  # no energy
    )
    state = _minimal_state(active0=active, turn_number=2)
    actions = get_legal_actions(state)
    assert not _has_kind(actions, ActionKind.ATTACK)


def test_attack_blocked_paralyzed():
    """PARALYZED active => no ATTACK."""
    active = PokemonSlot(
        card_id="a1-005", current_hp=50, max_hp=50,
        attached_energy={Element.GRASS: 1},
        status_effects={StatusEffect.PARALYZED},
    )
    state = _minimal_state(active0=active, turn_number=2)
    actions = get_legal_actions(state)
    assert not _has_kind(actions, ActionKind.ATTACK)


def test_attack_blocked_asleep():
    """ASLEEP active => no ATTACK."""
    active = PokemonSlot(
        card_id="a1-005", current_hp=50, max_hp=50,
        attached_energy={Element.GRASS: 1},
        status_effects={StatusEffect.ASLEEP},
    )
    state = _minimal_state(active0=active, turn_number=2)
    actions = get_legal_actions(state)
    assert not _has_kind(actions, ActionKind.ATTACK)


def test_attack_blocked_cant_attack_next_turn():
    """cant_attack_next_turn=True => no ATTACK."""
    active = PokemonSlot(
        card_id="a1-005", current_hp=50, max_hp=50,
        attached_energy={Element.GRASS: 1},
        cant_attack_next_turn=True,
    )
    state = _minimal_state(active0=active, turn_number=2)
    actions = get_legal_actions(state)
    assert not _has_kind(actions, ActionKind.ATTACK)


# ---------------------------------------------------------------------------
# Tests: RETREAT
# ---------------------------------------------------------------------------

def test_retreat_legal():
    """Has bench Pokemon, enough energy for retreat => RETREAT actions."""
    active = PokemonSlot(
        card_id="a1-001", current_hp=70, max_hp=70,
        attached_energy={Element.GRASS: 1},  # Bulbasaur retreat_cost=1
    )
    bench = [
        PokemonSlot(card_id="a1-005", current_hp=50, max_hp=50),
        None, None,
    ]
    state = _minimal_state(active0=active, bench0=bench, has_retreated=False)
    actions = get_legal_actions(state)
    retreat_actions = _actions_of(actions, ActionKind.RETREAT)
    assert len(retreat_actions) == 1
    assert retreat_actions[0].target == SlotRef.bench(0, 0)


def test_retreat_blocked_paralyzed():
    """PARALYZED active => no RETREAT."""
    active = PokemonSlot(
        card_id="a1-001", current_hp=70, max_hp=70,
        attached_energy={Element.GRASS: 1},
        status_effects={StatusEffect.PARALYZED},
    )
    bench = [PokemonSlot(card_id="a1-005", current_hp=50, max_hp=50), None, None]
    state = _minimal_state(active0=active, bench0=bench)
    actions = get_legal_actions(state)
    assert not _has_kind(actions, ActionKind.RETREAT)


def test_retreat_blocked_asleep():
    """ASLEEP active => no RETREAT."""
    active = PokemonSlot(
        card_id="a1-001", current_hp=70, max_hp=70,
        attached_energy={Element.GRASS: 1},
        status_effects={StatusEffect.ASLEEP},
    )
    bench = [PokemonSlot(card_id="a1-005", current_hp=50, max_hp=50), None, None]
    state = _minimal_state(active0=active, bench0=bench)
    actions = get_legal_actions(state)
    assert not _has_kind(actions, ActionKind.RETREAT)


def test_retreat_blocked_no_bench():
    """No bench Pokemon => no RETREAT."""
    active = PokemonSlot(
        card_id="a1-001", current_hp=70, max_hp=70,
        attached_energy={Element.GRASS: 1},
    )
    state = _minimal_state(active0=active, bench0=[None, None, None])
    actions = get_legal_actions(state)
    assert not _has_kind(actions, ActionKind.RETREAT)


def test_retreat_blocked_already_retreated():
    """has_retreated=True => no RETREAT."""
    active = PokemonSlot(
        card_id="a1-001", current_hp=70, max_hp=70,
        attached_energy={Element.GRASS: 1},
    )
    bench = [PokemonSlot(card_id="a1-005", current_hp=50, max_hp=50), None, None]
    state = _minimal_state(active0=active, bench0=bench, has_retreated=True)
    actions = get_legal_actions(state)
    assert not _has_kind(actions, ActionKind.RETREAT)


def test_retreat_blocked_not_enough_energy():
    """Not enough energy to pay retreat cost => no RETREAT."""
    # Bulbasaur has retreat_cost=1, no energy attached
    active = PokemonSlot(
        card_id="a1-001", current_hp=70, max_hp=70,
        attached_energy={},  # 0 energy, need 1
    )
    bench = [PokemonSlot(card_id="a1-005", current_hp=50, max_hp=50), None, None]
    state = _minimal_state(active0=active, bench0=bench)
    actions = get_legal_actions(state)
    assert not _has_kind(actions, ActionKind.RETREAT)


# ---------------------------------------------------------------------------
# Tests: get_legal_promotions
# ---------------------------------------------------------------------------

def test_promote_phase():
    """AWAITING_BENCH_PROMOTION + bench Pokemon => PROMOTE actions."""
    bench = [
        PokemonSlot(card_id="a1-001", current_hp=70, max_hp=70),
        PokemonSlot(card_id="a1-005", current_hp=50, max_hp=50),
        None,
    ]
    # Player 0 has no active (just KO'd)
    p0 = PlayerState(active=None, bench=bench)
    p1 = PlayerState(active=PokemonSlot(card_id="a1-230", current_hp=60, max_hp=60))
    state = GameState(
        players=[p0, p1],
        turn_number=2,
        current_player=1,
        phase=GamePhase.AWAITING_BENCH_PROMOTION,
        rng=random.Random(42),
    )
    promotions = get_legal_promotions(state, 0)
    assert len(promotions) == 2
    kinds = {a.kind for a in promotions}
    assert kinds == {ActionKind.PROMOTE}
    slots = {a.target.slot for a in promotions}
    assert slots == {0, 1}


def test_promote_empty_bench_returns_nothing():
    """AWAITING_BENCH_PROMOTION with empty bench => no promotions."""
    p0 = PlayerState(active=None, bench=[None, None, None])
    p1 = PlayerState(active=PokemonSlot(card_id="a1-230", current_hp=60, max_hp=60))
    state = GameState(
        players=[p0, p1],
        turn_number=2,
        current_player=1,
        phase=GamePhase.AWAITING_BENCH_PROMOTION,
        rng=random.Random(42),
    )
    promotions = get_legal_promotions(state, 0)
    assert promotions == []


def test_promote_wrong_phase_returns_empty():
    """Not in AWAITING_BENCH_PROMOTION => get_legal_promotions returns []."""
    bench = [PokemonSlot(card_id="a1-001", current_hp=70, max_hp=70), None, None]
    p0 = PlayerState(active=None, bench=bench)
    p1 = PlayerState(active=PokemonSlot(card_id="a1-230", current_hp=60, max_hp=60))
    state = GameState(
        players=[p0, p1],
        turn_number=2,
        phase=GamePhase.MAIN,
        rng=random.Random(42),
    )
    promotions = get_legal_promotions(state, 0)
    assert promotions == []
