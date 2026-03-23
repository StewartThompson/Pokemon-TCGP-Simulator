"""Test utility functions for Pokemon TCG Battle Simulator"""
import sys
sys.path.insert(0, '.')

from v3.models.cards.pokemon import Pokemon
from v3.models.cards.card import Card
from v3.models.cards.energy import Energy
from v3.models.cards.attack import Attack
from v3.models.match.player import Player
from v3.models.match.battle_engine import BattleEngine
from typing import List, Optional

def create_test_pokemon(
    name: str = "Test Pokemon",
    health: int = 100,
    pokemon_type: Energy.Type = Energy.Type.GRASS,
    attacks: Optional[List[Attack]] = None,
    ability = None,
    subtype: Card.Subtype = Card.Subtype.BASIC,
    evolves_from: Optional[str] = None
) -> Pokemon:
    """Create a test Pokemon with default values"""
    if attacks is None:
        attacks = []
    
    return Pokemon(
        id=f"test-{name.lower().replace(' ', '-')}",
        name=name,
        element=pokemon_type,
        type=Card.Type.POKEMON,
        subtype=subtype,
        health=health,
        set="Test Set",
        pack="Test Pack",
        rarity="Common",
        attacks=attacks,
        retreat_cost=1,
        weakness=None,
        evolves_from=evolves_from,
        ability=ability
    )

def create_test_attack(
    name: str = "Test Attack",
    damage: int = 30,
    cost: Optional[List[str]] = None
) -> Attack:
    """Create a test Attack"""
    if cost is None:
        cost = ["Colorless"]
    
    energy = Energy.from_string_list(cost)
    return Attack(
        name=name,
        ability=None,
        damage=damage,
        cost=energy
    )

def create_test_deck(pokemon_count: int = 20) -> List[Pokemon]:
    """Create a test deck with specified number of Pokemon"""
    deck = []
    for i in range(pokemon_count):
        pokemon = create_test_pokemon(name=f"Test Pokemon {i+1}")
        deck.append(pokemon)
    return deck

def create_test_players() -> tuple[Player, Player]:
    """Create two test players with basic decks"""
    deck1 = create_test_deck(20)
    deck2 = create_test_deck(20)
    player1 = Player("Player 1", deck1, [Energy.Type.GRASS])
    player2 = Player("Player 2", deck2, [Energy.Type.FIRE])
    return player1, player2

def create_test_battle_engine() -> BattleEngine:
    """Create a test battle engine with two players"""
    player1, player2 = create_test_players()
    return BattleEngine(player1, player2, debug=False)

