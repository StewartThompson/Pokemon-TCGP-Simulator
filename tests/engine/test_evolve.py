"""Tests for evolve.py — evolving Pokemon in play."""
import pytest
from ptcgp.cards.database import load_defaults
from ptcgp.cards.types import Element
from ptcgp.engine.actions import SlotRef
from ptcgp.engine.evolve import evolve_pokemon
from ptcgp.engine.state import GameState, PlayerState, PokemonSlot, StatusEffect


def setup_module():
    load_defaults()


def make_evolve_state(
    active_card_id: str = "a1-001",    # Bulbasaur
    evo_card_id: str = "a1-002",       # Ivysaur
    turns_in_play: int = 2,
    evolved_this_turn: bool = False,
    turn_number: int = 2,
    first_player: int = 0,
    current_player: int = 0,
    attached_energy: dict | None = None,
    tool_card_id: str | None = None,
    status_effects: set | None = None,
    active_hp: int | None = None,
) -> GameState:
    """Build a minimal state for evolution testing."""
    from ptcgp.cards.database import get_card
    card = get_card(active_card_id)
    if active_hp is None:
        active_hp = card.hp
    slot = PokemonSlot(
        card_id=active_card_id,
        current_hp=active_hp,
        max_hp=card.hp,
        turns_in_play=turns_in_play,
        evolved_this_turn=evolved_this_turn,
        attached_energy=dict(attached_energy or {}),
        tool_card_id=tool_card_id,
        status_effects=set(status_effects or set()),
    )
    player = PlayerState(
        active=slot,
        hand=[evo_card_id],
        energy_types=[Element.GRASS],
    )
    state = GameState(
        players=[player, PlayerState()],
        turn_number=turn_number,
        first_player=first_player,
        current_player=current_player,
    )
    return state


# --- basic evolution ---

def test_evolve_basic_to_stage1():
    """Bulbasaur evolves into Ivysaur successfully."""
    state = make_evolve_state()
    target = SlotRef.active(player=0)
    new_state = evolve_pokemon(state, hand_index=0, target=target)
    slot = new_state.players[0].active
    assert slot.card_id == "a1-002"  # Ivysaur


def test_evolve_removes_from_hand():
    """Evolution card is removed from hand."""
    state = make_evolve_state()
    target = SlotRef.active(player=0)
    new_state = evolve_pokemon(state, hand_index=0, target=target)
    assert "a1-002" not in new_state.players[0].hand


def test_evolve_sets_evolved_this_turn():
    """evolved_this_turn flag is True on the new slot."""
    state = make_evolve_state()
    target = SlotRef.active(player=0)
    new_state = evolve_pokemon(state, hand_index=0, target=target)
    assert new_state.players[0].active.evolved_this_turn is True


def test_evolve_clears_status():
    """Evolved Pokemon has no status effects."""
    state = make_evolve_state(status_effects={StatusEffect.POISONED, StatusEffect.BURNED})
    target = SlotRef.active(player=0)
    new_state = evolve_pokemon(state, hand_index=0, target=target)
    assert len(new_state.players[0].active.status_effects) == 0


def test_evolve_carries_energy():
    """Attached energy carries over to evolved Pokemon."""
    state = make_evolve_state(attached_energy={Element.GRASS: 2})
    target = SlotRef.active(player=0)
    new_state = evolve_pokemon(state, hand_index=0, target=target)
    slot = new_state.players[0].active
    assert slot.attached_energy.get(Element.GRASS, 0) == 2


def test_evolve_carries_tool():
    """Tool card ID carries over to evolved Pokemon."""
    state = make_evolve_state(tool_card_id="a2-147")
    target = SlotRef.active(player=0)
    new_state = evolve_pokemon(state, hand_index=0, target=target)
    assert new_state.players[0].active.tool_card_id == "a2-147"


def test_evolve_keeps_turns_in_play():
    """turns_in_play counter carries over (not reset)."""
    state = make_evolve_state(turns_in_play=3)
    target = SlotRef.active(player=0)
    new_state = evolve_pokemon(state, hand_index=0, target=target)
    assert new_state.players[0].active.turns_in_play == 3


def test_evolve_damage_carries_over():
    """If target took damage, evolved Pokemon is at (new_hp - damage_taken)."""
    from ptcgp.cards.database import get_card
    bulbasaur = get_card("a1-001")
    ivysaur = get_card("a1-002")
    damage = 20
    state = make_evolve_state(active_hp=bulbasaur.hp - damage)
    target = SlotRef.active(player=0)
    new_state = evolve_pokemon(state, hand_index=0, target=target)
    slot = new_state.players[0].active
    expected_hp = ivysaur.hp - damage
    assert slot.current_hp == expected_hp
    assert slot.max_hp == ivysaur.hp


def test_evolve_full_hp_stays_at_max():
    """Undamaged Pokemon evolves to full HP of new form."""
    from ptcgp.cards.database import get_card
    ivysaur = get_card("a1-002")
    state = make_evolve_state()
    target = SlotRef.active(player=0)
    new_state = evolve_pokemon(state, hand_index=0, target=target)
    slot = new_state.players[0].active
    assert slot.current_hp == ivysaur.hp


# --- failure cases ---

def test_evolve_fails_if_just_placed():
    """Raises ValueError if target has turns_in_play == 0."""
    state = make_evolve_state(turns_in_play=0)
    target = SlotRef.active(player=0)
    with pytest.raises(ValueError, match="just placed|at least 1 turn"):
        evolve_pokemon(state, hand_index=0, target=target)


def test_evolve_fails_wrong_evolves_from():
    """Raises ValueError if evo card's evolves_from doesn't match target."""
    # Metapod evolves from Caterpie, not Bulbasaur
    state = make_evolve_state(active_card_id="a1-001", evo_card_id="a1-006")
    target = SlotRef.active(player=0)
    with pytest.raises(ValueError, match="evolves from"):
        evolve_pokemon(state, hand_index=0, target=target)


def test_evolve_fails_if_already_evolved_this_turn():
    """Raises ValueError if target already evolved this turn."""
    state = make_evolve_state(evolved_this_turn=True)
    target = SlotRef.active(player=0)
    with pytest.raises(ValueError, match="already evolved"):
        evolve_pokemon(state, hand_index=0, target=target)


def test_evolve_fails_on_first_turn_player0():
    """Cannot evolve on turn 0 (very first turn)."""
    state = make_evolve_state(turn_number=0)
    target = SlotRef.active(player=0)
    with pytest.raises(ValueError, match="first turn"):
        evolve_pokemon(state, hand_index=0, target=target)


def test_evolve_fails_on_first_turn_player1():
    """Cannot evolve on turn 1 if it's the second player's first turn."""
    # first_player=0, current_player=1, turn_number=1 means player 1 is on their first turn
    state = make_evolve_state(turn_number=1, first_player=0, current_player=1)
    target = SlotRef.active(player=1)
    # Put Bulbasaur as player 1's active
    from ptcgp.cards.database import get_card
    card = get_card("a1-001")
    slot = PokemonSlot(card_id="a1-001", current_hp=card.hp, max_hp=card.hp, turns_in_play=2)
    state.players[1].active = slot
    state.players[1].hand = ["a1-002"]
    with pytest.raises(ValueError, match="first turn"):
        evolve_pokemon(state, hand_index=0, target=target)


def test_evolve_does_not_mutate_original():
    """Original state is unchanged (copy-on-write)."""
    state = make_evolve_state()
    target = SlotRef.active(player=0)
    original_card_id = state.players[0].active.card_id
    original_hand_len = len(state.players[0].hand)
    new_state = evolve_pokemon(state, hand_index=0, target=target)
    assert state.players[0].active.card_id == original_card_id
    assert len(state.players[0].hand) == original_hand_len
