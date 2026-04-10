"""Tests for retreat.py — retreating the active Pokemon."""
import pytest
from ptcgp.cards.database import load_defaults
from ptcgp.cards.types import Element
from ptcgp.engine.retreat import retreat
from ptcgp.engine.state import GameState, PlayerState, PokemonSlot, StatusEffect


def setup_module():
    load_defaults()


def make_retreat_state(
    active_card_id: str = "a1-001",    # Bulbasaur (retreat_cost=1)
    bench_card_id: str = "a1-005",     # Caterpie
    bench_slot: int = 0,
    active_energy: dict | None = None,
    active_status: set | None = None,
    has_retreated: bool = False,
) -> GameState:
    """Build a minimal state with an active and a bench Pokemon for retreat testing."""
    from ptcgp.cards.database import get_card

    a_card = get_card(active_card_id)
    b_card = get_card(bench_card_id)

    active_slot = PokemonSlot(
        card_id=active_card_id,
        current_hp=a_card.hp,
        max_hp=a_card.hp,
        attached_energy=dict({Element.GRASS: 1} if active_energy is None else active_energy),
        status_effects=set(active_status or set()),
    )

    bench = [None, None, None]
    bench[bench_slot] = PokemonSlot(
        card_id=bench_card_id,
        current_hp=b_card.hp,
        max_hp=b_card.hp,
    )

    player = PlayerState(
        active=active_slot,
        bench=bench,
        has_retreated=has_retreated,
        energy_types=[Element.GRASS],
    )
    state = GameState(players=[player, PlayerState()])
    return state


# --- basic retreat ---

def test_retreat_swaps_active_bench():
    """After retreating, bench Pokemon is now active and vice versa."""
    state = make_retreat_state()  # Bulbasaur active, Caterpie on bench
    new_state = retreat(state, bench_slot=0)
    assert new_state.players[0].active.card_id == "a1-005"   # Caterpie is now active
    assert new_state.players[0].bench[0].card_id == "a1-001"  # Bulbasaur is on bench


def test_retreat_sets_flag():
    """has_retreated is True after retreating."""
    state = make_retreat_state()
    new_state = retreat(state, bench_slot=0)
    assert new_state.players[0].has_retreated is True


def test_retreat_clears_status():
    """Status effects are cleared from the retreating (now bench) Pokemon."""
    state = make_retreat_state(
        active_status={StatusEffect.POISONED, StatusEffect.CONFUSED},
        active_energy={Element.GRASS: 2},  # Extra energy so retreat cost is covered
    )
    new_state = retreat(state, bench_slot=0)
    # Bulbasaur moved to bench at slot 0
    bench_slot = new_state.players[0].bench[0]
    assert len(bench_slot.status_effects) == 0


def test_retreat_discards_energy_randomly():
    """Energy count is reduced by retreat_cost after retreating."""
    from ptcgp.cards.database import get_card
    active_card = get_card("a1-001")
    retreat_cost = active_card.retreat_cost  # Bulbasaur has retreat_cost=1
    # Give active 3 grass energy
    state = make_retreat_state(active_energy={Element.GRASS: 3})
    new_state = retreat(state, bench_slot=0)
    # After retreating, Bulbasaur is now on bench
    bench_bulbasaur = new_state.players[0].bench[0]
    remaining = bench_bulbasaur.total_energy()
    assert remaining == 3 - retreat_cost


def test_retreat_zero_cost_always_works():
    """Pokemon with retreat_cost=0 can always retreat without spending energy."""
    # Find a 0 retreat cost Pokemon
    from ptcgp.cards.database import get_all_cards
    zero_cost_cards = [
        c for c in get_all_cards().values()
        if c.is_pokemon and c.retreat_cost == 0 and c.stage is not None
    ]
    assert zero_cost_cards, "No 0-cost retreat Pokemon found in database"
    zero_card = zero_cost_cards[0]

    from ptcgp.cards.database import get_card
    bench_card = get_card("a1-005")  # Caterpie as bench

    active_slot = PokemonSlot(
        card_id=zero_card.id,
        current_hp=zero_card.hp,
        max_hp=zero_card.hp,
        attached_energy={},  # No energy at all
    )
    bench = [None, None, None]
    bench[0] = PokemonSlot(
        card_id="a1-005",
        current_hp=bench_card.hp,
        max_hp=bench_card.hp,
    )
    player = PlayerState(active=active_slot, bench=bench, energy_types=[Element.GRASS])
    state = GameState(players=[player, PlayerState()])

    new_state = retreat(state, bench_slot=0)
    assert new_state.players[0].active.card_id == "a1-005"


# --- failure cases ---

def test_retreat_blocked_if_paralyzed():
    """Raises ValueError if active Pokemon is Paralyzed."""
    state = make_retreat_state(
        active_status={StatusEffect.PARALYZED},
        active_energy={Element.GRASS: 2},
    )
    with pytest.raises(ValueError, match="Paralyzed"):
        retreat(state, bench_slot=0)


def test_retreat_blocked_if_asleep():
    """Raises ValueError if active Pokemon is Asleep."""
    state = make_retreat_state(
        active_status={StatusEffect.ASLEEP},
        active_energy={Element.GRASS: 2},
    )
    with pytest.raises(ValueError, match="Asleep"):
        retreat(state, bench_slot=0)


def test_retreat_blocked_if_already_retreated():
    """Raises ValueError if player has already retreated this turn."""
    state = make_retreat_state(has_retreated=True)
    with pytest.raises(ValueError, match="Already retreated"):
        retreat(state, bench_slot=0)


def test_retreat_blocked_if_not_enough_energy():
    """Raises ValueError if active doesn't have enough energy for retreat cost."""
    # Bulbasaur needs 1 energy to retreat
    state = make_retreat_state(active_energy={})  # No energy
    with pytest.raises(ValueError, match="Not enough energy"):
        retreat(state, bench_slot=0)


def test_retreat_blocked_if_bench_empty():
    """Raises ValueError if target bench slot is empty."""
    from ptcgp.cards.database import get_card
    card = get_card("a1-001")
    active_slot = PokemonSlot(
        card_id="a1-001",
        current_hp=card.hp,
        max_hp=card.hp,
        attached_energy={Element.GRASS: 1},
    )
    player = PlayerState(active=active_slot, energy_types=[Element.GRASS])
    state = GameState(players=[player, PlayerState()])
    with pytest.raises(ValueError, match="No Pokemon in bench slot"):
        retreat(state, bench_slot=0)


def test_retreat_does_not_mutate_original():
    """Original state is unchanged (copy-on-write)."""
    state = make_retreat_state()
    original_active = state.players[0].active.card_id
    new_state = retreat(state, bench_slot=0)
    assert state.players[0].active.card_id == original_active
    assert state.players[0].has_retreated is False
