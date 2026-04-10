"""Tests for play_card.py — playing cards from hand."""
import pytest
from ptcgp.cards.database import load_defaults
from ptcgp.cards.types import Element
from ptcgp.engine.actions import SlotRef
from ptcgp.engine.play_card import attach_tool, play_basic, play_item, play_supporter
from ptcgp.engine.state import GameState, PlayerState, PokemonSlot


def setup_module():
    load_defaults()


def make_state(hand: list[str] | None = None, active_card_id: str | None = None) -> GameState:
    """Build a minimal GameState for testing."""
    active = None
    if active_card_id is not None:
        from ptcgp.cards.database import get_card
        card = get_card(active_card_id)
        active = PokemonSlot(card_id=active_card_id, current_hp=card.hp, max_hp=card.hp)

    player = PlayerState(
        active=active,
        hand=list(hand or []),
        energy_types=[Element.GRASS],
    )
    state = GameState(players=[player, PlayerState()])
    return state


# --- play_basic ---

def test_play_basic_to_bench():
    """Basic Pokemon from hand lands in bench slot 0."""
    state = make_state(hand=["a1-001"])  # Bulbasaur
    new_state = play_basic(state, hand_index=0, bench_slot=0)
    player = new_state.players[0]
    assert player.bench[0] is not None
    assert player.bench[0].card_id == "a1-001"


def test_play_basic_removes_from_hand():
    """Card is removed from hand after playing."""
    state = make_state(hand=["a1-001"])
    new_state = play_basic(state, hand_index=0, bench_slot=0)
    player = new_state.players[0]
    assert "a1-001" not in player.hand
    assert len(player.hand) == 0


def test_play_basic_sets_correct_hp():
    """Bench slot HP equals card's base HP."""
    from ptcgp.cards.database import get_card
    state = make_state(hand=["a1-001"])
    new_state = play_basic(state, hand_index=0, bench_slot=0)
    card = get_card("a1-001")
    slot = new_state.players[0].bench[0]
    assert slot.current_hp == card.hp
    assert slot.max_hp == card.hp
    assert slot.turns_in_play == 0


def test_play_basic_invalid_if_bench_occupied():
    """Cannot play to an occupied bench slot."""
    state = make_state(hand=["a1-001", "a1-005"])  # Bulbasaur, Caterpie
    state = play_basic(state, hand_index=0, bench_slot=0)
    # Hand now has Caterpie only; try to play to same slot
    with pytest.raises(ValueError, match="already occupied"):
        play_basic(state, hand_index=0, bench_slot=0)


def test_play_basic_fails_for_non_basic():
    """Cannot play a Stage 1 Pokemon as a basic."""
    state = make_state(hand=["a1-002"])  # Ivysaur is Stage 1
    with pytest.raises(ValueError):
        play_basic(state, hand_index=0, bench_slot=0)


def test_play_basic_does_not_mutate_original():
    """Original state is unchanged (copy-on-write)."""
    state = make_state(hand=["a1-001"])
    new_state = play_basic(state, hand_index=0, bench_slot=0)
    assert state.players[0].bench[0] is None
    assert len(state.players[0].hand) == 1


# --- play_item ---

def test_play_item_goes_to_discard():
    """Item card is removed from hand and added to discard."""
    state = make_state(hand=["pa-001"])  # Potion
    new_state = play_item(state, hand_index=0)
    player = new_state.players[0]
    assert "pa-001" not in player.hand
    assert "pa-001" in player.discard


def test_play_item_does_not_mutate_original():
    """Original state is unchanged."""
    state = make_state(hand=["pa-001"])
    new_state = play_item(state, hand_index=0)
    assert len(state.players[0].hand) == 1
    assert len(state.players[0].discard) == 0


def test_play_item_fails_for_non_item():
    """Cannot play a Pokemon card as an item."""
    state = make_state(hand=["a1-001"])
    with pytest.raises(ValueError):
        play_item(state, hand_index=0)


# --- play_supporter ---

def test_play_supporter_sets_flag():
    """has_played_supporter is set to True after playing a Supporter."""
    state = make_state(hand=["pa-007"])  # Professor's Research
    new_state = play_supporter(state, hand_index=0)
    assert new_state.players[0].has_played_supporter is True


def test_play_supporter_goes_to_discard():
    """Supporter card goes to discard."""
    state = make_state(hand=["pa-007"])
    new_state = play_supporter(state, hand_index=0)
    player = new_state.players[0]
    assert "pa-007" not in player.hand
    assert "pa-007" in player.discard


def test_play_supporter_fails_for_non_supporter():
    """Cannot play an item as a supporter."""
    state = make_state(hand=["pa-001"])
    with pytest.raises(ValueError):
        play_supporter(state, hand_index=0)


# --- attach_tool ---

def test_attach_tool_sets_tool_id():
    """Tool card's ID is stored on the target Pokemon slot."""
    # Active is Bulbasaur, tool in hand
    state = make_state(hand=["a2-147"], active_card_id="a1-001")  # Giant Cape
    target = SlotRef.active(player=0)
    new_state = attach_tool(state, hand_index=0, target=target)
    assert new_state.players[0].active.tool_card_id == "a2-147"


def test_attach_tool_removes_from_hand_and_stays_attached():
    """Tool is removed from hand and stays attached to the Pokemon slot.

    Tools do NOT go to discard on attach — they are discarded with the Pokemon
    when it is knocked out.
    """
    state = make_state(hand=["a2-147"], active_card_id="a1-001")
    target = SlotRef.active(player=0)
    new_state = attach_tool(state, hand_index=0, target=target)
    player = new_state.players[0]
    assert "a2-147" not in player.hand
    assert "a2-147" not in player.discard
    assert new_state.players[0].active.tool_card_id == "a2-147"


def test_attach_tool_fails_if_already_has_tool():
    """Cannot attach a second tool to a Pokemon that already has one."""
    state = make_state(hand=["a2-147"], active_card_id="a1-001")
    target = SlotRef.active(player=0)
    new_state = attach_tool(state, hand_index=0, target=target)

    # Give it another tool card in hand and try again
    new_state.players[0].hand.append("a2-148")  # Rocky Helmet
    with pytest.raises(ValueError, match="already has a tool"):
        attach_tool(new_state, hand_index=0, target=target)


def test_attach_tool_fails_for_non_tool():
    """Cannot call attach_tool with an Item card."""
    state = make_state(hand=["pa-001"], active_card_id="a1-001")  # Potion
    target = SlotRef.active(player=0)
    with pytest.raises(ValueError):
        attach_tool(state, hand_index=0, target=target)
