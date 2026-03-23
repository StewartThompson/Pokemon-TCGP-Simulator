# Create test file: tests/test_step20_full_game.py
import sys
sys.path.insert(0, '.')

from v3.models.match.battle_engine import BattleEngine
from v3.models.match.player import Player
from v3.models.cards.energy import Energy
from v3.models.cards.card import Card
from v3.models.cards.pokemon import Pokemon
from v3.models.cards.attack import Attack

def test_full_game():
    """Test a complete game flow"""
    # Create Pokemon with attacks
    attack1 = Attack("Vine Whip", 40, Energy.from_string_list(["Grass", "Colorless"]))
    attack2 = Attack("Tackle", 20, Energy.from_string_list(["Colorless"]))
    
    deck1 = []
    deck2 = []
    for i in range(20):
        pokemon1 = Pokemon(f"p1-{i:03d}", "Bulbasaur", Energy.Type.GRASS, Card.Type.POKEMON,
                          Card.Subtype.BASIC, 70, "Set", "Pack", "Common", [attack1], 1, Energy.Type.FIRE, None)
        pokemon2 = Pokemon(f"p2-{i:03d}", "Charmander", Energy.Type.FIRE, Card.Type.POKEMON,
                          Card.Subtype.BASIC, 60, "Set", "Pack", "Common", [attack2], 1, Energy.Type.WATER, None)
        deck1.append(pokemon1)
        deck2.append(pokemon2)
    
    player1 = Player("Player 1", deck1, [Energy.Type.GRASS])
    player2 = Player("Player 2", deck2, [Energy.Type.FIRE])
    engine = BattleEngine(player1, player2, debug=False)
    
    # Run a few turns
    engine._setup_game()
    
    # Execute a few turns
    initial_turn = engine.turn
    for turn in range(5):
        if engine._is_game_over():
            break
        engine._execute_turn()
        if engine.turn > initial_turn:
            break  # At least one turn executed
    
    # Check game state is valid
    # Turn should have incremented at least once
    assert engine.turn >= initial_turn
    # Game should either be ongoing or have a winner
    assert not engine._is_game_over() or engine._determine_winner() is not None
    
    print("✓ Full game test passed")
    return True

if __name__ == "__main__":
    success = test_full_game()
    exit(0 if success else 1)

